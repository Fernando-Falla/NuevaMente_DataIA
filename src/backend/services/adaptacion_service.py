"""
Servicio de orquestación de adaptación pedagógica en memoria/proceso.
Gestiona el almacenamiento temporal seguro del documento y coordina la ejecución
directa con el pipeline Data & IA (etapas IA-01 a IA-08).
"""

import asyncio
import json
import logging
from pathlib import Path
import re
import tempfile
import time
from typing import Any, AsyncGenerator, Optional, Union

from nuevamente_ai.pipeline import ejecutar_pipeline_adaptacion_controlado
from nuevamente_ai.schemas import (
    AdaptacionErrorResponseDTO,
    AdaptacionResponseDTO,
    CodigoErrorEnum,
    FaseProgresoEnum,
    FormatoSalidaEnum,
    NichoSectorEnum,
    NivelDetalleEnum,
    PerfilDestinatarioEnum,
    TelemetriaEstadoResponse,
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


async def procesar_adaptacion_stream(
    file_bytes: bytes,
    filename: str,
    perfil: PerfilDestinatarioEnum,
    formato: FormatoSalidaEnum,
    nicho: NichoSectorEnum = NichoSectorEnum.GENERAL,
    nivel_detalle: NivelDetalleEnum = NivelDetalleEnum.DIDACTICO,
    documento_titulo: Optional[str] = None,
    oci_storage: Optional[Any] = None,
) -> AsyncGenerator[str, None]:
    """
    Ejecuta el pipeline de adaptación pedagógica emitiendo eventos Server-Sent Events (SSE).
    Reporta en tiempo real las fases del pipeline (TelemetriaEstadoResponse) y finalmente
    el artefacto adaptado (AdaptacionResponseDTO) o error (AdaptacionErrorResponseDTO).
    """
    titulo = sanitizar_titulo(documento_titulo, filename)
    extension = Path(filename).suffix.lower()
    start_time = time.perf_counter()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

    def callback_telemetria(etapa: str, paso: int, progreso: int, mensaje: str) -> None:
        elapsed = round(time.perf_counter() - start_time, 2)
        try:
            fase_enum = FaseProgresoEnum(etapa)
        except (ValueError, KeyError):
            fase_enum = FaseProgresoEnum.EXTRACCION

        telemetria = TelemetriaEstadoResponse(
            fase_actual=fase_enum,
            fase_numero=paso,
            porcentaje_progreso=progreso,
            mensaje_descriptivo=mensaje,
            tiempo_transcurrido_segundos=elapsed,
        )
        loop.call_soon_threadsafe(
            queue.put_nowait,
            ("telemetria", telemetria.model_dump_json())
        )

    def worker() -> None:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file_path = Path(temp_dir) / f"temp_upload{extension}"
                temp_file_path.write_bytes(file_bytes)

                logger.info(
                    "Iniciando pipeline en streaming: titulo='%s', perfil='%s', formato='%s', nicho='%s'",
                    titulo, perfil.value, formato.value, nicho.value
                )

                resultado = ejecutar_pipeline_adaptacion_controlado(
                    documento_titulo=titulo,
                    documento_contenido=None,
                    ruta_archivo=str(temp_file_path),
                    perfil=perfil.value,
                    formato=formato.value,
                    nicho=nicho.value,
                    nivel_detalle=nivel_detalle.value,
                    callback_telemetria=callback_telemetria,
                )

                if isinstance(resultado, AdaptacionErrorResponseDTO):
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        ("error", resultado.model_dump_json())
                    )
                    return

                # Almacenamiento opcional en OCI Object Storage si está activo
                if oci_storage is not None:
                    elapsed = round(time.perf_counter() - start_time, 2)
                    telemetria_oci = TelemetriaEstadoResponse(
                        fase_actual=FaseProgresoEnum.PERSISTENCIA,
                        fase_numero=5,
                        porcentaje_progreso=95,
                        mensaje_descriptivo="Persistiendo documento fuente y artefacto JSON en OCI Object Storage...",
                        tiempo_transcurrido_segundos=elapsed,
                    )
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        ("telemetria", telemetria_oci.model_dump_json())
                    )
                    resultado = oci_storage.guardar(file_bytes, filename, resultado)

                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ("resultado", resultado.model_dump_json(exclude_unset=True))
                )
        except Exception as exc:
            logger.exception("Error no capturado en worker de streaming: %s", exc)
            err_dto = AdaptacionErrorResponseDTO(
                status="error",
                codigo_error=CodigoErrorEnum.ERROR_INTERNO,
                http_status=500,
                mensaje=f"Error inesperado durante la ejecución en streaming: {str(exc)}",
                sugerencia="Contacta al soporte o verifica los registros del backend."
            )
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("error", err_dto.model_dump_json())
            )
        finally:
            elapsed_final = round(time.perf_counter() - start_time, 2)
            fin_payload = json.dumps({"status": "finalizado", "tiempo_total_segundos": elapsed_final})
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("fin", fin_payload)
            )

    worker_task = asyncio.create_task(asyncio.to_thread(worker))
    try:
        while True:
            event_type, payload = await queue.get()
            yield f"event: {event_type}\ndata: {payload}\n\n"
            queue.task_done()
            if event_type == "fin":
                break
    except asyncio.CancelledError:
        logger.info("Cliente desconectado de la sesión de streaming: %s", filename)
        raise
    finally:
        await worker_task
