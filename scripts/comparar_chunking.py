"""Compara extracción + chunking (sin LLM ni red) entre dos versiones de Data/IA sobre los PDFs de prueba.

El enriquecimiento con Gemini se reemplaza por valores fijos: se mide solo la
extracción y la segmentación. Desde la raíz del repositorio, con una copia de
la versión anterior de ia/ (commit 12ee492) en ia_old/, que Git ignora:

    .venv\\Scripts\\python.exe ia\\scripts\\comparar_chunking.py ia_old\\src nuevamente-ai-core\\tests\\*.pdf
    .venv\\Scripts\\python.exe ia\\scripts\\comparar_chunking.py ia\\src nuevamente-ai-core\\tests\\*.pdf

cobertura_vocabulario: proporción de palabras distintas (más de 3 letras) del
texto plano de PyMuPDF que aparecen en los chunks.
"""
import json
import os
import re
import sys

sys.path.insert(0, sys.argv[1])
os.environ.pop("IA_STRICT_PROVIDERS", None)

from dataia.ingestion import enrichment, service as ingestion  # noqa: E402
from dataia.chunking import structural_splitter  # noqa: E402
from dataia.chunking.service import process_chunks  # noqa: E402

enrichment.enrich_document_metadata = lambda doc_id, _t: enrichment.DocumentPedagogicalMetadata(document_id=doc_id)
default = structural_splitter.ChunkPedagogicalInfo(tipo_contenido="afirmacion", nivel_dificultad=1, concepto_principal="General")
structural_splitter.enrich_chunk_metadata = lambda *_a: default
if hasattr(structural_splitter, "enrich_chunks_metadata"):
    structural_splitter.enrich_chunks_metadata = lambda texts: [default] * len(texts)

def vocab(s):
    return {w for w in re.findall(r"[^\W_]+", s.lower()) if len(w) > 3 and not w.isdigit()}

def plain_text(pdf):
    import pymupdf
    with pymupdf.open(pdf) as d:
        return " ".join(p.get_text("text") for p in d)

out = {}
for pdf in sys.argv[2:]:
    ing = ingestion.ingest_document(pdf)
    if ing.status != "aprobado":
        out[os.path.basename(pdf)] = {"error": ing.codigo}
        continue
    full = "\n".join(c.text for c in ing.content)
    res = process_chunks(ing)
    chunks = res.chunks
    sizes = [len(c.text.split()) for c in chunks]
    out[os.path.basename(pdf)] = {
        "paginas": len(ing.content),
        "titulos_md": len(re.findall(r"^#{1,6} ", full, re.MULTILINE)),
        "tablas_md": len(re.findall(r"^\|[\s\-:|]+\|$", full, re.MULTILINE)),
        "chunks": len(chunks),
        "palabras_min_max_prom": [min(sizes), max(sizes), round(sum(sizes) / len(sizes))],
        "chunks_con_section": sum(1 for c in chunks if c.metadata.section),
        "chunks_cruzan_pagina": sum(1 for c in chunks if getattr(c.metadata, "page_end", None) not in (None, c.metadata.page)),
        "secciones": list(dict.fromkeys(c.metadata.section for c in chunks if c.metadata.section))[:8],
        "document_id": ing.document_id,
        "cobertura_vocabulario": round(len(vocab(" ".join(c.text for c in chunks)) & vocab(plain_text(pdf))) / len(vocab(plain_text(pdf))), 3),
        "palabras_total": sum(sizes),
    }
print(json.dumps(out, ensure_ascii=False, indent=1))
