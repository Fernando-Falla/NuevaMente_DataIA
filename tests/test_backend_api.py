"""
Pruebas integrales del Backend FastAPI unificado (Tarea BE-01).
Verifica endpoints, validaciones de transporte multipart, ejecución de pipeline en proceso,
respuestas canónicas tipadas IA-08, rechazos controlados y persistencia OCI.
"""

import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.oci_service import OCIStorage, get_oci_storage
from nuevamente_ai.schemas import (
    AdaptacionErrorResponseDTO,
    AdaptacionResponseDTO,
    AlmacenamientoOCI,
    CodigoErrorEnum,
    DocumentoMetadataResumen,
    FlashcardItem,
    FormatoSalidaEnum,
    MetadatosAprendizaje,
    NichoSectorEnum,
    PaqueteContenidoAdaptado,
    PaqueteFlashcards,
    PaqueteGuia,
    PaqueteMapaMental,
    PaqueteQuiz,
    PaqueteResumen,
    PasoTutorialItem,
    PerfilDestinatarioEnum,
    QuizItem,
    ResumenEjecutivoItem,
    TutorialItem,
    ValidacionReporte,
)


@pytest.fixture
def client():
    """Cliente de pruebas para FastAPI."""
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_dummy_response(formato: str = "Flashcards") -> AdaptacionResponseDTO:
    """Genera una respuesta DTO canónica válida para pruebas de transporte."""
    if formato == "Flashcards":
        items = [
            FlashcardItem(
                frente="¿Qué es una API REST?",
                dorso="Un estilo de arquitectura para servicios web.",
                pista_didactica="Utiliza HTTP y métodos estándar.",
                categoria_dificultad="Intermedio",
            )
        ]
    elif formato == "Quiz Interactivo":
        items = [
            QuizItem(
                pregunta="¿Cuál método HTTP es idempotente?",
                opciones=["GET", "POST", "PATCH", "CONNECT"],
                indice_correcto=0,
                justificacion_tecnica="GET no modifica el estado del recurso.",
            )
        ]
    elif formato == "Resumen Ejecutivo":
        items = ResumenEjecutivoItem(
            tldr="Síntesis de arquitectura distribuida.",
            puntos_clave=["Desacoplamiento", "Escalabilidad horizontal"],
            impacto_negocio="Mejora la agilidad de despliegue continuo.",
            recomendaciones=["Adoptar API Gateway"],
        )
    elif formato == "Guia Paso a Paso":
        items = TutorialItem(
            prerrequisitos=["Docker instalado", "Python 3.12+"],
            pasos=[
                PasoTutorialItem(
                    numero_paso=1,
                    titulo_paso="Construir contenedor",
                    instrucciones="Ejecutar docker build .",
                )
            ],
            resumen_cierre="Contenedor listo para despliegue.",
        )
    elif formato == "Mapa Mental":
        items = {
            "nodo_central": "Arquitectura Cloud",
            "descripcion_general": "Visión de servicios cloud nativos.",
            "arbol": [],
            "codigo_mermaid": "mindmap\n  root((Cloud))",
        }
    else:
        items = []

    paquete = PaqueteContenidoAdaptado(
        titulo="Guía Didáctica de Microservicios",
        introduccion_contextualizada="Introducción pedagógica orientada al perfil Junior.",
        items=items,
    )

    return AdaptacionResponseDTO(
        status="exito",
        documento=DocumentoMetadataResumen(
            document_id="doc-test123456",
            titulo="Microservicios Modernos",
            dominio="TI",
        ),
        metadatos=MetadatosAprendizaje(
            perfil_aplicado=PerfilDestinatarioEnum.JUNIOR,
            formato_generado=getattr(FormatoSalidaEnum, formato.upper().replace(" ", "_"), FormatoSalidaEnum.FLASHCARDS),
            tiempo_estimado_estudio_minutos=15,
            conceptos_clave=["Microservicios", "Contenedores", "Docker"],
            nicho_contexto=NichoSectorEnum.TI,
        ),
        contenido_adaptado=paquete,
        validacion=ValidacionReporte(
            anclaje_fuente_score=0.96,
            aprobado=True,
            reintentos_realizados=0,
        ),
    )


# --- 1. Rutas generales ---

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "NuevaMente" in data["message"]


def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "nuevamente-backend"


# --- 2. Validaciones de Transporte (Archivos y Parámetros) ---

def test_adaptar_contenido_archivo_no_soportado(client):
    files = {"documento_original": ("documento.docx", b"Word content fake", "application/octet-stream")}
    data = {
        "perfil_destinatario": "Junior",
        "formato_salida": "Flashcards",
        "nicho_sector": "TI",
    }
    response = client.post("/api/v1/adaptar-contenido", files=files, data=data)
    assert response.status_code == 415
    body = response.json()
    assert body["status"] == "error"
    assert body["codigo_error"] == CodigoErrorEnum.ARCHIVO_INVALIDO.value
    assert "no soportado" in body["mensaje"].lower()


