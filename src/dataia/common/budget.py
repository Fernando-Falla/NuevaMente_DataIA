"""Límites de tamaño de los documentos y estimación de tokens (spec IA-02b)."""

import os


def _int_env(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} debe ser positivo.")
    return value


def max_file_mb() -> int:
    return _int_env("DATAIA_MAX_FILE_MB", 25)


def max_pages() -> int:
    return _int_env("DATAIA_MAX_PAGES", 300)


def max_document_tokens() -> int:
    return _int_env("DATAIA_MAX_DOCUMENT_TOKENS", 150_000)


def doc_metadata_max_tokens() -> int:
    return _int_env("DATAIA_DOC_METADATA_MAX_TOKENS", 8_000)


def estimate_tokens(text: str) -> int:
    """
    Estimación local, sin tokenizador del proveedor. Toma el mayor entre
    palabras × 1,3 (prosa) y caracteres / 4 (JSON, código, cifras), para no
    subestimar el consumo de cuota.
    """
    if not text:
        return 0
    return int(max(len(text.split()) * 1.3, len(text) / 4))
