"""Regresiones locales del agente crítico (spec IA-07): sin red ni proveedor real."""

import asyncio

import pytest
from unittest.mock import Mock

from dataia.common import providers
from nuevamente_ai.agents.auditor import AuditorAgent
from nuevamente_ai.agents.critico import EvaluacionItems, VeredictoItem, decidir_proximo_paso, nodo_critico


def veredictos(*pares):
    return EvaluacionItems(items=[VeredictoItem(indice=i, veredicto=v, observacion=o) for i, v, o in pares])


@pytest.fixture(autouse=True)
def juez_simulado(monkeypatch):
    # Evitar la rama del score fijo habilitada por la suite anterior.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("UMBRAL_ANCLAJE_MINIMO", raising=False)
    monkeypatch.delenv("IA_STRICT_PROVIDERS", raising=False)
    juez = Mock()
    juez.invoke.return_value = veredictos((0, "respaldado", ""))
    # obtener_llm_etapa devuelve el modelo con salida estructurada y el limitador de su proveedor
    proveedor = Mock(return_value=(juez, providers.GENERATION_LIMITER))
    monkeypatch.setattr("nuevamente_ai.config.obtener_llm_etapa", proveedor)
    return proveedor, juez


@pytest.mark.parametrize("documento", ["", " \n\t "])
def test_contexto_vacio_no_se_aprueba_ni_provoca_excepcion(documento, juez_simulado):
    state = {
        "fragmentos_relevantes": [{"contenido": ""}, {"contenido": ""}],
        "documento_contenido": documento,
        "borrador_contenido": {"items": ["afirmacion inventada sin respaldo"]},
        "contador_intentos": 1,
    }
    resultado = nodo_critico(state)
    assert resultado["anclaje_fuente_score"] == 0.0
    assert "Contexto Insuficiente" in resultado["critica_observaciones"]
    assert decidir_proximo_paso({**state, **resultado}) == "nodo_creador"
    proveedor, juez = juez_simulado
    proveedor.assert_not_called()
    juez.invoke.assert_not_called()


def test_fragmentos_con_contenido_permiten_evaluar_el_borrador(juez_simulado):
    fuente = "autenticacion seguridad arquitectura microservicios"
    resultado = nodo_critico({
        "fragmentos_relevantes": [{"contenido": fuente}],
        "documento_contenido": "",
        "borrador_contenido": {"items": [fuente]},
    })
    assert resultado["anclaje_fuente_score"] >= 0.85
    _, juez = juez_simulado
    juez.invoke.assert_called_once()
    assert fuente in juez.invoke.call_args.args[0][1].content


def test_separadores_vacios_permiten_usar_el_documento_de_respaldo(juez_simulado):
    fuente = "autenticacion seguridad arquitectura microservicios"
    resultado = nodo_critico({
        "fragmentos_relevantes": [{"contenido": " "}, {"contenido": " "}],
        "documento_contenido": fuente,
        "borrador_contenido": {"items": [fuente]},
    })
    assert resultado["anclaje_fuente_score"] >= 0.85
    _, juez = juez_simulado
    assert fuente in juez.invoke.call_args.args[0][1].content


def test_contexto_vacio_se_rechaza_incluso_con_clave_de_pruebas(monkeypatch, juez_simulado):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy_gemini_key")
    resultado = nodo_critico({
        "documento_titulo": "JWT en OCI",
        "fragmentos_relevantes": [],
        "documento_contenido": "",
        "borrador_contenido": {"items": ["afirmacion inventada"]},
    })
    assert resultado["anclaje_fuente_score"] == 0.0
    proveedor, _ = juez_simulado
    proveedor.assert_not_called()


def test_juez_rechaza_afirmaciones_sin_respaldo(juez_simulado):
    _, juez = juez_simulado
    juez.invoke.return_value = veredictos((0, "sin_respaldo", "La fuente no respalda que JWT siempre cifre el contenido."))
    state = {
        "fragmentos_relevantes": [{"contenido": "JWT describe autenticacion mediante tokens firmados"}],
        "borrador_contenido": {"items": [{"frente": "¿JWT cifra?", "dorso": "JWT siempre cifra el contenido"}]},
        "contador_intentos": 1,
    }
    resultado = nodo_critico(state)
    assert resultado["anclaje_fuente_score"] == 0.0
    assert "no respalda" in resultado["critica_observaciones"]
    assert decidir_proximo_paso({**state, **resultado}) == "nodo_creador"


