"""Módulo de prompts y calibración pedagógica."""
from .perfiles import PROMPTS_SISTEMA_POR_PERFIL, obtener_prompt_sistema
from .formatos import obtener_instrucciones_formato

__all__ = ["PROMPTS_SISTEMA_POR_PERFIL", "obtener_prompt_sistema", "obtener_instrucciones_formato"]
