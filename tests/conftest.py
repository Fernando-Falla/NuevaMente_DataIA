"""Configuración común de las pruebas."""

import os

# Las pruebas usan claves ficticias o proveedores simulados: el control de ritmo
# de la cuenta gratuita (10 llamadas por minuto) solo las haría más lentas.
# Las pruebas propias del limitador fijan sus límites con monkeypatch.
for variable in ("IA_PROVIDER_RPM", "IA_EMBEDDING_RPM"):
    os.environ.setdefault(variable, "100000")
for variable in ("IA_PROVIDER_TPM", "IA_EMBEDDING_TPM"):
    os.environ.setdefault(variable, "1000000000")
