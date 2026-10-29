"""
Punto de entrada público del pipeline de IA para NuevaMente.
Orquesta Ingesta -> Segmentación -> Vector Store -> Selección de contexto -> LangGraph -> Paquete Validado.
"""

import inspect
import logging
import os
from typing import Any, Dict, Optional, Union

from nuevamente_ai.contexto import seleccionar_contexto, verificar_pertinencia_formato
from nuevamente_ai.graph import grafo_adaptacion_compilado
from nuevamente_ai.schemas import (
    AdaptacionContenidoResponse,
    AdaptacionResponseDTO,
    AdaptacionRequestDTO,
    AdaptacionErrorResponseDTO,
    CodigoErrorEnum,
    DocumentoMetadataResumen,
    ChunkTrazabilidad,
    TrazabilidadContexto,
    ValidacionReporte,
    AuditoriaSeguridadReporte,
)
from dataia.common.providers import EMBEDDING_LIMITER, call_provider

logger = logging.getLogger(__name__)


class ErrorPipelineIA(ValueError):
    """
    Excepción estructurada con código canónico de error (spec IA-08 R4).
    Hereda de ValueError para mantener compatibilidad con tests previos.
    """
    def __init__(
        self,
        codigo_error: CodigoErrorEnum,
        http_status: int,
        mensaje: str,
        detalle: Optional[Dict[str, Any]] = None,
        sugerencia: Optional[str] = None
    ):
        super().__init__(mensaje)
        self.codigo_error = codigo_error
        self.http_status = http_status
        self.mensaje = mensaje
        self.detalle = detalle or {}
        self.sugerencia = sugerencia

    def to_dto(self) -> AdaptacionErrorResponseDTO:
        return AdaptacionErrorResponseDTO(
            status="error",
            codigo_error=self.codigo_error,
            http_status=self.http_status,
            mensaje=self.mensaje,
            detalle=self.detalle,
            sugerencia=self.sugerencia
        )


def _ingestar(ruta_archivo: Optional[str], documento_contenido: Optional[str]):
    if ruta_archivo:
        from dataia.ingestion.service import ingest_document
        ingestion_res = ingest_document(ruta_archivo)
        if getattr(ingestion_res, "status", None) != "aprobado":
            codigo = getattr(ingestion_res, "codigo", "ARCHIVO_INVALIDO")
            mensaje = getattr(ingestion_res, "mensaje", "Error durante la ingestión del documento.")
            
            http_status = 400
            sugerencia = "Verifica que el archivo sea un documento técnico soportado."
            if codigo in ("ARCHIVO_DEMASIADO_GRANDE", "DOCUMENTO_DEMASIADO_EXTENSO"):
                http_status = 413
                sugerencia = "Reduce el tamaño del documento o selecciona un extracto más breve."
            elif codigo == "DOMINIO_NO_SOPORTADO":
                http_status = 400
                sugerencia = "NuevaMente solo procesa documentos técnicos de TI, Fintech, Salud o Marketing digital."
                
            cod_enum = getattr(CodigoErrorEnum, codigo, CodigoErrorEnum.ARCHIVO_INVALIDO)
            raise ErrorPipelineIA(
                codigo_error=cod_enum,
                http_status=http_status,
                mensaje=f"Error de Ingestión: {mensaje}",
                sugerencia=sugerencia
            )
        return ingestion_res
    if documento_contenido:
        raise ErrorPipelineIA(
            codigo_error=CodigoErrorEnum.ARCHIVO_INVALIDO,
            http_status=400,
            mensaje="El nuevo pipeline DataIA requiere una ruta de archivo (ruta_archivo) para operar.",
            sugerencia="Proporciona una ruta válida a un archivo .pdf, .md o .txt."
        )
    raise ErrorPipelineIA(
        codigo_error=CodigoErrorEnum.ARCHIVO_INVALIDO,
        http_status=400,
        mensaje="Debe proporcionar 'ruta_archivo'.",
        sugerencia="Envía un archivo para su procesamiento."
    )


def _indexar(ingestion_res) -> str:
    """Chunking, clasificación y vector store. Devuelve el document_id."""
    from dataia.chunking.service import process_chunks
    from dataia.vectorstore.service import process_vectorstore

    chunking_res = process_chunks(ingestion_res)
    if not getattr(chunking_res, "status", None) == "aprobado":
        raise ValueError(f"Error de Chunking: {getattr(chunking_res, 'mensaje', 'Desconocido')}")
    vs_res = process_vectorstore(chunking_res)
    if not getattr(vs_res, "status", None) == "aprobado":
        raise ValueError(f"Error de VectorStore: {getattr(vs_res, 'mensaje', 'Desconocido')}")
    return vs_res.document_id