def test_adaptar_contenido_archivo_vacio(client):
    files = {"documento_original": ("documento.pdf", b"", "application/pdf")}
    data = {
        "perfil_destinatario": "Junior",
        "formato_salida": "Flashcards",
        "nicho_sector": "TI",
    }
    response = client.post("/api/v1/adaptar-contenido", files=files, data=data)
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["codigo_error"] == CodigoErrorEnum.ARCHIVO_INVALIDO.value
    assert "vacío" in body["mensaje"].lower()


def test_adaptar_contenido_archivo_demasiado_grande(client):
    with patch("backend.main.settings.MAX_DOCUMENT_BYTES", 50):
        files = {"documento_original": ("documento.txt", b"A" * 100, "text/plain")}
        data = {
            "perfil_destinatario": "Junior",
            "formato_salida": "Flashcards",
            "nicho_sector": "TI",
        }
        response = client.post("/api/v1/adaptar-contenido", files=files, data=data)
        assert response.status_code == 413
        body = response.json()
        assert body["status"] == "error"
        assert body["codigo_error"] == CodigoErrorEnum.ARCHIVO_DEMASIADO_GRANDE.value


def test_adaptar_contenido_parametro_enum_invalido(client):
    files = {"documento_original": ("documento.txt", b"Texto de prueba", "text/plain")}
    data = {
        "perfil_destinatario": "Astronauta",  # No válido
        "formato_salida": "Flashcards",
    }
    response = client.post("/api/v1/adaptar-contenido", files=files, data=data)
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["codigo_error"] == CodigoErrorEnum.ARCHIVO_INVALIDO.value


# --- 3. Procesamiento Exitoso de Formatos Canónicos ---

@pytest.mark.parametrize(
    "formato",
    [
        "Flashcards",
        "Quiz Interactivo",
        "Mapa Mental",
        "Guia Paso a Paso",
        "Resumen Ejecutivo",
    ],
)
def test_adaptar_contenido_formatos_exito(client, formato):
    fake_dto = make_dummy_response(formato)

    with patch("backend.main.procesar_adaptacion_directa", return_value=fake_dto) as mock_service:
        files = {"documento_original": ("doc_tecnico.md", b"# Arquitectura\nDetalles de microservicios.", "text/markdown")}
        data = {
            "perfil_destinatario": "Junior",
            "formato_salida": formato,
            "nicho_sector": "TI",
            "nivel_detalle": "Didactico",
            "documento_titulo": "Microservicios Test",
        }
        response = client.post("/api/v1/adaptar-contenido", files=files, data=data)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "exito"
        assert body["documento"]["document_id"] == "doc-test123456"
        assert body["metadatos"]["perfil_aplicado"] == "Junior"
        assert "contenido_adaptado" in body

        # Verificamos que el servicio fue invocado con los parámetros correctos
        mock_service.assert_called_once()
        _, kwargs = mock_service.call_args
        assert kwargs["filename"] == "doc_tecnico.md"
        assert kwargs["perfil"].value == "Junior"
        assert kwargs["formato"].value == formato
        assert kwargs["documento_titulo"] == "Microservicios Test"


# --- 4. Rechazos Controlados de Pipeline IA (IA-08) ---

def test_adaptar_contenido_rechazo_dominio_no_soportado(client):
    error_retornado = AdaptacionErrorResponseDTO(
        status="error",
        codigo_error=CodigoErrorEnum.DOMINIO_NO_SOPORTADO,
        http_status=400,
        mensaje="El documento trata sobre cocina y no pertenece a los dominios tecnológicos soportados.",
        sugerencia="Sube documentos técnicos de TI, Fintech, Salud o Marketing digital.",
    )

    with patch("backend.main.procesar_adaptacion_directa", return_value=error_retornado):
        files = {"documento_original": ("recetas.txt", b"Receta de pastel de manzana...", "text/plain")}
        data = {"perfil_destinatario": "Senior", "formato_salida": "Flashcards"}
        response = client.post("/api/v1/adaptar-contenido", files=files, data=data)
        assert response.status_code == 400
        body = response.json()
        assert body["status"] == "error"
        assert body["codigo_error"] == CodigoErrorEnum.DOMINIO_NO_SOPORTADO.value
        assert "cocina" in body["mensaje"].lower()


def test_adaptar_contenido_rechazo_formato_no_adecuado(client):
    error_retornado = AdaptacionErrorResponseDTO(
        status="error",
        codigo_error=CodigoErrorEnum.FORMATO_NO_ADECUADO,
        http_status=422,
        mensaje="El documento no contiene pasos procedimentales para una Guía Paso a Paso.",
        sugerencia="Te recomendamos un Mapa Mental o Resumen Ejecutivo.",
    )

    with patch("backend.main.procesar_adaptacion_directa", return_value=error_retornado):
        files = {"documento_original": ("teoria.md", b"# Teoria pura sin comandos...", "text/markdown")}
        data = {"perfil_destinatario": "Junior", "formato_salida": "Guia Paso a Paso"}
        response = client.post("/api/v1/adaptar-contenido", files=files, data=data)
        assert response.status_code == 422
        body = response.json()
        assert body["status"] == "error"
        assert body["codigo_error"] == CodigoErrorEnum.FORMATO_NO_ADECUADO.value


