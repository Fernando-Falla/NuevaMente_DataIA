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
    """Sector al que se adaptan ejemplos y analogías (spec IA-02c R4)."""
    TI = "TI"
    FINTECH = "Fintech"
    SALUD = "Salud"
    MARKETING_DIGITAL = "Marketing digital"
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
    resumen_ejecutivo: Optional[str] = Field(None, description="Síntesis pedagógica del documento")


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
    documento_original_objeto_id: Optional[str] = None
    documento_original_subido: Optional[bool] = None
    codigo_error: Optional[str] = None
    mensaje: Optional[str] = None


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


# --- Esquemas de generación: uno por formato (spec IA-06 R6) ---
# El generador recibe solo el del formato pedido; la respuesta conserva la forma
# de PaqueteContenidoAdaptado.

class _PaqueteBase(BaseModel):
    titulo: str = Field(..., description="Título del material generado")
    introduccion_contextualizada: str = Field(..., description="Introducción adaptada al perfil y al nicho")


class PaqueteFlashcards(_PaqueteBase):
    items: List[FlashcardItem] = Field(..., description="Entre 4 y 8 tarjetas")


class PaqueteQuiz(_PaqueteBase):
    items: List[QuizItem] = Field(..., description="Entre 3 y 5 preguntas")


class PaqueteResumen(_PaqueteBase):
    items: ResumenEjecutivoItem


class PaqueteGuia(_PaqueteBase):
    items: TutorialItem


class SubtemaMapa(BaseModel):
    etiqueta: str = Field(..., description="Subtema concreto del documento, en pocas palabras")
    detalles: List[str] = Field(default_factory=list, description="0 a 3 detalles breves del subtema")


class RamaMapa(BaseModel):
    etiqueta: str = Field(..., description="Idea principal del documento, en pocas palabras")
    subtemas: List[SubtemaMapa] = Field(..., description="Entre 2 y 5 subtemas")


class MapaMentalGenerado(BaseModel):
    """Mapa sin recursión (spec IA-06 R7): el código arma el árbol con ids y el Mermaid."""
    nodo_central: str = Field(..., description="Tema central del documento")
    descripcion_general: str = Field(..., description="Síntesis breve del alcance del mapa")
    ramas: List[RamaMapa] = Field(..., description="Entre 3 y 6 ramas principales")


class PaqueteMapaMental(_PaqueteBase):
    items: MapaMentalGenerado


ESQUEMA_GENERACION_POR_FORMATO = {
    FormatoSalidaEnum.FLASHCARDS.value: PaqueteFlashcards,
    FormatoSalidaEnum.QUIZ_INTERACTIVO.value: PaqueteQuiz,
    FormatoSalidaEnum.RESUMEN_EJECUTIVO.value: PaqueteResumen,
    FormatoSalidaEnum.GUIA_PASO_A_PASO.value: PaqueteGuia,
    FormatoSalidaEnum.MAPA_MENTAL.value: PaqueteMapaMental,
}


class CodigoErrorEnum(str, Enum):
    """Catálogo canónico de errores para integración con Backend (spec IA-08 R4)."""
    DOMINIO_NO_SOPORTADO = "DOMINIO_NO_SOPORTADO"
    ARCHIVO_INVALIDO = "ARCHIVO_INVALIDO"
    ARCHIVO_DEMASIADO_GRANDE = "ARCHIVO_DEMASIADO_GRANDE"
    DOCUMENTO_DEMASIADO_EXTENSO = "DOCUMENTO_DEMASIADO_EXTENSO"
    FORMATO_NO_ADECUADO = "FORMATO_NO_ADECUADO"
    FIDELIDAD_INSUFICIENTE = "FIDELIDAD_INSUFICIENTE"
    ERROR_PROVEEDOR_LLM = "ERROR_PROVEEDOR_LLM"
    ERROR_INTERNO = "ERROR_INTERNO"


class DocumentoMetadataResumen(BaseModel):
    document_id: str = Field(..., description="Identificador único del documento en el almacén vectorial")
    titulo: str = Field(..., description="Título del documento")
    dominio: Optional[str] = Field("General", description="Dominio clasificado (TI, Fintech, Salud, Marketing digital, etc.)")