def _similitud_con_conceptos(document_id: str, conceptos: list, total: int) -> Dict[str, float]:
    """Similitud de cada chunk con los conceptos clave del documento (desempate en IA-05 R3)."""
    if not conceptos:
        return {}
    from dataia.vectorstore.client import get_vector_store
    vectorstore = get_vector_store()
    # Distancia directa: la "relevancia" de Chroma supone vectores normalizados y con
    # embeddings locales da valores fuera de [0, 1]. Solo importa el orden.
    resultados = call_provider(
        "SIMILITUD_CONCEPTOS",
        lambda: vectorstore.similarity_search_with_score(" ; ".join(conceptos), k=total, filter={"document_id": document_id}),
        limiter=EMBEDDING_LIMITER,
    )
    return {doc.metadata.get("chunk_id", ""): -distancia for doc, distancia in resultados}


def _construir_estado(ingestion_res, document_id, documento_titulo, perfil, formato, nicho, nivel_detalle) -> Dict[str, Any]:
    """Selecciona el contexto (IA-05) y arma el estado inicial del grafo con la metadata del documento (IA-06 R5)."""
    from dataia.vectorstore.client import get_document_chunks

    chunks = get_document_chunks(document_id)
    rechazo = verificar_pertinencia_formato(formato, chunks)
    if rechazo:
        raise ErrorPipelineIA(
            codigo_error=CodigoErrorEnum.FORMATO_NO_ADECUADO,
            http_status=422,
            mensaje=f"Formato No Adecuado (Error 422): {rechazo}",
            sugerencia="Para este documento conceptual te sugerimos generar un Mapa Mental, Resumen Ejecutivo o Flashcards."
        )

    metadata = ingestion_res.pedagogical_metadata
    conceptos = list(getattr(metadata, "conceptos_clave", None) or [])
    seleccion = seleccionar_contexto(chunks, formato, _similitud_con_conceptos(document_id, conceptos, len(chunks)))
    logger.info("Contexto IA-05: %d de %d chunks para formato %s", len(seleccion), len(chunks), formato)

    return {
        "document_id": document_id,
        "total_chunks_documento": len(chunks),
        "documento_titulo": documento_titulo,
        "documento_contenido": " ".join(d.page_content for d in seleccion),
        "perfil_destinatario": perfil,
        "formato_salida": formato,
        "nicho_sector": nicho,
        "dominio_documento": getattr(metadata, "dominio", None) or "General",
        "nivel_detalle": nivel_detalle,
        "fragmentos_relevantes": [{"contenido": d.page_content, "metadatos": d.metadata} for d in seleccion],
        "conceptos_clave": conceptos,
        "metadata_documento": {
            "conceptos_clave": conceptos,
            "prerequisitos": list(getattr(metadata, "prerequisitos", None) or []),
            "resumen_ejecutivo": getattr(metadata, "resumen_ejecutivo", "") or "",
        },
        "prompt_sistema_calibrado": "",
        "tiempo_estimado_minutos": 5,
        "borrador_contenido": None,
        "codigo_mermaid": None,
        "anclaje_fuente_score": 0.0,
        "critica_observaciones": None,
        "contador_intentos": 0,
        "paquete_final_json": None,
        "status": "iniciando",
        "error": None
    }


def _validar_resultado(estado_final: Dict[str, Any], formato: str) -> Dict[str, Any]:
    score = estado_final.get("anclaje_fuente_score", 0.95)
    umbral_base = float(os.getenv("UMBRAL_ANCLAJE_MINIMO", 0.85))
    umbral = 0.75 if "Quiz" in formato else umbral_base
    if score < umbral:
        raise ErrorPipelineIA(
            codigo_error=CodigoErrorEnum.FIDELIDAD_INSUFICIENTE,
            http_status=422,
            mensaje=f"Contexto Insuficiente (Error 422): El documento carece de información relevante (Score: {score} vs Umbral {umbral}).",
            detalle={"score": score, "umbral": umbral},
            sugerencia="Intenta generar con otro perfil o verifica que el documento contenga suficiente contexto técnico."
        )
    paquete_json = estado_final.get("paquete_final_json")
    if not paquete_json:
        raise ErrorPipelineIA(
            codigo_error=CodigoErrorEnum.ERROR_INTERNO,
            http_status=500,
            mensaje="El grafo finalizó sin producir un paquete JSON válido."
        )
    return paquete_json


