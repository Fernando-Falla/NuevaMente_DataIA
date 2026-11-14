"""
Configuraciones centralizadas del Backend de NuevaMente.
Carga variables de entorno y define parámetros operativos y de persistencia.
"""

import os
from typing import List, Set
from dotenv import load_dotenv

load_dotenv()


class BackendSettings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "NuevaMente API")
    VERSION: str = os.getenv("API_VERSION", "1.0.0")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")

    # Límites de documentos (25 MB por defecto según IA-08)
    MAX_DOCUMENT_BYTES: int = int(os.getenv("MAX_DOCUMENT_BYTES", str(25 * 1024 * 1024)))
    ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".md", ".markdown", ".txt"}

    # Seguridad y CORS
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]

    # Configuración de OCI Object Storage
    OCI_BUCKET_NAME: str = os.getenv("OCI_BUCKET_NAME", "nuevamente-contenidos-educativos")
    _OCI_ENABLED_VAL: str = os.getenv("OCI_STORAGE_ENABLED", "false").strip().lower()
    OCI_STORAGE_ENABLED: bool = _OCI_ENABLED_VAL in {"true", "1", "yes"}

    OCI_NAMESPACE: str = os.getenv("OCI_NAMESPACE", "").strip()
    OCI_REGION: str = os.getenv("OCI_REGION", "").strip()
    OCI_AUTH_MODE: str = os.getenv("OCI_AUTH_MODE", "api_key").strip()
    OCI_CONFIG_FILE: str = os.getenv("OCI_CONFIG_FILE", "/run/secrets/oci/config")
    OCI_CONFIG_PROFILE: str = os.getenv("OCI_CONFIG_PROFILE", "DEFAULT")
    OCI_HTTP_TIMEOUT_SECONDS: float = float(os.getenv("OCI_HTTP_TIMEOUT_SECONDS", "10"))

    def validar_configuracion(self) -> None:
        """Valida coherencia de parámetros básicos de ejecución."""
        if self.MAX_DOCUMENT_BYTES <= 0:
            raise ValueError("MAX_DOCUMENT_BYTES debe ser mayor a 0.")
        if self.OCI_STORAGE_ENABLED:
            if not self.OCI_NAMESPACE or not self.OCI_BUCKET_NAME:
                raise ValueError("Para habilitar OCI se requieren OCI_NAMESPACE y OCI_BUCKET_NAME.")
            if self.OCI_AUTH_MODE not in {"api_key", "instance_principal"}:
                raise ValueError("OCI_AUTH_MODE debe ser 'api_key' o 'instance_principal'.")
            if not 0 < self.OCI_HTTP_TIMEOUT_SECONDS <= 30:
                raise ValueError("OCI_HTTP_TIMEOUT_SECONDS debe estar entre 1 y 30 segundos.")
            if self.OCI_AUTH_MODE == "instance_principal" and not self.OCI_REGION:
                raise ValueError("Instance Principal requiere OCI_REGION configurada.")


settings = BackendSettings()
settings.validar_configuracion()
