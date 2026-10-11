import re

FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")

def normalize_text(text: str) -> str:
    """
    Normaliza el texto extraído sin perder la información técnica o la estructura general.
    Conserva la indentación inicial (listas anidadas en Markdown) y no altera el
    interior de los bloques de código, donde los espacios son significativos.
    """
    if not text:
        return ""

    # Eliminar caracteres nulos
    text = text.replace("\x00", "")

    lines = []
    in_fence = False
    for line in text.split("\n"):
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            lines.append(line.rstrip())
        elif in_fence:
            lines.append(line.rstrip())
        else:
            # Normalizar múltiples espacios horizontales a uno solo, salvo la indentación inicial
            indent = re.match(r"[ \t]*", line).group(0)
            lines.append(indent + re.sub(r"[ \t]+", " ", line[len(indent):]).rstrip())
    text = "\n".join(lines)

    # Normalizar más de 3 saltos de línea consecutivos a 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