def _registrar_auditoria(is_secure: bool, vulns: list, recs: list) -> None:
    if not is_secure:
        logger.warning(f"Auditoría Hermes detectó problemas: {vulns}. Recomendaciones: {recs}")


def ejecutar_pipeline_adaptacion(
    documento_titulo: str,
    documento_contenido: Optional[str] = None,
    ruta_archivo: Optional[str] = None,
    perfil: str = "Junior",
    formato: str = "Flashcards",
    nicho: str = "General",
    nivel_detalle: str = "Didactico",
    callback_telemetria: Optional[Any] = None
) -> AdaptacionContenidoResponse:
    """
    Ejecuta el ciclo integral de adaptación pedagógica.
    Permite invocar tanto con texto plano en memoria como con ruta a archivo local (.pdf, .md, .txt).
    """
    def notificar(etapa, paso, progreso, mensaje):
        if callback_telemetria:
            callback_telemetria(etapa, paso, progreso, mensaje)

    notificar("EXTRACCION", 1, 20, "Extrayendo y normalizando texto del documento...")
    ingestion_res = _ingestar(ruta_archivo, documento_contenido)

    notificar("INDEXACION", 2, 40, "Segmentando fragmentos jerárquicos y calculando embeddings...")
    document_id = _indexar(ingestion_res)
    estado_inicial = _construir_estado(ingestion_res, document_id, documento_titulo, perfil, formato, nicho, nivel_detalle)

    notificar("GENERACION", 3, 60, f"LangGraph generando contenido para perfil '{perfil}'...")
    estado_final = grafo_adaptacion_compilado.invoke(estado_inicial)
    paquete_json = _validar_resultado(estado_final, formato)
    score = estado_final.get("anclaje_fuente_score")
    notificar("AUDITORIA", 4, 80, f"Agente Crítico: Fidelidad evaluada ({score}). Iniciando Auditoría heurística...")

    from nuevamente_ai.agents.auditor import AuditorAgent
    is_secure, vulns, recs = AuditorAgent().auditar_seguridad(paquete_json)
    _registrar_auditoria(is_secure, vulns, recs)

    notificar("COMPLETADO", 5, 100, f"Contenido generado y auditado (Seguro: {is_secure}).")
    respuesta = AdaptacionContenidoResponse(**paquete_json)
    if respuesta.validacion and respuesta.validacion.auditoria_seguridad:
        respuesta.validacion.auditoria_seguridad.es_seguro = is_secure
        respuesta.validacion.auditoria_seguridad.vulnerabilidades = vulns
        respuesta.validacion.auditoria_seguridad.recomendaciones = recs
    return respuesta


async def _invocar_callback_async(callback: Optional[Any], etapa: str, paso: int, progreso: int, mensaje: str) -> None:
    """Invoca el callback de telemetría soportando tanto funciones síncronas como asíncronas."""
    if not callback:
        return
    if inspect.iscoroutinefunction(callback):
        await callback(etapa, paso, progreso, mensaje)
    else:
        callback(etapa, paso, progreso, mensaje)


async def ejecutar_pipeline_adaptacion_async(
    documento_titulo: str,
    documento_contenido: Optional[str] = None,
    ruta_archivo: Optional[str] = None,
    perfil: str = "Junior",
    formato: str = "Flashcards",
    nicho: str = "General",
    nivel_detalle: str = "Didactico",
    callback_telemetria: Optional[Any] = None
) -> AdaptacionContenidoResponse:
    """
    Versión nativamente asíncrona para consumo no bloqueante en endpoints de FastAPI.
    Utiliza .ainvoke() sobre el StateGraph de LangGraph.
    """
    await _invocar_callback_async(callback_telemetria, "EXTRACCION", 1, 20, "Extrayendo y normalizando texto del documento...")
    ingestion_res = _ingestar(ruta_archivo, documento_contenido)

    await _invocar_callback_async(callback_telemetria, "INDEXACION", 2, 40, "Segmentando fragmentos jerárquicos y calculando embeddings...")
    document_id = _indexar(ingestion_res)
    estado_inicial = _construir_estado(ingestion_res, document_id, documento_titulo, perfil, formato, nicho, nivel_detalle)

    await _invocar_callback_async(callback_telemetria, "GENERACION", 3, 60, f"LangGraph generando contenido para perfil '{perfil}'...")
    estado_final = await grafo_adaptacion_compilado.ainvoke(estado_inicial)
    paquete_json = _validar_resultado(estado_final, formato)
    score = estado_final.get("anclaje_fuente_score")
    await _invocar_callback_async(callback_telemetria, "AUDITORIA", 4, 80, f"Agente Crítico: Fidelidad evaluada ({score}). Iniciando Auditoría heurística...")

    from nuevamente_ai.agents.auditor import AuditorAgent
    is_secure, vulns, recs = await AuditorAgent().auditar_seguridad_async(paquete_json)
    _registrar_auditoria(is_secure, vulns, recs)

    await _invocar_callback_async(callback_telemetria, "COMPLETADO", 5, 100, f"Contenido generado y auditado (Seguro: {is_secure}).")
    respuesta = AdaptacionContenidoResponse(**paquete_json)
    if respuesta.validacion and respuesta.validacion.auditoria_seguridad:
        respuesta.validacion.auditoria_seguridad.es_seguro = is_secure
        respuesta.validacion.auditoria_seguridad.vulnerabilidades = vulns
        respuesta.validacion.auditoria_seguridad.recomendaciones = recs
    return respuesta


