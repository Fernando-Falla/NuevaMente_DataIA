"""
Ejecuta el pipeline completo (IA-02 → IA-08) con Gemini real sobre un documento.

Uso, desde la raíz del repositorio:
    uv run --system-certs python scripts/run_pipeline_real.py <documento> [perfil] [formato] [nicho]

Perfiles: Junior, Senior, Ejecutivo. Formatos: Flashcards, "Quiz Interactivo",
"Resumen Ejecutivo", "Mapa Mental". Usa IA_STRICT_PROVIDERS=1: un fallo del
proveedor detiene la ejecución en lugar de usar contenido de contingencia.
La respuesta se guarda en .reports/salida_<documento>_<perfil>_<formato>.json.
"""
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))

# Credenciales desde .env (ignorado por Git) y certificados del sistema operativo,
# necesarios en redes que inspeccionan TLS (antivirus, proxies corporativos).
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

os.environ.setdefault("IA_STRICT_PROVIDERS", "1")
if os.getenv("GOOGLE_API_KEY"):
    os.environ.setdefault("GEMINI_API_KEY", os.environ["GOOGLE_API_KEY"])

from nuevamente_ai.pipeline import ejecutar_pipeline_adaptacion  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    documento = Path(sys.argv[1])
    perfil = sys.argv[2] if len(sys.argv) > 2 else "Junior"
    formato = sys.argv[3] if len(sys.argv) > 3 else "Flashcards"
    nicho = sys.argv[4] if len(sys.argv) > 4 else "General"

    inicio = time.time()

    def progreso(etapa, paso, porcentaje, mensaje):
        print(f"[{time.time() - inicio:6.1f}s] {porcentaje:3d}% [{etapa}] {mensaje}", flush=True)

    try:
        respuesta = ejecutar_pipeline_adaptacion(
            documento_titulo=documento.stem, ruta_archivo=str(documento),
            perfil=perfil, formato=formato, nicho=nicho, callback_telemetria=progreso,
        )
    except Exception as error:
        print(f"\nRESULTADO: fallo tras {time.time() - inicio:.1f}s -> {type(error).__name__}: {str(error)[:500]}")
        sys.exit(2)

    salida = PROJECT_ROOT / ".reports" / f"salida_{documento.stem}_{perfil}_{formato}.json".replace(" ", "_")
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(respuesta.model_dump_json(indent=2), encoding="utf-8")
    contenido = respuesta.contenido_adaptado
    items = contenido.items if isinstance(contenido.items, list) else [contenido.items]
    print(f"\nRESULTADO: éxito en {time.time() - inicio:.1f}s | ítems: {len(items)} | salida: {salida.relative_to(PROJECT_ROOT)}")
    print(json.dumps(respuesta.model_dump(), ensure_ascii=False, indent=2)[:1500])


if __name__ == "__main__":
    main()
