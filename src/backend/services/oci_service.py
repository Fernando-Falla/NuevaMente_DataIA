"""
Persistencia dual en Oracle Cloud Infrastructure (OCI) Object Storage:
Almacena el documento fuente original y el paquete pedagógico aprobado en JSON.
"""

import base64
from datetime import datetime, timezone
from hashlib import md5, sha256
from io import BytesIO
import json
import logging
from pathlib import Path
import re
from typing import Callable, Optional

import oci

from backend.config import settings
from nuevamente_ai.schemas import AdaptacionResponseDTO, AlmacenamientoOCI

logger = logging.getLogger(__name__)


def create_oci_client():
    """Fabrica el cliente de OCI Object Storage según la configuración del entorno."""
    options = {
        "timeout": (5, settings.OCI_HTTP_TIMEOUT_SECONDS),
        "retry_strategy": oci.retry.NoneRetryStrategy(),
    }
    if settings.OCI_AUTH_MODE == "instance_principal":
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner(
            federation_client_retry_strategy=oci.retry.NoneRetryStrategy(),
        )
        return oci.object_storage.ObjectStorageClient(
            {"region": settings.OCI_REGION}, signer=signer, **options
        )
    config = oci.config.from_file(settings.OCI_CONFIG_FILE, settings.OCI_CONFIG_PROFILE)
    if settings.OCI_REGION:
        config["region"] = settings.OCI_REGION
    return oci.object_storage.ObjectStorageClient(config, **options)


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class OCIStorage:
    def __init__(
        self,
        namespace: str,
        bucket: str,
        client_factory: Callable = create_oci_client,
        clock: Optional[Callable[[], datetime]] = None
    ):
        self.namespace = namespace
        self.bucket = bucket
        self.client_factory = client_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def guardar(
        self,
        documento_bytes: bytes,
        filename: str,
        resultado: AdaptacionResponseDTO
    ) -> AdaptacionResponseDTO:
        """
        Persiste el archivo original y el artefacto JSON generado en OCI.
        Si la subida falla, actualiza el estado de almacenamiento sin abortar el material adaptado.
        """
        digest = sha256(documento_bytes).hexdigest()
        nombre_limpio = (filename or "documento.txt").replace("\\", "/").rsplit("/", 1)[-1]
        suffix = Path(nombre_limpio).suffix.lower()
        stem = re.sub(r"[^A-Za-z0-9_-]", "_", Path(nombre_limpio).stem).strip("_")[:64] or "documento"
        period = self.clock().strftime("%Y/%m")
        source_key = f"documentos-fuente/{period}/{digest}-{stem}{suffix}"

        # Calculamos digest del artefacto
        content = resultado.model_dump(mode="json", exclude_unset=True, exclude={"almacenamiento_oci"})
        artifact_digest = sha256(_json_bytes(content)).hexdigest()
        artifact_key = f"artefactos-generados/{period}/{digest}-{artifact_digest}.json"

        stored_info = AlmacenamientoOCI(
            bucket=self.bucket,
            objeto_id=artifact_key,
            status_upload="subido",
            ruta_publica_o_par=None,
            documento_original_objeto_id=source_key,
            documento_original_subido=True,
        )

        source_confirmed = False
        stage = "configuracion"
        try:
            client = self.client_factory()
            with client.base_client.session:
                stage = "documento"
                content_type = "application/pdf" if suffix == ".pdf" else "text/plain; charset=utf-8"
                self._put(client, source_key, documento_bytes, content_type)
                source_confirmed = True

                stage = "json"
                resultado_con_oci = resultado.model_copy(update={"almacenamiento_oci": stored_info})
                json_data = _json_bytes(resultado_con_oci.model_dump(mode="json", exclude_unset=True))
                self._put(client, artifact_key, json_data, "application/json; charset=utf-8")
                return resultado_con_oci

        except Exception as error:
            code = "OCI_NO_CONFIGURADO" if stage == "configuracion" else "OCI_NO_DISPONIBLE"
            if isinstance(error, oci.exceptions.ServiceError) and error.status in {401, 403}:
                code = "OCI_ACCESO_DENEGADO"
            logger.warning("Persistencia OCI no confirmada: etapa=%s error=%s", stage, type(error).__name__)
            error_info = AlmacenamientoOCI(
                bucket=self.bucket,
                objeto_id=artifact_key,
                status_upload="parcial" if source_confirmed else "error",
                ruta_publica_o_par=None,
                documento_original_objeto_id=source_key,
                documento_original_subido=source_confirmed,
                codigo_error=code,
                mensaje="No se pudo confirmar la subida a OCI. El contenido generado se conserva íntegro.",
            )
            return resultado.model_copy(update={"almacenamiento_oci": error_info})

    def _put(self, client, key: str, data: bytes, content_type: str) -> None:
        response = client.put_object(
            self.namespace,
            self.bucket,
            key,
            BytesIO(data),
            content_length=len(data),
            content_type=content_type,
            content_md5=base64.b64encode(md5(data, usedforsecurity=False).digest()).decode("ascii"),
            retry_strategy=oci.retry.NoneRetryStrategy(),
        )
        if response.status != 200:
            raise RuntimeError(f"OCI no confirmó la operación PutObject (Status: {response.status}).")


def get_oci_storage() -> Optional[OCIStorage]:
    """Dependencia FastAPI: provee la instancia de OCIStorage si está activada."""
    if not settings.OCI_STORAGE_ENABLED:
        return None
    return OCIStorage(settings.OCI_NAMESPACE, settings.OCI_BUCKET_NAME)
