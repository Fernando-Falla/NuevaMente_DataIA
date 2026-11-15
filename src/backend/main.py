"""
Servidor FastAPI unificado para NuevaMente (Data & IA Pipeline).
Expone endpoints REST y ejecuta el pipeline de IA directamente en memoria/proceso.
"""

import logging
import os
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from backend.config import settings
from backend.services.adaptacion_service import (
    procesar_adaptacion_directa,
    procesar_adaptacion_stream,
)
from backend.services.oci_service import OCIStorage, get_oci_storage
from nuevamente_ai.pipeline import ErrorPipelineIA
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

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend unificado de NuevaMente para adaptación pedagógica automatizada con Data & IA Pipeline.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
def read_root():
    """Ruta raíz de bienvenida."""
    return {"message": "API de NuevaMente en ejecución", "status": "ok"}


@app.get("/health", tags=["Health"])
def health_check():
    """Chequeo de salud del servicio backend unificado."""
    return {
        "status": "healthy",
        "service": "nuevamente-backend",
        "version": settings.VERSION,
    }


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError):
    """Manejo de errores de validación de esquemas y tipos HTTP."""
    error_dto = AdaptacionErrorResponseDTO(
        status="error",
        codigo_error=CodigoErrorEnum.ARCHIVO_INVALIDO,
        http_status=422,
        mensaje="Parámetros de solicitud inválidos o incompletos. Revisa los campos enviados.",
        detalle={"errores": exc.errors()},
        sugerencia="Asegúrate de enviar perfil_destinatario, formato_salida y documento_original válidos.",
    )
    return JSONResponse(status_code=422, content=error_dto.model_dump(mode="json"))


@app.exception_handler(ErrorPipelineIA)
async def pipeline_error_handler(_request, exc: ErrorPipelineIA):
    """Manejo de excepciones estructuradas del pipeline de IA."""
    dto = exc.to_dto()
    return JSONResponse(status_code=exc.http_status, content=dto.model_dump(mode="json"))


@app.exception_handler(HTTPException)
async def http_exception_handler(_request, exc: HTTPException):
    """Manejo de excepciones HTTP directas."""
    if isinstance(exc.detail, dict) and "codigo_error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "codigo_error": CodigoErrorEnum.ERROR_INTERNO.value,
            "http_status": exc.status_code,
            "mensaje": str(exc.detail),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(_request, exc: Exception):
    """Manejo de cualquier excepción interna imprevista."""
    logger.exception("Excepción no controlada en Backend: %s", exc)
    error_dto = AdaptacionErrorResponseDTO(
        status="error",
        codigo_error=CodigoErrorEnum.ERROR_INTERNO,
        http_status=500,
        mensaje="Error interno del servidor en Backend.",
        detalle={"tipo": type(exc).__name__, "error": str(exc)},
        sugerencia="Verifica los registros del servidor o contacta con soporte.",
    )
    return JSONResponse(status_code=500, content=error_dto.model_dump(mode="json"))


