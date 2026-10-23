"""Límites y observabilidad comunes a las llamadas reales del proveedor."""

import logging
import math
import os
import re
import threading
import time
from collections import deque
from contextlib import contextmanager

import httpx
from google.genai import types
from google.genai.errors import APIError
from langchain_google_genai import ChatGoogleGenerativeAI

from dataia.common.credentials import get_gemini_model

logger = logging.getLogger(__name__)


def provider_limits() -> tuple[float, int]:
    timeout = float(os.getenv("IA_PROVIDER_TIMEOUT_SECONDS", "60"))
    retries = int(os.getenv("IA_PROVIDER_MAX_RETRIES", "1"))
    if not math.isfinite(timeout) or timeout <= 0 or not 0 <= retries <= 2:
        raise ValueError("Configuración inválida de límites del proveedor.")
    return timeout, retries


def provider_http_options() -> types.HttpOptions:
    timeout, retries = provider_limits()
    return types.HttpOptions(
        timeout=max(1, int(timeout * 1000)),
        retry_options=types.HttpRetryOptions(
            attempts=retries + 1, initial_delay=1, max_delay=5,
        ),
    )


def create_gemini_llm(temperature: float = 0.0, api_key: str | None = None):
    """Data/IA pasa su propia clave (DATAIA_GOOGLE_API_KEY); AI Core usa la de entorno."""
    timeout, retries = provider_limits()
    model = get_gemini_model()
    # Google recomienda el valor predeterminado para Gemini 3. LangChain
    # deja temperature=None para esta familia y el SDK usa el default.
    temperature_options = {} if model.removeprefix("models/").startswith("gemini-3") else {"temperature": temperature}
    # En langchain-google-genai 4.4, max_retries se transmite al SDK como
    # número de intentos totales. Convertimos los reintentos configurados.
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        **temperature_options,
        timeout=timeout,
        max_retries=retries + 1,
    )


def error_chain(error: Exception):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        yield error
        error = error.__cause__ or error.__context__


def is_provider_error(error: Exception) -> bool:
    return any(isinstance(e, (APIError, httpx.RequestError, TimeoutError)) for e in error_chain(error))


def safe_error_fields(error: Exception) -> tuple[str, int | None, str]:
    for current in error_chain(error):
        if isinstance(current, APIError):
            code = current.code if isinstance(current.code, int) else None
            category = {429: "cuota", 503: "indisponibilidad", 504: "timeout"}.get(code, "proveedor")
            return type(current).__name__, code, category
        if isinstance(current, (httpx.TimeoutException, TimeoutError)):
            return type(current).__name__, None, "timeout"
        if isinstance(current, httpx.RequestError):
            return type(current).__name__, None, "comunicacion"
    return type(error).__name__, None, "interno"


class RateLimiter:
    """
    Respeta peticiones y tokens por minuto en una ventana deslizante de 60 s
    (spec IA-02b R3). Los límites se leen en cada llamada para poder cambiarlos
    por variables de entorno sin reiniciar.
    """

    WINDOW_SECONDS = 60.0

    def __init__(self, rpm_env: str, rpm_default: int, tpm_env: str, tpm_default: int):
        self.rpm_env, self.rpm_default = rpm_env, rpm_default
        self.tpm_env, self.tpm_default = tpm_env, tpm_default
        self._events: deque[tuple[float, int, int]] = deque()
        self._lock = threading.Lock()

    def limits(self) -> tuple[int, int]:
        return int(os.getenv(self.rpm_env, self.rpm_default)), int(os.getenv(self.tpm_env, self.tpm_default))

    def acquire(self, tokens: int, requests: int = 1) -> float:
        """
        Bloquea hasta que la llamada quepa en la ventana. Devuelve los segundos esperados.
        `requests` permite contar una llamada por lotes como varias peticiones: en los
        embeddings cada chunk cuenta como una, porque el cliente divide el lote en
        varias peticiones HTTP.
        """
        waited = 0.0
        while True:
            rpm, tpm = self.limits()
            with self._lock:
                now = _clock()
                while self._events and now - self._events[0][0] >= self.WINDOW_SECONDS:
                    self._events.popleft()
                used_tokens = sum(t for _, t, _ in self._events)
                used_requests = sum(r for _, _, r in self._events)
                # Una llamada mayor que los límites se admite sola, con la ventana vacía
                if not self._events or (used_requests + requests <= rpm and used_tokens + tokens <= tpm):
                    self._events.append((now, tokens, requests))
                    return waited
                wait = self._events[0][0] + self.WINDOW_SECONDS - now + 0.05
            logger.info("IA proveedor control de ritmo: espera %.1f s (rpm=%d tpm=%d)", wait, rpm, tpm)
            _sleep(wait)
            waited += wait

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


