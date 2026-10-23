"""
Contratos de datos Pydantic V2 para NuevaMente AI Core.
Define de forma estricta los tipos de entrada, salida y estructuras intermedias.
"""

from enum import Enum
import re
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class PerfilDestinatarioEnum(str, Enum):
    JUNIOR = "Junior"
    SENIOR = "Senior"
    EJECUTIVO = "Ejecutivo"


class FormatoSalidaEnum(str, Enum):
    FLASHCARDS = "Flashcards"
    QUIZ_INTERACTIVO = "Quiz Interactivo"
    MAPA_MENTAL = "Mapa Mental"
    GUIA_PASO_A_PASO = "Guia Paso a Paso"
    RESUMEN_EJECUTIVO = "Resumen Ejecutivo"


class NichoSectorEnum(str, Enum):
    FINTECH = "Fintech"
    SALUD = "Salud"
    ECOMMERCE = "E-commerce"
    GENERAL = "General"


class NivelDetalleEnum(str, Enum):
    DIDACTICO = "Didactico"
    TECNICO_INTERMEDIO = "Tecnico Intermedio"
    EXHAUSTIVO = "Exhaustivo"


class FaseProgresoEnum(str, Enum):
    EXTRACCION = "EXTRACCION"
    INDEXACION = "INDEXACION"
    GENERACION = "GENERACION"
    AUDITORIA = "AUDITORIA"
    PERSISTENCIA = "PERSISTENCIA"
    COMPLETADO = "COMPLETADO"
    ERROR = "ERROR"


# Modelos específicos por formato didáctico
class FlashcardItem(BaseModel):
    frente: str = Field(..., description="Concepto, término o pregunta concisa")
    dorso: str = Field(..., description="Explicación pedagógica, definición o respuesta")
    pista_didactica: Optional[str] = Field(None, description="Analogía o mnemotecnia de apoyo")
    categoria_dificultad: Optional[str] = Field("Intermedio", description="Básico, Intermedio o Avanzado")


class QuizItem(BaseModel):
    pregunta: str = Field(..., description="Pregunta de evaluación conceptual")
    opciones: List[str] = Field(..., min_length=4, max_length=4, description="Exactamente 4 alternativas")
    indice_correcto: int = Field(..., ge=0, le=3, description="Índice de la respuesta correcta (0-3)")
    justificacion_tecnica: str = Field(..., description="Explicación técnica del porqué la respuesta es correcta")
    pista_didactica: Optional[str] = Field(None, description="Pista para orientar al estudiante")
    explicacion_distractores: Optional[str] = Field(None, description="Por qué las otras 3 opciones son erróneas")


class NodoMapaMental(BaseModel):
    id: str = Field(..., description="Identificador único del nodo")
    etiqueta: str = Field(..., description="Texto del concepto")
    subnodos: List["NodoMapaMental"] = Field(default_factory=list, description="Ramas secundarias")


class MapaMentalItem(BaseModel):
    nodo_central: str = Field(..., description="Concepto núcleo")
    descripcion_general: str = Field(..., description="Breve síntesis del mapa")
    arbol: List[NodoMapaMental] = Field(default_factory=list, description="Estructura arbórea de conceptos")
    codigo_mermaid: Optional[str] = Field(None, description="Sintaxis mindmap formal en Mermaid.js")


class PasoTutorialItem(BaseModel):
    numero_paso: int = Field(..., ge=1)
    titulo_paso: str
    instrucciones: str
    bloque_codigo: Optional[str] = None
    resultado_esperado: Optional[str] = None


class TutorialItem(BaseModel):
    prerrequisitos: List[str] = Field(default_factory=list)
    pasos: List[PasoTutorialItem] = Field(default_factory=list)
    resumen_cierre: str


class ResumenEjecutivoItem(BaseModel):
    tldr: str = Field(..., description="Resumen ultra conciso en un párrafo")
    puntos_clave: List[str] = Field(default_factory=list, description="Puntos de alto impacto")
    impacto_negocio: str = Field(..., description="Beneficios operativos y comerciales")
    recomendaciones: List[str] = Field(default_factory=list, description="Acciones de implementación")


