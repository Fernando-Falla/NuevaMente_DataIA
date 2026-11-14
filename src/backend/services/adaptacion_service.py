"""
Servicio de orquestación de adaptación pedagógica en memoria/proceso.
Gestiona el almacenamiento temporal seguro del documento y coordina la ejecución
directa con el pipeline Data & IA (etapas IA-01 a IA-08).
"""

import logging
from pathlib import Path
import re
import tempfile
from typing import Optional, Union

from nuevamente_ai.pipeline import ejecutar_pipeline_adaptacion_controlado
from nuevamente_ai.schemas import (
    AdaptacionErrorResponseDTO,
    AdaptacionResponseDTO,
    CodigoErrorEnum,
    FormatoSalidaEnum,
    NichoSectorEnum,
    NivelDetalleEnum,
    PerfilDestinatarioEnum,
)

logger = logging.getLogger(__name__)


def sanitizar_titulo(titulo: Optional[str], filename: str) -> str:
    """Obtiene y sanitiza un título válido para el documento procesado."""
    if titulo and titulo.strip():
        limpio = titulo.strip()
    else:
        # Extraer el nombre base sin extensión y reemplazar guiones y guiones bajos por espacios
        base = Path(filename).stem
        limpio = base.replace("_", " ").replace("-", " ")
        limpio = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚáéíóúÑñ\s\.,]", " ", limpio)
        limpio = re.sub(r"\s+", " ", limpio).strip()

    if not limpio or len(limpio) < 3:
        limpio = "Documento Tecnico de Estudio"
    return limpio[:150]


def procesar_adaptacion_directa(
    file_bytes: bytes,
    filename: str,
    perfil: PerfilDestinatarioEnum,
    formato: FormatoSalidaEnum,
    nicho: NichoSectorEnum = NichoSectorEnum.GENERAL,
    nivel_detalle: NivelDetalleEnum = NivelDetalleEnum.DIDACTICO,
    documento_titulo: Optional[str] = None
) -> Union[AdaptacionResponseDTO, AdaptacionErrorResponseDTO]:
    """
    Ejecuta el pipeline de adaptación pedagógica directamente en memoria/proceso.
    Crea un archivo temporal seguro en disco para las herramientas de parsing (PyMuPDF),
    asegurando su eliminación al culminar la ejecución.
    """
    titulo = sanitizar_titulo(documento_titulo, filename)
    extension = Path(filename).suffix.lower()

    # Creación de directorio temporal aislado para garantizar compatibilidad con Windows y concurrencia
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = Path(temp_dir) / f"temp_upload{extension}"
        temp_file_path.write_bytes(file_bytes)

        logger.info(
            "Iniciando pipeline en proceso: titulo='%s', perfil='%s', formato='%s', nicho='%s'",
            titulo, perfil.value, formato.value, nicho.value
        )

        try:
            resultado = ejecutar_pipeline_adaptacion_controlado(
                documento_titulo=titulo,
                documento_contenido=None,
                ruta_archivo=str(temp_file_path),
                perfil=perfil.value,
                formato=formato.value,
                nicho=nicho.value,
                nivel_detalle=nivel_detalle.value,
            )
            return resultado
        except Exception as exc:
            logger.exception("Error no capturado durante ejecución de pipeline: %s", exc)
            return AdaptacionErrorResponseDTO(
                status="error",
                codigo_error=CodigoErrorEnum.ERROR_INTERNO,
                http_status=500,
                mensaje=f"Error inesperado al ejecutar el pipeline de IA: {str(exc)}",
                sugerencia="Contacta al soporte o verifica los logs del backend."
            )
