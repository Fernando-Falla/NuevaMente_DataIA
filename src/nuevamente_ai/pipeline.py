"""
Punto de entrada público del pipeline de IA para NuevaMente.
Orquesta Ingesta -> Segmentación -> Vector Store -> LangGraph -> Paquete Validado.
"""

from typing import Any, Dict, List, Optional

from nuevamente_ai.graph import grafo_adaptacion_compilado
from nuevamente_ai.schemas import AdaptacionContenidoResponse
from dataia.common.providers import EMBEDDING_LIMITER, call_provider


def _construir_query_pedagogica(titulo: str, formato: str) -> str:
    """Traduce el formato pedagógico solicitado en un vector de búsqueda optimizado para RAG."""
    fmt = formato.lower()
    if "flashcards" in fmt:
        return f"Definiciones, conceptos clave, glosario y terminología de {titulo}"
    elif "quiz" in fmt:
        return f"Afirmaciones verificables, datos técnicos, buenas prácticas y reglas de {titulo}"
    elif "guion" in fmt or "tutorial" in fmt:
        return f"Ejemplos prácticos, instrucciones paso a paso, fundamentos y aplicación de {titulo}"
    elif "resumen" in fmt or "tldr" in fmt:
        return f"Resumen ejecutivo, impacto de negocio, ventajas y visión general de {titulo}"
    return f"Conceptos principales, definiciones y reglas de {titulo}"


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
    # 1. Fase de Extracción
    if callback_telemetria:
        callback_telemetria("EXTRACCION", 1, 20, "Extrayendo y normalizando texto del documento...")

    if ruta_archivo:
        from dataia.ingestion.service import ingest_document
        ingestion_res = ingest_document(ruta_archivo)
        if not getattr(ingestion_res, "status", None) == "aprobado":
            raise ValueError(f"Error de Ingestión: {getattr(ingestion_res, 'mensaje', 'Desconocido')}")
    elif documento_contenido:
        raise ValueError("El nuevo pipeline DataIA requiere una ruta de archivo (ruta_archivo) para operar.")
    else:
        raise ValueError("Debe proporcionar 'ruta_archivo'.")

    # 2. Fase de Chunking e Indexación Vectorial
    if callback_telemetria:
        callback_telemetria("INDEXACION", 2, 40, "Segmentando fragmentos jerárquicos y calculando embeddings...")

    from dataia.chunking.service import process_chunks
    chunking_res = process_chunks(ingestion_res)
    if not getattr(chunking_res, "status", None) == "aprobado":
        raise ValueError(f"Error de Chunking: {getattr(chunking_res, 'mensaje', 'Desconocido')}")

    from dataia.vectorstore.service import process_vectorstore
    from dataia.vectorstore.client import get_vector_store
    
    vs_res = process_vectorstore(chunking_res)
    if not getattr(vs_res, "status", None) == "aprobado":
        raise ValueError(f"Error de VectorStore: {getattr(vs_res, 'mensaje', 'Desconocido')}")

    query_pedagogica = _construir_query_pedagogica(documento_titulo, formato)
    vectorstore = get_vector_store()
    
    docs_relevantes = call_provider(
        "RECUPERACION_FRAGMENTOS",
        lambda: vectorstore.similarity_search(query=query_pedagogica, k=15, filter={"document_id": vs_res.document_id}),
        limiter=EMBEDDING_LIMITER,
    )
    
    fragmentos_relevantes = [{"contenido": d.page_content, "metadatos": d.metadata} for d in docs_relevantes]
    texto_completo = " ".join([d.page_content for d in docs_relevantes])

    # 3. Fase de LangGraph (Generación y Crítica)
    if callback_telemetria:
        callback_telemetria("GENERACION", 3, 60, f"LangGraph generando contenido para perfil '{perfil}'...")

    estado_inicial = {
        "documento_titulo": documento_titulo,
        "documento_contenido": texto_completo,
        "perfil_destinatario": perfil,
        "formato_salida": formato,
        "nicho_sector": nicho,
        "dominio_documento": getattr(ingestion_res.pedagogical_metadata, "dominio", None) or "General",
        "nivel_detalle": nivel_detalle,
        "fragmentos_relevantes": fragmentos_relevantes,
        "conceptos_clave": [],
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

    # Ejecutar grafo
    estado_final = grafo_adaptacion_compilado.invoke(estado_inicial)

    # 4. Fase de Auditoría y Crítica
    score = estado_final.get("anclaje_fuente_score", 0.95)
    import os
    umbral_base = float(os.getenv("UMBRAL_ANCLAJE_MINIMO", 0.85))
    umbral = 0.75 if "Quiz" in formato else umbral_base
    if score < umbral:
        raise ValueError(f"Contexto Insuficiente (Error 422): El documento carece de información relevante (Score: {score} vs Umbral {umbral}).")
        
    if callback_telemetria:
        callback_telemetria(
            "AUDITORIA",
            4,
            80,
            f"Agente Crítico: Fidelidad evaluada ({score}). Iniciando Auditoría heurística..."
        )

    # 5. Retorno tipado Pydantic y Auditoría Heurística
    paquete_json = estado_final.get("paquete_final_json")
    if not paquete_json:
        raise RuntimeError("El grafo finalizó sin producir un paquete JSON válido.")

    from nuevamente_ai.agents.auditor import AuditorAgent
    import asyncio
    import logging
    
    auditor = AuditorAgent()
    is_secure, vulns, recs = asyncio.run(auditor.auditar_seguridad_async(paquete_json))
    
    if not is_secure:
        logging.getLogger(__name__).warning(f"Auditoría Hermes detectó problemas: {vulns}. Recomendaciones: {recs}")

    if callback_telemetria:
        callback_telemetria("COMPLETADO", 5, 100, f"Contenido generado y auditado (Seguro: {is_secure}).")

    return AdaptacionContenidoResponse(**paquete_json)


async def _invocar_callback_async(callback: Optional[Any], etapa: str, paso: int, progreso: int, mensaje: str) -> None:
    """Invoca el callback de telemetría soportando tanto funciones síncronas como asíncronas."""
    if not callback:
        return
    import inspect
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
    # 1. Fase de Extracción
    await _invocar_callback_async(callback_telemetria, "EXTRACCION", 1, 20, "Extrayendo y normalizando texto del documento...")

    if ruta_archivo:
        from dataia.ingestion.service import ingest_document
        ingestion_res = ingest_document(ruta_archivo)
        if not getattr(ingestion_res, "status", None) == "aprobado":
            raise ValueError(f"Error de Ingestión: {getattr(ingestion_res, 'mensaje', 'Desconocido')}")
    elif documento_contenido:
        raise ValueError("El nuevo pipeline DataIA requiere una ruta de archivo (ruta_archivo) para operar.")
    else:
        raise ValueError("Debe proporcionar 'ruta_archivo'.")

    # 2. Fase de Chunking e Indexación Vectorial
    await _invocar_callback_async(callback_telemetria, "INDEXACION", 2, 40, "Segmentando fragmentos jerárquicos y calculando embeddings...")

    from dataia.chunking.service import process_chunks
    chunking_res = process_chunks(ingestion_res)
    if not getattr(chunking_res, "status", None) == "aprobado":
        raise ValueError(f"Error de Chunking: {getattr(chunking_res, 'mensaje', 'Desconocido')}")

    from dataia.vectorstore.service import process_vectorstore
    from dataia.vectorstore.client import get_vector_store
    
    vs_res = process_vectorstore(chunking_res)
    if not getattr(vs_res, "status", None) == "aprobado":
        raise ValueError(f"Error de VectorStore: {getattr(vs_res, 'mensaje', 'Desconocido')}")

    query_pedagogica = _construir_query_pedagogica(documento_titulo, formato)
    vectorstore = get_vector_store()
    
    docs_relevantes = call_provider(
        "RECUPERACION_FRAGMENTOS",
        lambda: vectorstore.similarity_search(query=query_pedagogica, k=15, filter={"document_id": vs_res.document_id}),
        limiter=EMBEDDING_LIMITER,
    )
    
    fragmentos_relevantes = [{"contenido": d.page_content, "metadatos": d.metadata} for d in docs_relevantes]
    texto_completo = " ".join([d.page_content for d in docs_relevantes])

    # 3. Fase de LangGraph Asíncrono
    await _invocar_callback_async(callback_telemetria, "GENERACION", 3, 60, f"LangGraph generando contenido para perfil '{perfil}'...")

    estado_inicial = {
        "documento_titulo": documento_titulo,
        "documento_contenido": texto_completo,
        "perfil_destinatario": perfil,
        "formato_salida": formato,
        "nicho_sector": nicho,
        "dominio_documento": getattr(ingestion_res.pedagogical_metadata, "dominio", None) or "General",
        "nivel_detalle": nivel_detalle,
        "fragmentos_relevantes": fragmentos_relevantes,
        "conceptos_clave": [],
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

    # Invocación asíncrona no bloqueante
    estado_final = await grafo_adaptacion_compilado.ainvoke(estado_inicial)

    # 4. Fase de Auditoría y Crítica
    score = estado_final.get("anclaje_fuente_score", 0.95)
    
    import os
    umbral_base = float(os.getenv("UMBRAL_ANCLAJE_MINIMO", 0.85))
    umbral = 0.75 if "Quiz" in formato else umbral_base
    if score < umbral:
        raise ValueError(f"Contexto Insuficiente (Error 422): El documento carece de información relevante (Score: {score} vs Umbral {umbral}).")
        
    await _invocar_callback_async(callback_telemetria, "AUDITORIA", 4, 80, f"Agente Crítico: Fidelidad evaluada ({score}). Iniciando Auditoría heurística...")

    paquete_json = estado_final.get("paquete_final_json")
    if not paquete_json:
        raise RuntimeError("El grafo finalizó sin producir un paquete JSON válido.")

    from nuevamente_ai.agents.auditor import AuditorAgent
    auditor = AuditorAgent()
    is_secure, vulns, recs = await auditor.auditar_seguridad_async(paquete_json)
    
    # Agregar resultados de auditoría al paquete o log
    if not is_secure:
        # Aquí se podría decidir abortar o simplemente registrar el fallo (fail-open vs fail-closed)
        import logging
        logging.getLogger(__name__).warning(f"Auditoría Hermes detectó problemas: {vulns}. Recomendaciones: {recs}")
        
    await _invocar_callback_async(callback_telemetria, "COMPLETADO", 5, 100, f"Contenido generado y auditado (Seguro: {is_secure}).")

    return AdaptacionContenidoResponse(**paquete_json)