class MetadatosAprendizaje(BaseModel):
    perfil_aplicado: PerfilDestinatarioEnum
    formato_generado: FormatoSalidaEnum
    tiempo_estimado_estudio_minutos: int = Field(..., ge=1, le=180)
    conceptos_clave: List[str] = Field(..., min_length=1)
    nicho_contexto: NichoSectorEnum = Field(default=NichoSectorEnum.GENERAL)


class EvaluacionCalidad(BaseModel):
    anclaje_fuente_score: float = Field(..., ge=0.0, le=1.0, description="Métrica de fidelidad fáctica")
    claridad_pedagogica: str = Field("Alta", description="Evaluación cualitativa")
    observaciones: Optional[str] = Field(None, description="Dictamen del Agente Crítico")
    reintentos_realizados: int = Field(default=0, ge=0)


class AlmacenamientoOCI(BaseModel):
    bucket: str = Field(default="nuevamente-contenidos-educativos")
    objeto_id: str
    status_upload: str = Field(default="pendiente")
    ruta_publica_o_par: Optional[str] = None


class PaqueteContenidoAdaptado(BaseModel):
    titulo: str = Field(..., description="Título del material generado")
    introduccion_contextualizada: str = Field(..., description="Introducción adaptada al perfil")
    items: Union[
        List[FlashcardItem],
        List[QuizItem],
        MapaMentalItem,
        TutorialItem,
        ResumenEjecutivoItem,
        Dict[str, Any]
    ]


class AdaptacionContenidoRequest(BaseModel):
    documento_titulo: str = Field(..., min_length=3, max_length=150, pattern=r"^[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ\s\-\.,_]+$")
    documento_contenido: str = Field(..., min_length=20, max_length=50000)
    perfil_destinatario: PerfilDestinatarioEnum = Field(default=PerfilDestinatarioEnum.JUNIOR)
    formato_salida: FormatoSalidaEnum = Field(default=FormatoSalidaEnum.FLASHCARDS)
    nicho_sector: NichoSectorEnum = Field(default=NichoSectorEnum.GENERAL)
    nivel_detalle: NivelDetalleEnum = Field(default=NivelDetalleEnum.DIDACTICO)

    @field_validator('documento_contenido', 'documento_titulo')
    @classmethod
    def sanitizar_entradas(cls, v: str) -> str:
        # Detectar XSS o inyecciones de código comunes con regex estricto
        if re.search(r'<script.*?>', v, re.IGNORECASE):
            raise ValueError("Contenido bloqueado: etiquetas script (XSS) detectadas.")
        
        # Eliminar caracteres de control no imprimibles (bypass filtering)
        v = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', v)

        # Detectar intentos comunes de Prompt Injection
        patrones_prohibidos = [
            r"ignore\s+(all\s+)?(previous\s+)?instructions",
            r"ignora\s+(todas\s+)?(las\s+)?instrucciones",
            r"system\s+prompt",
            r"olvida\s+lo\s+anterior"
        ]
        for patron in patrones_prohibidos:
            if re.search(patron, v, re.IGNORECASE):
                raise ValueError("Contenido bloqueado: posible intento de Prompt Injection detectado.")
        
        return v


class AdaptacionContenidoResponse(BaseModel):
    status: str = Field(default="exito")
    metadatos: MetadatosAprendizaje
    contenido_adaptado: PaqueteContenidoAdaptado


class TelemetriaEstadoResponse(BaseModel):
    fase_actual: FaseProgresoEnum
    fase_numero: int = Field(..., ge=1, le=5)
    porcentaje_progreso: int = Field(..., ge=0, le=100)
    mensaje_descriptivo: str
    tiempo_transcurrido_segundos: float = Field(default=0.0)
    error_detalle: Optional[str] = Field(default=None)