def test_score_se_calcula_en_codigo_y_omitidos_cuentan_como_parcial(juez_simulado):
    _, juez = juez_simulado
    # 4 ítems: respaldado, parcial, sin respaldo y uno omitido por el juez -> (1 + 0,5 + 0 + 0,5) / 4
    juez.invoke.return_value = veredictos((0, "respaldado", ""), (1, "parcial", "x"), (2, "sin_respaldo", "y"))
    resultado = nodo_critico({
        "fragmentos_relevantes": [{"contenido": "fuente técnica"}],
        "borrador_contenido": {"items": [{"frente": f"p{i}", "dorso": "d"} for i in range(4)]},
        "contador_intentos": 2,
    })
    assert resultado["anclaje_fuente_score"] == 0.5
    assert "el juez no lo evaluó" in resultado["critica_observaciones"]


def test_retroalimentacion_nombra_los_items_a_corregir(juez_simulado):
    _, juez = juez_simulado
    juez.invoke.return_value = veredictos((0, "respaldado", ""), (1, "sin_respaldo", "Inventa una expiración de 24 horas."))
    resultado = nodo_critico({
        "fragmentos_relevantes": [{"contenido": "fuente técnica"}],
        "borrador_contenido": {"items": [{"frente": "¿Qué es un JWT?", "dorso": "d"}, {"frente": "¿Cuánto dura un JWT?", "dorso": "24 h"}]},
        "contador_intentos": 1,
    })
    observaciones = resultado["critica_observaciones"]
    assert "Ítem 2 (¿Cuánto dura un JWT?)" in observaciones
    assert "24 horas" in observaciones
    assert "Ítem 1" not in observaciones


def test_objeto_unico_y_campos_excluidos(juez_simulado):
    _, juez = juez_simulado
    nodo_critico({
        "fragmentos_relevantes": [{"contenido": "fuente técnica"}],
        "borrador_contenido": {"items": {"nodo_central": "VCN", "arbol": [], "codigo_mermaid": "mindmap\n  root((VCN))"}},
        "formato_salida": "Mapa Mental",
    })
    prompt = juez.invoke.call_args.args[0][1].content
    contenido = prompt.split("--- CONTENIDO GENERADO ---")[1]
    assert "ÍTEM 0" in contenido and "ÍTEM 1" not in contenido
    assert "codigo_mermaid" not in contenido


def test_quiz_indica_que_los_distractores_son_falsos(juez_simulado):
    _, juez = juez_simulado
    nodo_critico({
        "fragmentos_relevantes": [{"contenido": "fuente técnica"}],
        "borrador_contenido": {"items": [{"pregunta": "p", "opciones": ["a", "b", "c", "d"], "indice_correcto": 1}]},
        "formato_salida": "Quiz Interactivo",
    })
    assert "opciones incorrectas son falsas a propósito" in juez.invoke.call_args.args[0][1].content


def test_fallo_del_proveedor(monkeypatch, juez_simulado):
    _, juez = juez_simulado
    juez.invoke.side_effect = TimeoutError("sin respuesta")
    state = {"fragmentos_relevantes": [{"contenido": "fuente"}], "borrador_contenido": {"items": ["x"]}}
    assert nodo_critico(state)["anclaje_fuente_score"] == 0.5
    monkeypatch.setenv("IA_STRICT_PROVIDERS", "1")
    with pytest.raises(TimeoutError):
        nodo_critico(state)


def test_auditor_reconoce_contenido_adaptado():
    paquete = {"status": "exito", "contenido_adaptado": {"titulo": "JWT", "items": [{"frente": "¿Qué es un JWT?"}]}}
    seguro, vulnerabilidades, _ = asyncio.run(AuditorAgent().auditar_seguridad_async(paquete))
    assert seguro, vulnerabilidades