def test_adaptar_contenido_rechazo_fidelidad_insuficiente(client):
    error_retornado = AdaptacionErrorResponseDTO(
        status="error",
        codigo_error=CodigoErrorEnum.FIDELIDAD_INSUFICIENTE,
        http_status=422,
        mensaje="El Agente Crítico detectó anclaje insuficiente a la fuente.",
        detalle={"score": 0.65, "umbral": 0.85},
    )

    with patch("backend.main.procesar_adaptacion_directa", return_value=error_retornado):
        files = {"documento_original": ("resumen.pdf", b"%PDF-1.4...", "application/pdf")}
        data = {"perfil_destinatario": "Ejecutivo", "formato_salida": "Resumen Ejecutivo"}
        response = client.post("/api/v1/adaptar-contenido", files=files, data=data)
        assert response.status_code == 422
        body = response.json()
        assert body["codigo_error"] == CodigoErrorEnum.FIDELIDAD_INSUFICIENTE.value


# --- 5. Persistencia OCI Storage Integrada ---

def test_adaptar_contenido_con_oci_exitoso(client):
    fake_dto = make_dummy_response("Flashcards")
    mock_oci = MagicMock(spec=OCIStorage)

    def guardar_mock(data_bytes, filename, resultado):
        return resultado.model_copy(update={
            "almacenamiento_oci": AlmacenamientoOCI(
                bucket="nuevamente-test",
                objeto_id="artefactos/test.json",
                status_upload="subido",
                documento_original_objeto_id="fuente/test.pdf",
                documento_original_subido=True,
            )
        })

    mock_oci.guardar.side_effect = guardar_mock
    app.dependency_overrides[get_oci_storage] = lambda: mock_oci

    with patch("backend.main.procesar_adaptacion_directa", return_value=fake_dto):
        files = {"documento_original": ("doc.pdf", b"%PDF-1.4 contenido binario", "application/pdf")}
        data = {"perfil_destinatario": "Junior", "formato_salida": "Flashcards"}
        response = client.post("/api/v1/adaptar-contenido", files=files, data=data)

        assert response.status_code == 200
        body = response.json()
        assert body["almacenamiento_oci"]["status_upload"] == "subido"
        assert body["almacenamiento_oci"]["bucket"] == "nuevamente-test"
        mock_oci.guardar.assert_called_once()


# --- 6. Pruebas Unitarias de adaptacion_service ---

def test_sanitizar_titulo():
    from backend.services.adaptacion_service import sanitizar_titulo

    # Título explícito
    assert sanitizar_titulo("Mi Documento Especial", "cualquier.pdf") == "Mi Documento Especial"

    # Título extraído de filename
    assert sanitizar_titulo(None, "arquitectura_de_microservicios_v2.pdf") == "arquitectura de microservicios v2"

    # Filename con caracteres extraños
    assert sanitizar_titulo("", "doc%&$@!123.md") == "doc 123"

    # Filename extremadamente corto
    assert sanitizar_titulo("", "a.txt") == "Documento Tecnico de Estudio"


def test_procesar_adaptacion_directa_gestiona_archivo_temporal():
    from backend.services.adaptacion_service import procesar_adaptacion_directa

    archivo_recibido_en_pipeline = None

    def fake_pipeline_controlado(**kwargs):
        nonlocal archivo_recibido_en_pipeline
        archivo_recibido_en_pipeline = kwargs["ruta_archivo"]
        # Durante la llamada, el archivo temporal debe existir físicamente
        assert os.path.exists(archivo_recibido_en_pipeline)
        with open(archivo_recibido_en_pipeline, "rb") as f:
            assert f.read() == b"Contenido en memoria"
        return make_dummy_response("Flashcards")

    with patch(
        "backend.services.adaptacion_service.ejecutar_pipeline_adaptacion_controlado",
        side_effect=fake_pipeline_controlado,
    ):
        resultado = procesar_adaptacion_directa(
            file_bytes=b"Contenido en memoria",
            filename="archivo_test.txt",
            perfil=PerfilDestinatarioEnum.JUNIOR,
            formato=FormatoSalidaEnum.FLASHCARDS,
        )

        assert isinstance(resultado, AdaptacionResponseDTO)
        assert resultado.status == "exito"
        # Al salir del bloque, el archivo y su directorio temporal deben haber sido destruidos limpiamente
        assert archivo_recibido_en_pipeline is not None
        assert not os.path.exists(archivo_recibido_en_pipeline)

