import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Añadir 'src' al path para poder importar módulos locales
sys.path.append(str(PROJECT_ROOT / "src"))

from dataia.ingestion.service import ingest_document
from dataia.chunking.service import process_chunks
from dataia.vectorstore.service import process_vectorstore

def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/test_pipeline_local.py <ruta_al_pdf>")
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"Error: El archivo '{file_path}' no existe.")
        sys.exit(1)

    print("\n" + "="*55)
    print("🚀 INICIANDO PRUEBA LOCAL DEL PIPELINE (IA-02 -> IA-04)")
    print("="*55)

    # ---------------------------------------------------------
    # FASE 1: INGESTIÓN (IA-02)
    # ---------------------------------------------------------
    print(f"\n[IA-02] Ingestando archivo: {file_path}...")
    ingestion_res = ingest_document(file_path)
    
    if ingestion_res.status == "rechazado":
        print(f"❌ FALLO EN INGESTIÓN: [{ingestion_res.codigo}] {ingestion_res.mensaje}")
        sys.exit(1)
        
    print(f"✅ INGESTIÓN EXITOSA.")
    print(f"  -> document_id generado: {ingestion_res.document_id}")
    print(f"  -> Páginas/Secciones extraídas: {len(ingestion_res.content)}")

    # ---------------------------------------------------------
    # FASE 2: CHUNKING Y METADATA (IA-03)
    # ---------------------------------------------------------
    print("\n[IA-03] Ejecutando segmentación (Chunking)...")
    chunking_res = process_chunks(ingestion_res)

    if chunking_res.status == "rechazado":
        print(f"❌ FALLO EN CHUNKING: [{chunking_res.codigo}] {chunking_res.mensaje}")
        sys.exit(1)

    print(f"✅ CHUNKING EXITOSO.")
    print(f"  -> Total chunks generados: {len(chunking_res.chunks)}")
    
    if chunking_res.chunks:
        # Métricas de Tamaño
        lengths = [len(chunk.text) for chunk in chunking_res.chunks]
        avg_len = sum(lengths) / len(lengths)
        max_len = max(lengths)
        min_len = min(lengths)
        print(f"  -> Métricas de tamaño (Caracteres): Promedio: {avg_len:.1f} | Max: {max_len} | Min: {min_len}")
        
        # Heurística para detección de estructuras (Tablas y Código)
        tabular_chunks = []
        code_chunks = []
        for chunk in chunking_res.chunks:
            is_table = getattr(chunk.metadata, 'tipo_contenido', '') == 'tabla' or chunk.text.count('|') >= 3
            is_code = getattr(chunk.metadata, 'tipo_contenido', '') == 'codigo' or '```' in chunk.text
            
            if is_table:
                tabular_chunks.append(chunk)
            if is_code:
                code_chunks.append(chunk)
                
        print(f"  -> Chunks con bloques de código detectados: {len(code_chunks)}")
        if code_chunks:
            print("\n  [AUDITORÍA VISUAL DE BLOQUES DE CÓDIGO (IA-03 REAPERTURA)]")
            for i, c_chunk in enumerate(code_chunks[:1]):
                print(f"  --- Muestra Código {i+1} (chunk_id: {c_chunk.metadata.chunk_id}, tipo: {getattr(c_chunk.metadata, 'tipo_contenido', 'N/A')}) ---")
                print(c_chunk.text)
                print("  --------------------------------------------------")

        print(f"  -> Chunks con posibles datos tabulares detectados: {len(tabular_chunks)}")
        if tabular_chunks:
            print("\n  [AUDITORÍA VISUAL DE ESTRUCTURAS TABULARES (IA-03 REAPERTURA)]")
            for i, tbl_chunk in enumerate(tabular_chunks[:1]):
                print(f"  --- Muestra Tabular {i+1} (chunk_id: {tbl_chunk.metadata.chunk_id}, tipo: {getattr(tbl_chunk.metadata, 'tipo_contenido', 'N/A')}) ---")
                print(tbl_chunk.text)
                print("  --------------------------------------------------")

        sample_chunk = chunking_res.chunks[0]
        print("\n  -> Ejemplo de trazabilidad y metadata pedagógica (Primer Chunk):")
        print(f"     - chunk_id: {sample_chunk.metadata.chunk_id}")
        print(f"     - document_id heredado: {sample_chunk.metadata.document_id}")
        print(f"     - página origen: {sample_chunk.metadata.page}")
        print(f"     - tipo_contenido: {getattr(sample_chunk.metadata, 'tipo_contenido', 'N/A')}")
        print(f"     - nivel_dificultad: {getattr(sample_chunk.metadata, 'nivel_dificultad', 'N/A')}")
        print(f"     - concepto_principal: {getattr(sample_chunk.metadata, 'concepto_principal', 'N/A')}")

    # ---------------------------------------------------------
    # FASE 3: EMBEDDINGS Y VECTOR STORE (IA-04)
    # ---------------------------------------------------------
    print("\n[IA-04] Generando embeddings y persistiendo en ChromaDB...")
    
    if not os.environ.get("GOOGLE_API_KEY"):
        print("⚠️ ADVERTENCIA: No se encontró la variable GOOGLE_API_KEY.")
        print("⚠️ La generación de embeddings mediante Gemini podría fallar.")
    
    vector_res = process_vectorstore(chunking_res)

    if vector_res.status == "rechazado":
        print(f"❌ FALLO EN VECTORSTORE: [{vector_res.codigo}] {vector_res.mensaje}")
        sys.exit(1)

    print(f"✅ VECTOR STORE EXITOSO.")
    print(f"  -> Chunks insertados físicamente: {vector_res.chunks_inserted}")
    print(f"  -> Colección destino: {vector_res.collection_name}")
    print(f"  -> Ruta de persistencia ChromaDB: {os.path.abspath('.chromadb_data')}")

    print("\n" + "="*55)
    print("🎉 PRUEBA E2E (HASTA IA-04) COMPLETADA EXITOSAMENTE")
    print("="*55 + "\n")

if __name__ == "__main__":
    main()
