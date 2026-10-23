"""Specs IA-02b (tamaño y cuota) e IA-02c (dominios): pruebas sin red ni proveedor real."""

import pymupdf
import pytest
from google.genai.errors import ClientError

from dataia.common import providers
from dataia.common.budget import estimate_tokens
from dataia.common.models import DocumentMetadata, DocumentPedagogicalMetadata, ExtractedContent
from dataia.ingestion import enrichment, service as ingestion
from dataia.ingestion.enrichment import build_document_digest
from dataia.ingestion.validators import detect_domain_by_lexicon
from nuevamente_ai.agents.analizador import nodo_analizador

TEXTOS = {
    "Salud": "El protocolo de manejo de hipertensión arterial establece metas de presión arterial menores a 130/80 mmHg. "
             "La terapia inicial combina un IECA con un diurético tiazídico. Se recomienda control de creatinina y potasio.",
    "Fintech": "La conciliación de pagos con tarjeta requiere validar el código de autorización, el monto capturado y la fecha "
               "de liquidación. El adquirente transfiere los fondos al comercio descontando la tasa de intercambio y la comisión.",
    "Marketing digital": "La campaña de pago por clic se optimiza ajustando la puja por palabra clave según el costo por "
                         "adquisición objetivo. El embudo de conversión mide impresiones, clics, leads y ventas; el ROAS "
                         "compara ingresos atribuidos con inversión publicitaria.",
    "TI": "Un Deployment de Kubernetes declara el número de réplicas de un Pod. El controlador mantiene el estado deseado "
          "y realiza actualizaciones progresivas sin interrumpir el servicio.",
}
RECETA = "Para preparar la tarta de manzana, mezcla harina, azúcar y mantequilla fría. Hornea durante cuarenta minutos a temperatura media."


@pytest.fixture(autouse=True)
def aislado(monkeypatch, tmp_path):
    monkeypatch.delenv("IA_STRICT_PROVIDERS", raising=False)
    monkeypatch.setattr(enrichment, "CACHE_DIR", str(tmp_path / "metadata"))
    providers.GENERATION_LIMITER.reset()
    providers.EMBEDDING_LIMITER.reset()


def metadata_llm(dominio=None, tecnico=None):
    def fake(doc_id, _digest):
        return DocumentPedagogicalMetadata(document_id=doc_id, dominio=dominio, es_documento_tecnico=tecnico,
                                           justificacion_dominio="simulado")
    return fake


def sin_llm(*_args):
    raise AssertionError("No debía llamarse al LLM")


# --- IA-02c: dominios ---

@pytest.mark.parametrize("esperado", list(TEXTOS))
def test_lexico_detecta_los_cuatro_dominios(esperado):
    assert detect_domain_by_lexicon(TEXTOS[esperado])[0] == esperado


def test_lexico_rechaza_texto_no_tecnico_y_usa_palabras_completas():
    assert detect_domain_by_lexicon(RECETA)[0] is None
    # "api" no debe encontrarse dentro de "terapia"
    assert "api" not in detect_domain_by_lexicon("La terapia física mejora la movilidad.")[1]["TI"]


def escribir(tmp_path, texto, nombre="doc.md"):
    ruta = tmp_path / nombre
    ruta.write_text(texto, encoding="utf-8")
    return str(ruta)


@pytest.mark.parametrize("dominio", ["TI", "Fintech", "Salud", "Marketing digital"])
def test_ingestion_acepta_dominios_soportados(monkeypatch, tmp_path, dominio):
    monkeypatch.setattr(enrichment, "enrich_document_metadata", metadata_llm(dominio, True))
    resultado = ingestion.ingest_document(escribir(tmp_path, TEXTOS[dominio]))
    assert resultado.status == "aprobado"
    assert resultado.pedagogical_metadata.dominio == dominio
    assert resultado.estimated_tokens > 0


@pytest.mark.parametrize("dominio, tecnico", [("Otro", True), ("Salud", False)])
def test_ingestion_rechaza_dominio_otro_o_no_tecnico(monkeypatch, tmp_path, dominio, tecnico):
    monkeypatch.setattr(enrichment, "enrich_document_metadata", metadata_llm(dominio, tecnico))
    resultado = ingestion.ingest_document(escribir(tmp_path, TEXTOS["Salud"]))
    assert resultado.status == "rechazado"
    assert resultado.codigo == "DOMINIO_NO_SOPORTADO"


def test_sin_llm_decide_el_lexico(monkeypatch, tmp_path):
    monkeypatch.setattr(enrichment, "enrich_document_metadata", metadata_llm(None, None))
    aceptado = ingestion.ingest_document(escribir(tmp_path, TEXTOS["Fintech"]))
    assert aceptado.pedagogical_metadata.dominio == "Fintech"
    rechazado = ingestion.ingest_document(escribir(tmp_path, RECETA * 3, "receta.md"))
    assert rechazado.codigo == "DOMINIO_NO_SOPORTADO"


def test_analizador_agrega_pautas_del_dominio():
    prompt = nodo_analizador({"perfil_destinatario": "Junior", "formato_salida": "Flashcards", "dominio_documento": "Salud",
                              "fragmentos_relevantes": [{"contenido": TEXTOS["Salud"]}]})["prompt_sistema_calibrado"]
    assert "DOMINIO DEL DOCUMENTO: SALUD" in prompt
    assert "no sustituye el criterio de un profesional" in prompt


# --- IA-02b: tamaño ---