class ChunkTrazabilidad(BaseModel):
    chunk_id: str = Field(..., description="Identificador del fragmento utilizado")
    seccion: Optional[str] = Field(None, description="Sección o título donde se ubica el chunk")
    pagina_inicio: Optional[int] = Field(None, description="Página de inicio en el documento original")
    pagina_fin: Optional[int] = Field(None, description="Página de término en el documento original")
    tipo_contenido: Optional[str] = Field(None, description="Clasificación del tipo de contenido (definicion, afirmacion, etc.)")


class TrazabilidadContexto(BaseModel):
    chunks_utilizados: List[ChunkTrazabilidad] = Field(default_factory=list, description="Fragmentos seleccionados para el contexto RAG")
    total_chunks_documento: int = Field(default=0, description="Total de fragmentos indexados del documento")
    total_chunks_contexto: int = Field(default=0, description="Cantidad de fragmentos incluidos dentro del presupuesto")


class AuditoriaSeguridadReporte(BaseModel):
    es_seguro: bool = Field(default=True, description="Indica si superó los controles de seguridad y sanitización")
    vulnerabilidades: List[str] = Field(default_factory=list, description="Vulnerabilidades o sospechas detectadas")
    recomendaciones: List[str] = Field(default_factory=list, description="Recomendaciones de corrección")


class ValidacionReporte(BaseModel):
    anclaje_fuente_score: float = Field(..., ge=0.0, le=1.0, description="Puntaje de fidelidad fáctica del crítico")
    aprobado: bool = Field(default=True, description="Indica si supera el umbral de fidelidad")
    reintentos_realizados: int = Field(default=0, ge=0, description="Cantidad de reintentos de generación")
    auditoria_seguridad: AuditoriaSeguridadReporte = Field(default_factory=AuditoriaSeguridadReporte)


class AdaptacionErrorResponseDTO(BaseModel):
    status: str = Field(default="error")
    codigo_error: CodigoErrorEnum = Field(..., description="Código canónico de error")
    http_status: int = Field(..., description="Código HTTP sugerido (400, 413, 422, 503, 500)")
    mensaje: str = Field(..., description="Mensaje explicativo para Backend y Frontend")
    detalle: Optional[Dict[str, Any]] = Field(default=None, description="Detalles técnicos o métricas complementarias")
    sugerencia: Optional[str] = Field(None, description="Recomendación de acción o formato alternativo")


class AdaptacionContenidoRequest(BaseModel):
    documento_titulo: str = Field(..., min_length=3, max_length=150, pattern=r"^[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ\s\-\.,_]+$")
    documento_contenido: Optional[str] = Field(None, max_length=50000)
    ruta_archivo: Optional[str] = Field(None, description="Ruta local o temporal del archivo subido")
    document_id: Optional[str] = Field(None, description="ID del documento si ya está indexado en ChromaDB")
    perfil_destinatario: PerfilDestinatarioEnum = Field(default=PerfilDestinatarioEnum.JUNIOR)
    formato_salida: FormatoSalidaEnum = Field(default=FormatoSalidaEnum.FLASHCARDS)
    nicho_sector: NichoSectorEnum = Field(default=NichoSectorEnum.GENERAL)
    nivel_detalle: NivelDetalleEnum = Field(default=NivelDetalleEnum.DIDACTICO)

    @field_validator('documento_contenido', 'documento_titulo')
    @classmethod
    def sanitizar_entradas(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
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
    documento: Optional[DocumentoMetadataResumen] = Field(None, description="Identificación y dominio del documento")
    metadatos: MetadatosAprendizaje
    contenido_adaptado: PaqueteContenidoAdaptado
    trazabilidad: Optional[TrazabilidadContexto] = Field(None, description="Trazabilidad de fragmentos fuente utilizados")
    validacion: Optional[ValidacionReporte] = Field(None, description="Reporte de fidelidad y seguridad")
    almacenamiento_oci: Optional[AlmacenamientoOCI] = Field(None, description="Persistencia en almacenamiento OCI")


# Alias oficiales de contrato IA-08
AdaptacionRequestDTO = AdaptacionContenidoRequest
AdaptacionResponseDTO = AdaptacionContenidoResponse


class TelemetriaEstadoResponse(BaseModel):
    fase_actual: FaseProgresoEnum
    fase_numero: int = Field(..., ge=1, le=5)
    porcentaje_progreso: int = Field(..., ge=0, le=100)
    mensaje_descriptivo: str
    tiempo_transcurrido_segundos: float = Field(default=0.0)
    error_detalle: Optional[str] = Field(default=None)
