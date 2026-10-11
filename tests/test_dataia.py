"""Pruebas locales de Data/IA: no usan red ni proveedores LLM."""

import pymupdf
import pytest

from dataia.chunking import structural_splitter
from dataia.chunking.structural_splitter import ChunkPedagogicalInfo, StructuralSplitter, perform_structural_chunking
from dataia.common.models import Chunk, ChunkMetadata, DocumentMetadata, ExtractedContent
from dataia.ingestion import enrichment, service as ingestion
from dataia.ingestion.normalizer import normalize_text
from dataia.vectorstore import client


INFO = ChunkPedagogicalInfo(tipo_contenido="definicion", nivel_dificultad=2, concepto_principal="JWT")
TECH_TEXT = "La arquitectura del sistema usa una API con token JWT para la seguridad del servidor en la nube. "


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.delenv("IA_STRICT_PROVIDERS", raising=False)
    monkeypatch.setattr(structural_splitter, "CACHE_DIR", str(tmp_path / "chunk_cache"))
    monkeypatch.setattr(client, "DOCUMENTS_DIRECTORY", str(tmp_path / "documents"))
    monkeypatch.setattr(enrichment, "enrich_document_metadata", lambda doc_id, _text: enrichment.DocumentPedagogicalMetadata(document_id=doc_id))


def content(text, page=None):
    return ExtractedContent(text=text, metadata=DocumentMetadata(document_id="doc-x", name="a.md", doc_type="md", page=page))


def test_clave_propia_de_dataia(monkeypatch):
    from dataia.common.credentials import get_google_api_key

    monkeypatch.setenv("GOOGLE_API_KEY", "clave-ai-core")
    monkeypatch.setenv("DATAIA_GOOGLE_API_KEY", "")
    assert get_google_api_key() == "clave-ai-core"
    monkeypatch.setenv("DATAIA_GOOGLE_API_KEY", "clave-dataia")
    assert get_google_api_key() == "clave-dataia"
    assert client.get_embeddings_model().google_api_key.get_secret_value() == "clave-dataia"


def test_normalizer_preserva_indentacion_y_codigo():
    text = "Lista:\n- uno\n    - anidado   con   espacios\n```python\ndef f():\n    return  1\n```"
    result = normalize_text(text)
    assert "    - anidado con espacios" in result
    assert "    return  1" in result


def test_titulo_dentro_de_codigo_no_es_seccion():
    text = (
        "# Instalación\n\nPaso inicial.\n\n```bash\n# comentario de shell\necho hola\n```\n\n"
        + "Texto posterior de la instalación. " * 400
    )
    pieces = StructuralSplitter().split_with_sections(text)
    assert len(pieces) > 1
    assert {piece.section for piece in pieces} == {"Instalación"}
    assert all(piece.text.startswith("# Instalación") for piece in pieces)


def test_titulo_aislado_no_genera_chunk():
    pieces = StructuralSplitter().split_with_sections("## Tokens\n\n" + "Firma del token JWT. " * 400)
    assert all(piece.text.strip() != "## Tokens" for piece in pieces)
    assert all(piece.section == "Tokens" for piece in pieces)


def test_chunking_cruza_paginas_y_registra_pagina_final(monkeypatch):
    monkeypatch.setattr(structural_splitter, "enrich_chunks_metadata", lambda texts: [INFO] * len(texts))
    page_1 = "\n\n".join(f"Párrafo {n} sobre la firma del token JWT y su validación en el servidor. " * 3 for n in range(12))
    page_2 = "\n\n".join(f"Párrafo {n} de la segunda página. " * 5 for n in range(12, 18))
    pages = [content("## Tokens\n\n" + page_1, page=1), content(page_2, page=2)]
    chunks = perform_structural_chunking("doc-x", pages)
    assert chunks[0].metadata.page == 1
    assert chunks[-1].metadata.page_end == 2
    assert any(c.metadata.page == 1 and c.metadata.page_end == 2 for c in chunks)
    assert all(c.metadata.section == "Tokens" for c in chunks)
    assert [c.metadata.chunk_id for c in chunks] == [f"doc-x-chk-{i:04d}" for i in range(1, len(chunks) + 1)]


def test_enriquecimiento_por_lotes_cache_y_reintento(monkeypatch):
    calls = []
    monkeypatch.setattr(structural_splitter, "BATCH_SIZE", 2)

    def fake_batch(texts):
        calls.append(list(texts))
        return {0: INFO}  # omite el segundo fragmento de cada lote

    monkeypatch.setattr(structural_splitter, "_enrich_batch", fake_batch)
    monkeypatch.setattr(structural_splitter, "enrich_chunk_metadata", lambda _id, _text: INFO)
    texts = ["uno", "dos", "tres"]
    assert structural_splitter.enrich_chunks_metadata(texts) == [INFO, INFO, INFO]
    assert calls == [["uno", "dos"], ["tres"]]

    calls.clear()
    structural_splitter.enrich_chunks_metadata(["uno", "tres"])
    assert calls == []  # ambos quedaron en caché


def test_enriquecimiento_sin_proveedor(monkeypatch):
    def fail(_texts):
        raise ConnectionError("sin red")

    monkeypatch.setattr(structural_splitter, "_enrich_batch", fail)
    assert structural_splitter.enrich_chunks_metadata(["uno"])[0].concepto_principal == "General"
    monkeypatch.setenv("IA_STRICT_PROVIDERS", "1")
    with pytest.raises(ConnectionError):
        structural_splitter.enrich_chunks_metadata(["dos"])