def _validar_archivo_upload(documento_original: UploadFile) -> tuple[str, bytes, Optional[JSONResponse]]:
    """Valida extensión y tamaño del archivo cargado antes de procesarlo."""
    filename = (documento_original.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    extension = Path(filename).suffix.lower()

    if extension not in settings.ALLOWED_EXTENSIONS:
        error_dto = AdaptacionErrorResponseDTO(
            status="error",
            codigo_error=CodigoErrorEnum.ARCHIVO_INVALIDO,
            http_status=415,
            mensaje=f"Formato de archivo '{extension}' no soportado. Debe ser PDF, Markdown (.md) o TXT (.txt).",
            sugerencia="Utiliza un archivo con extensión .pdf, .md o .txt.",
        )
        return filename, b"", JSONResponse(status_code=415, content=error_dto.model_dump(mode="json"))

    documento_original.file.seek(0, os.SEEK_END)
    size = documento_original.file.tell()
    documento_original.file.seek(0)

    if size == 0:
        error_dto = AdaptacionErrorResponseDTO(
            status="error",
            codigo_error=CodigoErrorEnum.ARCHIVO_INVALIDO,
            http_status=422,
            mensaje="El documento proporcionado está vacío (0 bytes).",
            sugerencia="Proporciona un documento con contenido técnico legible.",
        )
        return filename, b"", JSONResponse(status_code=422, content=error_dto.model_dump(mode="json"))

    if size > settings.MAX_DOCUMENT_BYTES:
        max_mb = settings.MAX_DOCUMENT_BYTES // (1024 * 1024)
        error_dto = AdaptacionErrorResponseDTO(
            status="error",
            codigo_error=CodigoErrorEnum.ARCHIVO_DEMASIADO_GRANDE,
            http_status=413,
            mensaje=f"El documento supera el límite permitido de {max_mb} MB.",
            detalle={"tamano_recibido_bytes": size, "max_permitido_bytes": settings.MAX_DOCUMENT_BYTES},
            sugerencia="Reduce el tamaño del documento o divide el archivo en secciones más breves.",
        )
        return filename, b"", JSONResponse(status_code=413, content=error_dto.model_dump(mode="json"))

    content = documento_original.file.read()
    return filename, content, None


@app.post(
    f"{settings.API_V1_STR}/adaptar-contenido",
    response_model=AdaptacionResponseDTO,
    response_model_exclude_unset=True,
    status_code=status.HTTP_200_OK,
    summary="Adaptar contenido educativo mediante el Pipeline Data & IA",
    description="Recibe documento (PDF, MD, TXT) y parámetros pedagógicos, ejecuta el pipeline en memoria y retorna el paquete adaptado.",
    responses={
        400: {"model": AdaptacionErrorResponseDTO, "description": "Dominio no soportado o archivo inválido"},
        413: {"model": AdaptacionErrorResponseDTO, "description": "Archivo o documento demasiado grande"},
        415: {"model": AdaptacionErrorResponseDTO, "description": "Formato de archivo no soportado"},
        422: {"model": AdaptacionErrorResponseDTO, "description": "Formato pedagógico no adecuado o documento vacío"},
        500: {"model": AdaptacionErrorResponseDTO, "description": "Error interno del servidor"},
        503: {"model": AdaptacionErrorResponseDTO, "description": "Proveedor de IA no disponible"},
    },
    tags=["Adaptación Pedagógica"],
)
def adaptar_contenido(
    documento_original: Annotated[
        UploadFile,
        File(
            description="Documento original PDF (.pdf), Markdown (.md) o Texto (.txt).",
            json_schema_extra={"format": "binary"},
        ),
    ],
    perfil_destinatario: Annotated[
        PerfilDestinatarioEnum,
        Form(description="Perfil de destinatario: Junior, Senior, Ejecutivo."),
    ] = PerfilDestinatarioEnum.JUNIOR,
    formato_salida: Annotated[
        FormatoSalidaEnum,
        Form(description="Formato educativo: Flashcards, Quiz Interactivo, Mapa Mental, Guia Paso a Paso, Resumen Ejecutivo."),
    ] = FormatoSalidaEnum.FLASHCARDS,
    nicho_sector: Annotated[
        NichoSectorEnum,
        Form(description="Nicho o sector: TI, Fintech, Salud, Marketing digital, General."),
    ] = NichoSectorEnum.GENERAL,
    nivel_detalle: Annotated[
        NivelDetalleEnum,
        Form(description="Nivel de profundidad didáctica: Didactico, Tecnico Intermedio, Exhaustivo."),
    ] = NivelDetalleEnum.DIDACTICO,
    documento_titulo: Annotated[
        Optional[str],
        Form(description="Título personalizado del documento (opcional)."),
    ] = None,
    oci_storage: Annotated[
        Optional[OCIStorage],
        Depends(get_oci_storage),
    ] = None,
):
    """
    Endpoint principal para adaptación de contenidos educativos.
    Valida transporte, persiste temporalmente y ejecuta el pipeline Data & IA en memoria.
    """
    filename, content, error_resp = _validar_archivo_upload(documento_original)
    if error_resp is not None:
        return error_resp

    # Procesamiento directo en proceso/memoria
    resultado = procesar_adaptacion_directa(
        file_bytes=content,
        filename=filename,
        perfil=perfil_destinatario,
        formato=formato_salida,
        nicho=nicho_sector,
        nivel_detalle=nivel_detalle,
        documento_titulo=documento_titulo,
    )

    # Manejo de respuesta según contrato canónico IA-08
    if isinstance(resultado, AdaptacionErrorResponseDTO):
        return JSONResponse(status_code=resultado.http_status, content=resultado.model_dump(mode="json"))

    # Almacenamiento opcional en OCI Object Storage
    if oci_storage is not None:
        resultado = oci_storage.guardar(content, filename, resultado)

    return resultado


@app.post(
    f"{settings.API_V1_STR}/adaptar-contenido/stream",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Adaptar contenido educativo con streaming SSE de telemetría (BE-02)",
    description="Recibe documento (PDF, MD, TXT) y parámetros pedagógicos, ejecutando el pipeline mientras emite eventos Server-Sent Events (SSE) con el progreso en tiempo real de las 5 etapas, seguido del resultado final o error.",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Flujo continuo de eventos SSE ('telemetria', 'resultado', 'error', 'fin').",
        },
        400: {"model": AdaptacionErrorResponseDTO, "description": "Dominio no soportado o archivo inválido"},
        413: {"model": AdaptacionErrorResponseDTO, "description": "Archivo o documento demasiado grande"},
        415: {"model": AdaptacionErrorResponseDTO, "description": "Formato de archivo no soportado"},
        422: {"model": AdaptacionErrorResponseDTO, "description": "Formato pedagógico no adecuado o documento vacío"},
        500: {"model": AdaptacionErrorResponseDTO, "description": "Error interno del servidor"},
        503: {"model": AdaptacionErrorResponseDTO, "description": "Proveedor de IA no disponible"},
    },
    tags=["Adaptación Pedagógica"],
)
def adaptar_contenido_stream(
    documento_original: Annotated[
        UploadFile,
        File(
            description="Documento original PDF (.pdf), Markdown (.md) o Texto (.txt).",
            json_schema_extra={"format": "binary"},
        ),
    ],
    perfil_destinatario: Annotated[
        PerfilDestinatarioEnum,
        Form(description="Perfil de destinatario: Junior, Senior, Ejecutivo."),
    ] = PerfilDestinatarioEnum.JUNIOR,
    formato_salida: Annotated[
        FormatoSalidaEnum,
        Form(description="Formato educativo: Flashcards, Quiz Interactivo, Mapa Mental, Guia Paso a Paso, Resumen Ejecutivo."),
    ] = FormatoSalidaEnum.FLASHCARDS,
    nicho_sector: Annotated[
        NichoSectorEnum,
        Form(description="Nicho o sector: TI, Fintech, Salud, Marketing digital, General."),
    ] = NichoSectorEnum.GENERAL,
    nivel_detalle: Annotated[
        NivelDetalleEnum,
        Form(description="Nivel de profundidad didáctica: Didactico, Tecnico Intermedio, Exhaustivo."),
    ] = NivelDetalleEnum.DIDACTICO,
    documento_titulo: Annotated[
        Optional[str],
        Form(description="Título personalizado del documento (opcional)."),
    ] = None,
    oci_storage: Annotated[
        Optional[OCIStorage],
        Depends(get_oci_storage),
    ] = None,
):
    """
    Endpoint de streaming SSE para adaptación de contenidos educativos (BE-02).
    Emite eventos de telemetría de las 5 etapas en tiempo real hacia el cliente frontend.
    """
    filename, content, error_resp = _validar_archivo_upload(documento_original)
    if error_resp is not None:
        return error_resp

    stream_generator = procesar_adaptacion_stream(
        file_bytes=content,
        filename=filename,
        perfil=perfil_destinatario,
        formato=formato_salida,
        nicho=nicho_sector,
        nivel_detalle=nivel_detalle,
        documento_titulo=documento_titulo,
        oci_storage=oci_storage,
    )

    return StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