GENERATION_LIMITER = RateLimiter("IA_PROVIDER_RPM", 10, "IA_PROVIDER_TPM", 200_000)
# Margen sobre los 30k tokens por minuto de la cuenta gratuita: la estimación local
# (palabras × 1,3) se queda hasta un 25 % corta con documentos con mucho código.
EMBEDDING_LIMITER = RateLimiter("IA_EMBEDDING_RPM", 100, "IA_EMBEDDING_TPM", 20_000)
# Cuenta gratuita de Groq: 8.000 tokens por minuto y 1.000 peticiones por día para
# gpt-oss-120b, gpt-oss-20b y qwen3.8-27b (cabeceras x-ratelimit, 2026-10-22)
GROQ_LIMITER = RateLimiter("IA_GROQ_RPM", 30, "IA_GROQ_TPM", 8_000)
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def groq_max_prompt_tokens() -> int:
    """
    Tamaño máximo de prompt que se envía a Groq: el 70 % de su límite por minuto,
    dejando margen para la respuesta y el razonamiento del modelo. Un prompt mayor
    se rechazaría (413) aunque la ventana estuviera vacía.
    """
    return int(os.getenv("IA_GROQ_MAX_PROMPT_TOKENS", int(GROQ_LIMITER.limits()[1] * 0.7)))

PROVEEDORES_ETAPA = ("gemini", "groq")


def stage_provider(stage: str) -> str:
    """
    Proveedor de una etapa (CLASIFICACION, GENERACION, CRITICO) según
    IA_PROVIDER_<ETAPA>. Groq sin GROQ_API_KEY usa Gemini (spec proveedores R1-R2).
    """
    provider = os.getenv(f"IA_PROVIDER_{stage}", "gemini").strip().lower()
    if provider not in PROVEEDORES_ETAPA:
        raise ValueError(f"IA_PROVIDER_{stage} debe ser uno de {PROVEEDORES_ETAPA}.")
    if provider == "groq" and not os.getenv("GROQ_API_KEY"):
        logger.warning("IA_PROVIDER_%s=groq sin GROQ_API_KEY: la etapa usa Gemini.", stage)
        return "gemini"
    return provider


def create_groq_llm(temperature: float = 0.0):
    from langchain_groq import ChatGroq

    timeout, retries = provider_limits()
    return ChatGroq(
        model=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=temperature,
        timeout=timeout,
        max_retries=retries,
    )


def _limited(runnable, limiter: "RateLimiter"):
    """El respaldo también respeta la cuota de su proveedor."""
    from langchain_core.runnables import RunnableLambda

    def invoke(value):
        limiter.acquire(int(len(str(value)) / 4))
        return runnable.invoke(value)

    return RunnableLambda(invoke)


def create_stage_llm(
    stage: str, schema=None, temperature: float = 0.0, gemini_api_key: str | None = None, prompt_tokens: int = 0
):
    """
    Modelo de la etapa (con salida estructurada si se indica `schema`) y el
    limitador de ritmo de su proveedor. Si la etapa usa Groq, Gemini queda como
    respaldo ante cualquier error de Groq (cuota, tamaño de la petición, caída).
    Un prompt que no cabe en la cuota por minuto de Groq va directo a Gemini.
    """
    gemini = create_gemini_llm(temperature, api_key=gemini_api_key)
    if schema is not None:
        gemini = gemini.with_structured_output(schema)
    if stage_provider(stage) == "gemini":
        return gemini, GENERATION_LIMITER
    if prompt_tokens > groq_max_prompt_tokens():
        logger.info(
            "IA proveedor etapa=%s prompt de ~%d tokens supera el máximo de Groq (%d): se usa Gemini",
            stage, prompt_tokens, groq_max_prompt_tokens(),
        )
        return gemini, GENERATION_LIMITER
    groq = create_groq_llm(temperature)
    if schema is not None:
        groq = groq.with_structured_output(schema)
    return groq.with_fallbacks([_limited(gemini, GENERATION_LIMITER)]), GROQ_LIMITER

# Reemplazables en pruebas
_clock = time.monotonic
_sleep = time.sleep

_RETRY_DELAY = re.compile(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s")


def quota_retry_delay(error: Exception) -> float | None:
    """Segundos a esperar si el error es de cuota (429); None si no lo es (spec IA-02b R4)."""
    for current in error_chain(error):
        if isinstance(current, APIError) and current.code == 429:
            match = _RETRY_DELAY.search(f"{current.details} {current}")
            return min(float(match.group(1)), 120.0) if match else 60.0
    return None


def call_provider(stage: str, fn, estimated_tokens: int = 0, limiter: RateLimiter | None = None, requests: int = 1):
    """
    Ejecuta una llamada al proveedor respetando el control de ritmo y esperando
    ante un 429 hasta IA_PROVIDER_QUOTA_RETRIES veces. Los demás errores se propagan.
    """
    limiter = limiter or GENERATION_LIMITER
    retries = int(os.getenv("IA_PROVIDER_QUOTA_RETRIES", "2"))
    for attempt in range(retries + 1):
        limiter.acquire(estimated_tokens, requests)
        try:
            with provider_call(stage):
                return fn()
        except Exception as error:
            delay = quota_retry_delay(error)
            if delay is None or attempt == retries:
                raise
            logger.warning("IA proveedor etapa=%s cuota agotada: reintento %d/%d en %.0f s", stage, attempt + 1, retries, delay)
            _sleep(delay)


@contextmanager
def provider_call(stage: str):
    started = time.monotonic()
    logger.info("IA proveedor etapa=%s estado=inicio", stage)
    try:
        yield
    except Exception as error:
        kind, code, category = safe_error_fields(error)
        logger.error(
            "IA proveedor etapa=%s estado=fallo tipo=%s codigo=%s categoria=%s segundos=%.2f",
            stage, kind, code, category, time.monotonic() - started,
        )
        raise
    else:
        logger.info("IA proveedor etapa=%s estado=fin segundos=%.2f", stage, time.monotonic() - started)