def test_document_id_estable_y_nombre_original(tmp_path):
    path = tmp_path / "documento.md"
    path.write_text(TECH_TEXT * 3, encoding="utf-8")
    first = ingestion.ingest_document(str(path), document_name="JWT en OCI.md")
    second = ingestion.ingest_document(str(path))
    assert first.status == "aprobado"
    assert first.document_id == second.document_id
    assert first.content[0].metadata.name == "JWT en OCI.md"


def test_extraccion_pdf_por_pagina(tmp_path):
    path = tmp_path / "doc.pdf"
    pdf = pymupdf.open()
    for number in (1, 2):
        pdf.new_page().insert_text((72, 72), f"Pagina {number}: {TECH_TEXT}"[:90])
    pdf.save(str(path))
    pdf.close()
    pages = ingestion._extract_pdf(str(path), "doc-x", "doc.pdf")
    assert [p.metadata.page for p in pages] == [1, 2]
    assert "Pagina 2" in pages[1].text


def test_pagina_con_markdown_incompleto_usa_texto_plano(tmp_path, monkeypatch):
    import pymupdf4llm

    path = tmp_path / "doc.pdf"
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "Arquitectura de red con subredes privadas y gateways")
    pdf.save(str(path))
    pdf.close()
    # Simula el caso real: pymupdf4llm omite el texto superpuesto a una imagen
    monkeypatch.setattr(pymupdf4llm, "to_markdown", lambda *_a, **_k: "29/9/26 encabezado")
    pages = ingestion._extract_pdf(str(path), "doc-x", "doc.pdf")
    assert "subredes privadas" in pages[0].text


def test_encabezados_repetidos_y_enlaces():
    bodies = ["\n".join(f"Paso {n}{i}: configurar la subred" for i in range(1, 9)) for n in range(1, 5)]
    texts = [f"29/9/26, 17:05 VCN\n{body}\nhttps://docs.example/x {n}/4" for n, body in enumerate(bodies, start=1)]
    cleaned = ingestion._remove_repeated_lines(texts)
    # Se eliminan encabezado y pie; el cuerpo se conserva aunque sus líneas solo difieran en números
    assert cleaned == bodies
    assert ingestion._MARKDOWN_LINK.sub(r"\1", "Ver [la VCN](https://a.b/c?x=(1)) ahora") == "Ver la VCN ahora"


class FakeStore:
    def __init__(self):
        self.rows = {}
        self.added = 0
        self._collection = self  # insert_chunks actualiza metadata mediante _collection.update

    def update(self, ids, metadatas):
        for i, meta in zip(ids, metadatas):
            self.rows[i] = (self.rows[i][0], meta)

    def get(self, where, include):
        ids = [i for i, (_, meta) in self.rows.items() if meta["document_id"] == where["document_id"]]
        return {"ids": ids, "documents": [self.rows[i][0] for i in ids], "metadatas": [self.rows[i][1] for i in ids]}

    def delete(self, ids):
        for i in ids:
            self.rows.pop(i)

    def add_documents(self, documents, ids):
        self.added += len(documents)
        for i, doc in zip(ids, documents):
            self.rows[i] = (doc.page_content, doc.metadata)


def make_chunks(*texts):
    return [
        Chunk(text=t, metadata=ChunkMetadata(document_id="doc-x", chunk_id=f"doc-x-chk-{i:04d}", name="a", doc_type="md", section="S"))
        for i, t in enumerate(texts, start=1)
    ]


def test_indexacion_idempotente(monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(client, "get_vector_store", lambda: store)
    assert client.insert_chunks(make_chunks("a", "b")) is False
    assert client.insert_chunks(make_chunks("a", "b")) is True
    assert store.added == 2  # no se recalcularon embeddings
    assert client.insert_chunks(make_chunks("a")) is False
    assert list(store.rows) == ["doc-x-chk-0001"]  # se eliminaron los vectores obsoletos
    assert [d.page_content for d in client.get_document_chunks("doc-x")] == ["a"]


def test_reindexacion_actualiza_metadata_sin_recalcular_embeddings(monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(client, "get_vector_store", lambda: store)
    client.insert_chunks(make_chunks("a"))
    reclasificado = make_chunks("a")
    reclasificado[0].metadata.tipo_contenido = "definicion"
    assert client.insert_chunks(reclasificado) is True
    assert store.added == 1
    assert store.rows["doc-x-chk-0001"][1]["tipo_contenido"] == "definicion"


def test_modelo_configurable(monkeypatch):
    from dataia.common.credentials import DEFAULT_GEMINI_MODEL, get_gemini_model

    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert get_gemini_model() == DEFAULT_GEMINI_MODEL
    monkeypatch.setenv("GEMINI_MODEL", "otro-modelo")
    assert get_gemini_model() == "otro-modelo"


def test_registro_documento():
    meta = enrichment.DocumentPedagogicalMetadata(document_id="doc-x", conceptos_clave=["JWT"])
    client.save_document_record("doc-x", make_chunks("a", "b"), meta)
    record = client.load_document_record("doc-x")
    assert record["chunks"] == 2
    assert record["sections"] == ["S"]
    assert record["pedagogical_metadata"]["conceptos_clave"] == ["JWT"]
    assert client.load_document_record("doc-otro") is None
