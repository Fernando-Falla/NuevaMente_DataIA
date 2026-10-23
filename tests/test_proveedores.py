"""Spec de proveedores por etapa y embeddings locales: pruebas sin red."""

import numpy as np
import pytest
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks

from dataia.common import providers
from dataia.vectorstore import client


class ModeloFalso:
    """Imita un chat de LangChain: with_structured_output devuelve un Runnable."""

    def __init__(self, respuesta=None, error=None):
        self.respuesta, self.error = respuesta, error

    def with_structured_output(self, _schema):
        def invoke(_value):
            if self.error:
                raise self.error
            return self.respuesta
        return RunnableLambda(invoke)


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    for variable in ("IA_PROVIDER_CLASIFICACION", "IA_PROVIDER_GENERACION", "IA_PROVIDER_CRITICO", "GROQ_API_KEY", "DATAIA_EMBEDDINGS"):
        monkeypatch.delenv(variable, raising=False)


def test_gemini_por_defecto_en_todas_las_etapas():
    assert {providers.stage_provider(e) for e in ("CLASIFICACION", "GENERACION", "CRITICO")} == {"gemini"}


def test_groq_sin_clave_usa_gemini(monkeypatch):
    monkeypatch.setenv("IA_PROVIDER_CRITICO", "groq")
    assert providers.stage_provider("CRITICO") == "gemini"
    monkeypatch.setenv("GROQ_API_KEY", "clave")
    assert providers.stage_provider("CRITICO") == "groq"


def test_proveedor_invalido(monkeypatch):
    monkeypatch.setenv("IA_PROVIDER_GENERACION", "otro")
    with pytest.raises(ValueError):
        providers.stage_provider("GENERACION")


def test_groq_con_respaldo_en_gemini(monkeypatch):
    monkeypatch.setenv("IA_PROVIDER_CRITICO", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "clave")
    monkeypatch.setattr(providers, "create_groq_llm", lambda temperature=0.0: ModeloFalso(error=RuntimeError("413 request too large")))
    monkeypatch.setattr(providers, "create_gemini_llm", lambda temperature=0.0, api_key=None: ModeloFalso(respuesta="gemini"))
    llm, limiter = providers.create_stage_llm("CRITICO", schema=object)
    assert isinstance(llm, RunnableWithFallbacks)
    assert limiter is providers.GROQ_LIMITER
    assert llm.invoke("prompt") == "gemini"


def test_etapa_gemini_usa_su_limitador(monkeypatch):
    monkeypatch.setattr(providers, "create_gemini_llm", lambda temperature=0.0, api_key=None: ModeloFalso(respuesta="ok"))
    llm, limiter = providers.create_stage_llm("GENERACION", schema=object)
    assert limiter is providers.GENERATION_LIMITER
    assert llm.invoke("prompt") == "ok"


def test_embeddings_locales_por_defecto():
    assert client.embeddings_backend() == "local"


def test_coleccion_por_modelo_de_embeddings(monkeypatch):
    monkeypatch.setenv("DATAIA_EMBEDDINGS", "gemini")
    assert client.collection_name() == client.COLLECTION_NAME
    monkeypatch.delenv("DATAIA_EMBEDDINGS")
    monkeypatch.setenv("DATAIA_EMBEDDINGS", "local")
    monkeypatch.setenv("DATAIA_LOCAL_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    minilm = client.collection_name()
    assert minilm.startswith(client.COLLECTION_NAME + "__") and "minilm" in minilm and len(minilm) <= 63
    monkeypatch.setenv("DATAIA_LOCAL_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    assert client.collection_name() != minilm  # modelos distintos, colecciones distintas


def test_backend_de_embeddings_invalido(monkeypatch):
    monkeypatch.setenv("DATAIA_EMBEDDINGS", "otro")
    with pytest.raises(ValueError):
        client.embeddings_backend()


def test_embeddings_locales_con_fastembed_simulado(monkeypatch):
    import fastembed

    class TextEmbeddingFalso:
        def __init__(self, model_name, cache_dir):
            self.model_name = model_name

        def embed(self, textos):
            return (np.array([float(len(t)), 1.0]) for t in textos)

        def query_embed(self, texto):
            return iter([np.array([float(len(texto)), 0.0])])

    monkeypatch.setattr(fastembed, "TextEmbedding", TextEmbeddingFalso)
    modelo = client.LocalEmbeddings("modelo")
    assert modelo.embed_documents(["ab", "abc"]) == [[2.0, 1.0], [3.0, 1.0]]
    assert modelo.embed_query("abcd") == [4.0, 0.0]


def test_embeddings_locales_no_usan_control_de_cuota(monkeypatch):
    from tests.test_dataia import FakeStore, make_chunks

    store = FakeStore()
    monkeypatch.setenv("DATAIA_EMBEDDINGS", "local")
    monkeypatch.setattr(client, "get_vector_store", lambda: store)

    def sin_cuota(*_args, **_kwargs):
        raise AssertionError("Los embeddings locales no deben pasar por el control de cuota")

    monkeypatch.setattr(providers.EMBEDDING_LIMITER, "acquire", sin_cuota)
    assert client.insert_chunks(make_chunks("a", "b", "c")) is False
    assert store.added == 3


def test_prompt_que_no_cabe_en_groq_va_directo_a_gemini(monkeypatch):
    monkeypatch.setenv("IA_PROVIDER_CRITICO", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "clave")
    monkeypatch.setenv("IA_GROQ_TPM", "8000")

    def groq_no_debe_crearse(temperature=0.0):
        raise AssertionError("Groq no debía usarse para un prompt grande")

    monkeypatch.setattr(providers, "create_groq_llm", groq_no_debe_crearse)
    monkeypatch.setattr(providers, "create_gemini_llm", lambda temperature=0.0, api_key=None: ModeloFalso(respuesta="gemini"))
    assert providers.groq_max_prompt_tokens() == 5600
    llm, limiter = providers.create_stage_llm("CRITICO", schema=object, prompt_tokens=9000)
    assert limiter is providers.GENERATION_LIMITER and llm.invoke("x") == "gemini"
