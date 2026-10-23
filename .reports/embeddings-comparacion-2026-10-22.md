# Comparación de embeddings

**Fecha:** 2026-10-22
**Documentos:** 9 | **Consultas:** 27 | **top_k:** 4

Consultas: 3 conceptos clave por documento; búsqueda dentro del documento; juicio de relevancia por pooling con Gemini.

| Modelo | Hit@4 | Precision@4 | MRR | Indexación |
|---|---|---|---|---|
| models/gemini-embedding-001 | 0.96 | 0.63 | 0.87 | 485 s |
| sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | 0.93 | 0.53 | 0.70 | 62 s |
| sentence-transformers/paraphrase-multilingual-mpnet-base-v2 | 0.96 | 0.58 | 0.83 | 314 s |

## Documentos

- JWT en OCI.pdf (9 chunks): Oracle Cloud Infrastructure, API Gateway, Autenticación y Autorización
- VCN y subredes.pdf (14 chunks): VCN, Subredes, IPv4/IPv6 Doble Pila
- Arquitectura de microservicios.pdf (5 chunks): arquitectura de microservicios, arquitectura monolítica, Kubernetes
- Definiciones de salud.pdf (7 chunks): Derecho a la protección de la salud, Servicios de salud, Derechos de los pacientes
- Tema-11_SALUD-PUBLICA.pdf (21 chunks): Salud Pública, Binomio Salud-Enfermedad, Determinantes de la salud
- LatamFintechMarket2025.pdf (6 chunks): Fintech, Sistema financiero, Inteligencia artificial
- Mariana_GutierrezSanchez_MariaJose_MorenoFigueroa_2023.pdf (38 chunks): Fintech, Regulación financiera, Transformación digital
- Marketing_Digital_para_emprendedores.pdf (9 chunks): Marketing Digital, FODA, Benchmark
- elementos-marketing-digital.pdf (73 chunks): marketing digital, estrategia digital, SEO
