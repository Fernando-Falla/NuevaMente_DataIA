"""Límites y observabilidad comunes a las llamadas reales del proveedor."""

import logging
import math
import os
import time
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
