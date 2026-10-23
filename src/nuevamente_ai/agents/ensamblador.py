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
    NichoSectorEnum
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
    metadatos = MetadatosAprendizaje(
        perfil_aplicado=perfil_enum,
        formato_generado=formato_enum,
        tiempo_estimado_estudio_minutos=state.get("tiempo_estimado_minutos", tiempo_calculado),
        conceptos_clave=state.get("conceptos_clave", [titulo_doc]),
        nicho_contexto=nicho_enum
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

    respuesta = AdaptacionContenidoResponse(
        status="exito",
        metadatos=metadatos,
        contenido_adaptado=paquete_contenido
    )

    return {
        "paquete_final_json": respuesta.model_dump(),
        "status": "finalizado_exitosamente"
    }
