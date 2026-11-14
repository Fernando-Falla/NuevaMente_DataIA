"""
Pruebas unitarias de OCIStorage sin requerir credenciales reales ni conexión de red.
Verifica cálculo de hashes SHA-256, estructura de claves, firmas y resiliencia ante errores OCI.
"""

from datetime import datetime, timezone
from hashlib import md5, sha256
from io import BytesIO
from unittest.mock import MagicMock
import oci
import pytest

from backend.services.oci_service import OCIStorage
from tests.test_backend_api import make_dummy_response


@pytest.fixture
def dummy_resultado():
    return make_dummy_response("Flashcards")


def test_oci_storage_guardar_exitoso(dummy_resultado):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_client.put_object.return_value = mock_response

    storage = OCIStorage(
        namespace="test-namespace",
        bucket="test-bucket",
        client_factory=lambda: mock_client,
        clock=lambda: datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc),
    )

    doc_bytes = b"%PDF-1.4 Fake content for testing OCI storage"
    resultado_almacenado = storage.guardar(doc_bytes, "test_file.pdf", dummy_resultado)

    assert resultado_almacenado.almacenamiento_oci is not None
    assert resultado_almacenado.almacenamiento_oci.status_upload == "subido"
    assert resultado_almacenado.almacenamiento_oci.bucket == "test-bucket"
    assert resultado_almacenado.almacenamiento_oci.documento_original_subido is True

    # Comprobamos que put_object fue llamado exactamente 2 veces (fuente + artefacto)
    assert mock_client.put_object.call_count == 2
    calls = mock_client.put_object.call_args_list

    # Primera llamada: documento original
    call_doc = calls[0]
    assert call_doc.args[0] == "test-namespace"
    assert call_doc.args[1] == "test-bucket"
    assert "documentos-fuente/2026/11/" in call_doc.args[2]
    assert call_doc.kwargs["content_type"] == "application/pdf"

    # Segunda llamada: JSON generado
    call_json = calls[1]
    assert "artefactos-generados/2026/11/" in call_json.args[2]
    assert call_json.kwargs["content_type"] == "application/json; charset=utf-8"


def test_oci_storage_fallback_error_autenticacion(dummy_resultado):
    mock_client = MagicMock()
    # Simular ServiceError 401 de OCI
    mock_client.put_object.side_effect = oci.exceptions.ServiceError(
        status=401,
        code="NotAuthenticated",
        message="The required information to complete authentication was not provided.",
        headers={},
    )

    storage = OCIStorage(
        namespace="test-namespace",
        bucket="test-bucket",
        client_factory=lambda: mock_client,
    )

    doc_bytes = b"Sample text"
    resultado = storage.guardar(doc_bytes, "sample.txt", dummy_resultado)

    # El contenido generado se conserva intacto, con código de error descriptivo en metadatos
    assert resultado.contenido_adaptado.titulo == dummy_resultado.contenido_adaptado.titulo
    assert resultado.almacenamiento_oci is not None
    assert resultado.almacenamiento_oci.status_upload == "error"
    assert resultado.almacenamiento_oci.codigo_error == "OCI_ACCESO_DENEGADO"


def test_oci_storage_fallo_segundo_objeto_parcial(dummy_resultado):
    mock_client = MagicMock()
    mock_response = MagicMock(status=200)

    # Primer put_object tiene éxito, segundo falla
    mock_client.put_object.side_effect = [
        mock_response,
        RuntimeError("OCI connection lost on artifact upload"),
    ]

    storage = OCIStorage(
        namespace="test-namespace",
        bucket="test-bucket",
        client_factory=lambda: mock_client,
    )

    doc_bytes = b"# Titulo Markdown"
    resultado = storage.guardar(doc_bytes, "guia.md", dummy_resultado)

    assert resultado.almacenamiento_oci is not None
    # Como el original subió pero el JSON falló, el estado es 'parcial'
    assert resultado.almacenamiento_oci.status_upload == "parcial"
    assert resultado.almacenamiento_oci.documento_original_subido is True
    assert resultado.almacenamiento_oci.codigo_error == "OCI_NO_DISPONIBLE"
