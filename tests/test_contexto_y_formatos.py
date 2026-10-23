"""Spec IA-05/IA-06 (contexto y formatos): pruebas sin red."""

from unittest.mock import Mock

import pytest
from langchain_core.documents import Document

from dataia.common import providers
from dataia.common.budget import estimate_tokens
from nuevamente_ai.agents import creador
from nuevamente_ai.agents.analizador import nodo_analizador
from nuevamente_ai.agents.creador import convertir_mapa_mental
from nuevamente_ai.contexto import seleccionar_contexto, verificar_pertinencia_formato
from nuevamente_ai.schemas import ESQUEMA_GENERACION_POR_FORMATO, MapaMentalItem, PaqueteMapaMental


def chunk(i, seccion, tipo, palabras=100):
    return Document(page_content=f"chunk {i} " + "palabra " * palabras,
                    metadata={"chunk_id": f"doc-x-chk-{i:04d}", "section": seccion, "tipo_contenido": tipo})


def ids(docs):
    return [d.metadata["chunk_id"][-2:] for d in docs]


def test_documento_que_cabe_se_envia_completo():
    docs = [chunk(i, "A", "afirmacion") for i in range(1, 4)]
    assert ids(seleccionar_contexto(list(reversed(docs)), "Flashcards", max_tokens=10_000)) == ["01", "02", "03"]


def test_presupuesto_cobertura_y_orden_del_documento():
    # 3 secciones con 3 chunks de ~130 tokens; presupuesto para 4 chunks
    docs = [chunk(i, s, t) for i, (s, t) in enumerate(
        [("A", "afirmacion"), ("A", "definicion"), ("A", "ejemplo"),
         ("B", "afirmacion"), ("B", "afirmacion"), ("B", "definicion"),
         ("C", "tabla"), ("C", "tabla"), ("C", "tabla")], start=1)]
    presupuesto = 4 * estimate_tokens(docs[0].page_content)
    elegidos = seleccionar_contexto(docs, "Flashcards", max_tokens=presupuesto)
    assert sum(estimate_tokens(d.page_content) for d in elegidos) <= presupuesto
    assert {d.metadata["section"] for d in elegidos} == {"A", "B", "C"}  # una por sección
    assert "02" in ids(elegidos) and "06" in ids(elegidos)  # definiciones primero en Flashcards
    assert ids(elegidos) == sorted(ids(elegidos))  # orden del documento


def test_prioridad_de_la_guia_y_desempate_por_similitud():
    docs = [chunk(1, "A", "definicion"), chunk(2, "A", "procedimiento"), chunk(3, "A", "procedimiento")]
    un_chunk = estimate_tokens(docs[0].page_content)
    elegidos = seleccionar_contexto(docs, "Guia Paso a Paso", similitud={"doc-x-chk-0003": 0.9, "doc-x-chk-0002": 0.1},
                                    max_tokens=un_chunk)
    assert ids(elegidos) == ["03"]


def test_siempre_al_menos_un_chunk():
    assert len(seleccionar_contexto([chunk(1, "A", "afirmacion", palabras=5000)], "Quiz Interactivo", max_tokens=100)) == 1


@pytest.mark.parametrize("tipos, adecuado", [
    (["definicion"] * 20 + ["procedimiento"], False),          # 1 chunk: insuficiente
    (["procedimiento"] + ["afirmacion"] * 5, False),            # 17 % pero un solo chunk
    (["procedimiento", "codigo"] + ["definicion"] * 20, False),  # 2 chunks pero 9 %
    (["procedimiento"] * 4 + ["definicion"] * 5, True),
])
def test_pertinencia_de_la_guia(tipos, adecuado):
    docs = [chunk(i, "A", t) for i, t in enumerate(tipos, start=1)]
    rechazo = verificar_pertinencia_formato("Guia Paso a Paso", docs)
    assert (rechazo is None) == adecuado
    assert verificar_pertinencia_formato("Flashcards", docs) is None


def test_mapa_sin_recursion_se_convierte_en_arbol_y_mermaid_coincidentes():
    borrador = {"titulo": "t", "introduccion_contextualizada": "i", "items": {
        "nodo_central": "Salud Pública", "descripcion_general": "d",
        "ramas": [{"etiqueta": "Determinantes", "subtemas": [{"etiqueta": "Biología", "detalles": ["Genética"]},
                                                              {"etiqueta": "Entorno", "detalles": []}]},
                  {"etiqueta": "Prevención", "subtemas": [{"etiqueta": "Primaria", "detalles": ["Vacunas", "Educación"]}]}]}}
    items = convertir_mapa_mental(borrador)["items"]
    MapaMentalItem(**items)  # cumple el contrato de respuesta
    arbol = items["arbol"]
    assert arbol[0]["id"] == "1" and arbol[0]["subnodos"][0]["id"] == "1.1"
    assert arbol[1]["subnodos"][0]["subnodos"][1]["id"] == "2.1.2"
    lineas = items["codigo_mermaid"].splitlines()
    assert lineas[:2] == ["mindmap", "  root((Salud Pública))"]
    # una línea por nodo: 2 ramas + 3 subtemas + 3 detalles
    assert len(lineas) - 2 == 8
    assert "        Genética" in lineas  # tercer nivel con su sangría


def test_otros_formatos_no_se_modifican():
    borrador = {"items": [{"frente": "a", "dorso": "b"}]}
    assert convertir_mapa_mental(borrador) == borrador


def test_un_esquema_por_formato_en_el_generador(monkeypatch):
    llm = Mock()
    llm.invoke.return_value = PaqueteMapaMental(titulo="t", introduccion_contextualizada="i", items={
        "nodo_central": "C", "descripcion_general": "d",
        "ramas": [{"etiqueta": "R", "subtemas": [{"etiqueta": "S", "detalles": []}]}]})
    obtener = Mock(return_value=(llm, providers.GENERATION_LIMITER))
    monkeypatch.setattr(creador, "obtener_llm_etapa", obtener)
    resultado = creador.nodo_creador({"formato_salida": "Mapa Mental", "fragmentos_relevantes": [{"contenido": "fuente"}],
                                      "metadata_documento": {"conceptos_clave": ["Concepto A"], "resumen_ejecutivo": "Síntesis"}})
    assert obtener.call_args.args[1] is ESQUEMA_GENERACION_POR_FORMATO["Mapa Mental"]
    assert resultado["borrador_contenido"]["items"]["arbol"][0]["subnodos"][0]["etiqueta"] == "S"
    prompt = llm.invoke.call_args.args[0][1].content
    assert "Concepto A" in prompt and "Síntesis" in prompt


def test_analizador_usa_los_conceptos_del_documento():
    estado = nodo_analizador({"perfil_destinatario": "Junior", "formato_salida": "Flashcards",
                              "conceptos_clave": ["Tasa de intercambio", "Contracargo"],
                              "fragmentos_relevantes": [{"contenido": "Notas Gateway Oracle"}]})
    assert estado["conceptos_clave"] == ["Tasa de intercambio", "Contracargo"]