def test_rechaza_archivo_grande_sin_abrirlo(monkeypatch, tmp_path):
    monkeypatch.setenv("DATAIA_MAX_FILE_MB", "1")
    monkeypatch.setattr(enrichment, "enrich_document_metadata", sin_llm)
    resultado = ingestion.ingest_document(escribir(tmp_path, "palabra " * 200_000))
    assert resultado.codigo == "ARCHIVO_DEMASIADO_GRANDE"
    assert "1 MB" in resultado.mensaje


def test_rechaza_pdf_con_demasiadas_paginas_antes_de_extraer(monkeypatch, tmp_path):
    monkeypatch.setenv("DATAIA_MAX_PAGES", "2")
    monkeypatch.setattr(enrichment, "enrich_document_metadata", sin_llm)
    monkeypatch.setattr(ingestion, "_extract_pdf", sin_llm)
    ruta = tmp_path / "largo.pdf"
    pdf = pymupdf.open()
    for _ in range(3):
        pdf.new_page().insert_text((72, 72), TEXTOS["TI"][:80])
    pdf.save(str(ruta))
    pdf.close()
    resultado = ingestion.ingest_document(str(ruta))
    assert resultado.codigo == "DOCUMENTO_DEMASIADO_EXTENSO"
    assert "3 páginas" in resultado.mensaje


def test_rechaza_exceso_de_tokens_sin_llamar_al_llm(monkeypatch, tmp_path):
    monkeypatch.setenv("DATAIA_MAX_DOCUMENT_TOKENS", "100")
    monkeypatch.setattr(enrichment, "enrich_document_metadata", sin_llm)
    resultado = ingestion.ingest_document(escribir(tmp_path, TEXTOS["TI"] * 10))
    assert resultado.codigo == "DOCUMENTO_DEMASIADO_EXTENSO"
    assert "tokens" in resultado.mensaje


def test_resumen_acotado_conserva_titulos():
    secciones = "\n\n".join(f"## Sección {i}\n\n" + ("Contenido técnico de la sección. " * 300) for i in range(40))
    contenido = [ExtractedContent(text=secciones, metadata=DocumentMetadata(document_id="d", name="n", doc_type="md"))]
    resumen = build_document_digest(contenido, max_tokens=2_000)
    assert estimate_tokens(resumen) <= 2_000
    assert "## Sección 0" in resumen and "## Sección 39" in resumen


def test_documento_pequeno_se_envia_completo():
    contenido = [ExtractedContent(text=TEXTOS["TI"], metadata=DocumentMetadata(document_id="d", name="n", doc_type="md"))]
    assert build_document_digest(contenido, max_tokens=2_000) == TEXTOS["TI"]


# --- IA-02b: cuota ---

class Reloj:
    def __init__(self):
        self.ahora = 0.0
        self.esperas = []

    def clock(self):
        return self.ahora

    def sleep(self, segundos):
        self.esperas.append(segundos)
        self.ahora += segundos


@pytest.fixture
def reloj(monkeypatch):
    r = Reloj()
    monkeypatch.setattr(providers, "_clock", r.clock)
    monkeypatch.setattr(providers, "_sleep", r.sleep)
    return r


def test_control_de_ritmo_por_peticiones(monkeypatch, reloj):
    monkeypatch.setenv("IA_PROVIDER_RPM", "2")
    for _ in range(3):
        providers.GENERATION_LIMITER.acquire(10)
    assert len(reloj.esperas) == 1 and 59 < reloj.esperas[0] <= 61


def test_control_de_ritmo_por_tokens(monkeypatch, reloj):
    monkeypatch.setenv("IA_PROVIDER_TPM", "1000")
    providers.GENERATION_LIMITER.acquire(800)
    providers.GENERATION_LIMITER.acquire(300)
    assert len(reloj.esperas) == 1


def error_cuota(segundos="7s"):
    return ClientError(429, {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED",
                                       "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": segundos}]}})


def test_espera_y_reintenta_ante_un_429(reloj):
    intentos = []

    def llamada():
        intentos.append(1)
        if len(intentos) == 1:
            raise error_cuota()
        return "ok"

    assert providers.call_provider("PRUEBA", llamada) == "ok"
    assert len(intentos) == 2
    assert 7.0 in reloj.esperas


def test_429_persistente_se_propaga(monkeypatch, reloj):
    monkeypatch.setenv("IA_PROVIDER_QUOTA_RETRIES", "1")

    def llamada():
        raise error_cuota("3s")

    with pytest.raises(ClientError):
        providers.call_provider("PRUEBA", llamada)
    assert reloj.esperas == [3.0]


def test_otros_errores_no_se_reintentan(reloj):
    intentos = []

    def llamada():
        intentos.append(1)
        raise TimeoutError("sin respuesta")

    with pytest.raises(TimeoutError):
        providers.call_provider("PRUEBA", llamada)
    assert len(intentos) == 1 and reloj.esperas == []


def test_cada_chunk_cuenta_como_peticion_de_embeddings(monkeypatch, reloj):
    monkeypatch.setenv("IA_EMBEDDING_RPM", "30")
    providers.EMBEDDING_LIMITER.acquire(100, requests=20)
    providers.EMBEDDING_LIMITER.acquire(100, requests=20)
    assert len(reloj.esperas) == 1


def test_lotes_de_embeddings_no_superan_un_tercio_de_la_cuota(monkeypatch):
    from langchain_core.documents import Document
    from dataia.vectorstore.client import _embedding_batches

    monkeypatch.setenv("IA_EMBEDDING_TPM", "3000")
    documentos = [Document(page_content="palabra " * 400) for _ in range(10)]  # ~520 tokens cada uno
    lotes = list(_embedding_batches(documentos, [f"id{i}" for i in range(10)]))
    assert sum(len(b) for b, _, _ in lotes) == 10
    assert all(tokens <= 1000 for _, _, tokens in lotes)
