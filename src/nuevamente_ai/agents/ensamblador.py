"""
Nodo 4: Ensamblador y Formateador Final.
Construye y valida el objeto canónico AdaptacionContenidoResponse bajo los esquemas Pydantic V2.
"""

from typing import Any, Dict
from nuevamente_ai.state import EstadoPipelineAdaptacion
from nuevamente_ai.schemas import (
    AdaptacionContenidoResponse,
    MetadatosAprendizaje,
    PaqueteContenidoAdaptado,
    PerfilDestinatarioEnum,
    FormatoSalidaEnum,
    NichoSectorEnum,
    DocumentoMetadataResumen,
    ChunkTrazabilidad,
    TrazabilidadContexto,
    ValidacionReporte,
    AuditoriaSeguridadReporte,
)


def nodo_ensamblador(state: EstadoPipelineAdaptacion) -> Dict[str, Any]:
    """
    Construye la respuesta final normalizada lista para ser retornada a Backend / Frontend.
    """
    borrador = state.get("borrador_contenido", {})
    perfil_str = state.get("perfil_destinatario", "Junior")
    formato_str = state.get("formato_salida", "Flashcards")
    nicho_str = state.get("nicho_sector", "General")
    titulo_doc = state.get("documento_titulo", "Documento")

    # Mapear a enums de forma segura
    try:
        perfil_enum = PerfilDestinatarioEnum(perfil_str)
    except Exception:
        perfil_enum = PerfilDestinatarioEnum.JUNIOR

    try:
        formato_enum = FormatoSalidaEnum(formato_str)
    except Exception:
        formato_enum = FormatoSalidaEnum.FLASHCARDS

    try:
        nicho_enum = NichoSectorEnum(nicho_str)
    except Exception:
        nicho_enum = NichoSectorEnum.GENERAL

    items_raw = borrador.get("items", [])
    
    # F2: Cálculo matemático del tiempo estimado
    num_items = len(items_raw) if isinstance(items_raw, list) else 1
    if formato_enum == FormatoSalidaEnum.FLASHCARDS:
        tiempo_calculado = num_items * 3
    elif formato_enum == FormatoSalidaEnum.QUIZ_INTERACTIVO:
        tiempo_calculado = num_items * 5
    else:
        tiempo_calculado = 15

    # Construir modelos
    resumen = state.get("metadata_documento", {}).get("resumen_ejecutivo")
    metadatos = MetadatosAprendizaje(
        perfil_aplicado=perfil_enum,
        formato_generado=formato_enum,
        tiempo_estimado_estudio_minutos=state.get("tiempo_estimado_minutos", tiempo_calculado),
        conceptos_clave=state.get("conceptos_clave", [titulo_doc]),
        nicho_contexto=nicho_enum,
        resumen_ejecutivo=resumen
    )

    if formato_enum == FormatoSalidaEnum.MAPA_MENTAL and isinstance(items_raw, dict):
        from nuevamente_ai.utils.mermaid import sanitizar_codigo_mermaid
        nodo_central = items_raw.get("nodo_central", titulo_doc)
        arbol = items_raw.get("arbol", [])
        items_raw["codigo_mermaid"] = sanitizar_codigo_mermaid(
            codigo=items_raw.get("codigo_mermaid"),
            nodo_central=nodo_central,
            arbol=arbol
        )

    paquete_contenido = PaqueteContenidoAdaptado(
        titulo=borrador.get("titulo", f"{titulo_doc} para {perfil_enum.value}"),
        introduccion_contextualizada=borrador.get(
            "introduccion_contextualizada",
            f"Contenido estructurado para perfil {perfil_enum.value}."
        ),
        items=items_raw
    )

    # Trazabilidad y metadatos de integración (spec IA-08)
    doc_id = state.get("document_id") or "doc-local"
    dominio_doc = state.get("dominio_documento") or "General"
    documento_resumen = DocumentoMetadataResumen(
        document_id=doc_id,
        titulo=titulo_doc,
        dominio=dominio_doc
    )

    frags = state.get("fragmentos_relevantes", [])
    chunks_utilizados = []
    for f in frags:
        meta = f.get("metadatos", {}) if isinstance(f, dict) else getattr(f, "metadata", {})
        chunks_utilizados.append(
            ChunkTrazabilidad(
                chunk_id=meta.get("chunk_id", ""),
                seccion=meta.get("section"),
                pagina_inicio=meta.get("page"),
                pagina_fin=meta.get("page_end"),
                tipo_contenido=meta.get("tipo_contenido")
            )
        )
    trazabilidad = TrazabilidadContexto(
        chunks_utilizados=chunks_utilizados,
        total_chunks_documento=state.get("total_chunks_documento", len(chunks_utilizados)),
        total_chunks_contexto=len(chunks_utilizados)
    )

    score = state.get("anclaje_fuente_score", 0.95)
    intentos = max(0, state.get("contador_intentos", 1) - 1)
    validacion = ValidacionReporte(
        anclaje_fuente_score=score if score is not None else 0.95,
        aprobado=True,
        reintentos_realizados=intentos,
        auditoria_seguridad=AuditoriaSeguridadReporte(es_seguro=True)
    )

    respuesta = AdaptacionContenidoResponse(
        status="exito",
        documento=documento_resumen,
        metadatos=metadatos,
        contenido_adaptado=paquete_contenido,
        trazabilidad=trazabilidad,
        validacion=validacion
    )

    return {
        "paquete_final_json": respuesta.model_dump(),
        "status": "finalizado_exitosamente"
    }