def ejecutar_pipeline_adaptacion_controlado(
    documento_titulo: str,
    documento_contenido: Optional[str] = None,
    ruta_archivo: Optional[str] = None,
    perfil: str = "Junior",
    formato: str = "Flashcards",
    nicho: str = "General",
    nivel_detalle: str = "Didactico",
    callback_telemetria: Optional[Any] = None
) -> Union[AdaptacionContenidoResponse, AdaptacionErrorResponseDTO]:
    """
    Punto de entrada con manejo controlado de errores tipados para Backend (spec IA-08 R4).
    Captura validaciones y errores de negocio devolviendo AdaptacionErrorResponseDTO sin excepciones crudas.
    """
    try:
        return ejecutar_pipeline_adaptacion(
            documento_titulo=documento_titulo,
            documento_contenido=documento_contenido,
            ruta_archivo=ruta_archivo,
            perfil=perfil,
            formato=formato,
            nicho=nicho,
            nivel_detalle=nivel_detalle,
            callback_telemetria=callback_telemetria
        )
    except ErrorPipelineIA as err:
        logger.warning("Pipeline rechazado de forma controlada [%s]: %s", err.codigo_error.value, err.mensaje)
        return err.to_dto()
    except Exception as exc:
        logger.exception("Error inesperado en el pipeline: %s", exc)
        return AdaptacionErrorResponseDTO(
            status="error",
            codigo_error=CodigoErrorEnum.ERROR_INTERNO,
            http_status=500,
            mensaje=f"Error interno durante la ejecución del pipeline: {str(exc)}",
            sugerencia="Contacta al soporte o revisa los logs del servicio."
        )


def ejecutar_pipeline_dto(
    peticion: AdaptacionRequestDTO,
    callback_telemetria: Optional[Any] = None
) -> Union[AdaptacionResponseDTO, AdaptacionErrorResponseDTO]:
    """
    Recibe directamente el DTO validado de Pydantic y retorna el DTO de respuesta estructurada (spec IA-08).
    """
    return ejecutar_pipeline_adaptacion_controlado(
        documento_titulo=peticion.documento_titulo,
        documento_contenido=peticion.documento_contenido,
        ruta_archivo=peticion.ruta_archivo,
        perfil=peticion.perfil_destinatario.value,
        formato=peticion.formato_salida.value,
        nicho=peticion.nicho_sector.value,
        nivel_detalle=peticion.nivel_detalle.value,
        callback_telemetria=callback_telemetria
    )


def exportar_esquemas_json(directorio_destino: str) -> Dict[str, str]:
    """
    Exporta los JSON Schemas de los contratos IA-08 para integración con Backend/Frontend (CA4).
    """
    import json
    from pathlib import Path
    destino = Path(directorio_destino)
    destino.mkdir(parents=True, exist_ok=True)

    rutas = {}
    esquemas = {
        "schema_request.json": AdaptacionRequestDTO.model_json_schema(),
        "schema_response_success.json": AdaptacionResponseDTO.model_json_schema(),
        "schema_response_error.json": AdaptacionErrorResponseDTO.model_json_schema(),
    }
    for nombre, esquema in esquemas.items():
        archivo = destino / nombre
        archivo.write_text(json.dumps(esquema, indent=2, ensure_ascii=False), encoding="utf-8")
        rutas[nombre] = str(archivo)
    return rutas
