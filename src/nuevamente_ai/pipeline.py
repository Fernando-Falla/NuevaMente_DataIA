"""
Punto de entrada público del pipeline de IA para NuevaMente.
Orquesta Ingesta -> Segmentación -> Vector Store -> Selección de contexto -> LangGraph -> Paquete Validado.
"""

import inspect
import logging
import os
from typing import Any, Dict, Optional

from nuevamente_ai.contexto import seleccionar_contexto, verificar_pertinencia_formato
from nuevamente_ai.graph import grafo_adaptacion_compilado
from nuevamente_ai.schemas import AdaptacionContenidoResponse
from dataia.common.providers import EMBEDDING_LIMITER, call_provider

logger = logging.getLogger(__name__)


def _ingestar(ruta_archivo: Optional[str], documento_contenido: Optional[str]):
    if ruta_archivo:
        from dataia.ingestion.service import ingest_document
        ingestion_res = ingest_document(ruta_archivo)
        if not getattr(ingestion_res, "status", None) == "aprobado":
            raise ValueError(f"Error de Ingestión: {getattr(ingestion_res, 'mensaje', 'Desconocido')}")
        return ingestion_res
    if documento_contenido:
        raise ValueError("El nuevo pipeline DataIA requiere una ruta de archivo (ruta_archivo) para operar.")
    raise ValueError("Debe proporcionar 'ruta_archivo'.")


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
        raise ValueError(f"Formato No Adecuado (Error 422): {rechazo}")

    metadata = ingestion_res.pedagogical_metadata
    conceptos = list(getattr(metadata, "conceptos_clave", None) or [])
    seleccion = seleccionar_contexto(chunks, formato, _similitud_con_conceptos(document_id, conceptos, len(chunks)))
    logger.info("Contexto IA-05: %d de %d chunks para formato %s", len(seleccion), len(chunks), formato)

    return {
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
        raise ValueError(f"Contexto Insuficiente (Error 422): El documento carece de información relevante (Score: {score} vs Umbral {umbral}).")
    paquete_json = estado_final.get("paquete_final_json")
    if not paquete_json:
        raise RuntimeError("El grafo finalizó sin producir un paquete JSON válido.")
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

    import asyncio
    from nuevamente_ai.agents.auditor import AuditorAgent
    is_secure, vulns, recs = asyncio.run(AuditorAgent().auditar_seguridad_async(paquete_json))
    _registrar_auditoria(is_secure, vulns, recs)

    notificar("COMPLETADO", 5, 100, f"Contenido generado y auditado (Seguro: {is_secure}).")
    return AdaptacionContenidoResponse(**paquete_json)


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
    return AdaptacionContenidoResponse(**paquete_json)
