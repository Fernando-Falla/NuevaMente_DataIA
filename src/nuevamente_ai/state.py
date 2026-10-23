"""
Definición del estado del grafo de LangGraph para NuevaMente.
"""

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
import operator


class EstadoPipelineAdaptacion(TypedDict):
    # Entradas originales
    documento_titulo: str
    documento_contenido: str
    perfil_destinatario: str
    formato_salida: str
    nicho_sector: str
    nivel_detalle: str

    # Contexto intermedio generado por agentes
    fragmentos_relevantes: List[Dict[str, Any]]
    conceptos_clave: List[str]
    prompt_sistema_calibrado: str
    tiempo_estimado_minutos: int

    # Borradores y refinamientos
    borrador_contenido: Optional[Dict[str, Any]]
    codigo_mermaid: Optional[str]

    # Auditoría del Agente Crítico
    anclaje_fuente_score: float
    critica_observaciones: Optional[str]
    contador_intentos: int

    # Salida final empaquetada
    paquete_final_json: Optional[Dict[str, Any]]
    status: str
    error: Optional[str]
