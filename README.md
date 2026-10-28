# Minería de texto para la investigación (SCA2) — paquete completo

Pipeline reproducible que toma un **CSV bibliográfico** (títulos y resúmenes exportados de
bases científicas), realiza **minería de texto** y genera:

- un esqueleto `materia_prima.md` con la evidencia extraída (términos clave, temas,
  co-ocurrencia, candidatas a brecha, tendencia temporal), pensado como **materia prima
  para que un LLM redacte una cuartilla** de la investigación;
- dos figuras: **red de co-ocurrencia** de términos y **barras de temas**.

Incluye además un **skill** (`redactar-cuartilla-investigacion`) para que un agente como
**opencode** convierta la materia prima en la cuartilla, con reglas estrictas de honestidad
(no inventar datos ni citas).

## Estructura

```
mineria-texto-sca2/
├── README.md
├── COMO_EJECUTAR.md           # guía de ejecución paso a paso
├── requirements.txt
├── install.sh / install.bat  # instalación (Linux·macOS / Windows)
├── recolector.py             # (Paso 1) ingesta por API -> CSV
├── lector_md_mcp.py          # (Paso 1 alt.) carpeta de .md del MCP -> corpus
├── mineria_texto.py          # minería -> materia_prima.md
├── figuras_mineria.py        # red de co-ocurrencia + barras de temas
├── run_pipeline.py           # orquestador (minería + figuras en un paso)
├── data/
│   ├── sample_corpus.csv            # corpus mínimo de ejemplo (títulos)
│   └── wos_miembros_inferiores.csv  # corpus real (Web of Science, 77 docs)
├── docs/
│   └── INTEGRACION_OPENCODE.md   # guía del skill + opencode
└── .opencode/
    └── skills/
        └── redactar-cuartilla-investigacion/
            └── SKILL.md      # skill de redacción de la cuartilla
```

## Requisitos

Python 3.9+. Dependencias núcleo (funciona 100 % offline): `pandas`, `numpy`,
`scikit-learn`, `matplotlib`, `networkx`. Opcional: `bertopic` + `sentence-transformers`
para minería semántica (descarga modelos en tiempo de ejecución).

## Instalación

**Linux / macOS:**
```bash
bash install.sh          # crea .venv e instala las dependencias núcleo
source .venv/bin/activate
```

**Windows** (doble clic en `install.bat`, o en CMD/PowerShell):
```bat
install.bat
.venv\Scripts\activate
```

o manualmente (cualquier sistema):

```bash
python -m venv .venv
# Linux/macOS:  source .venv/bin/activate
# Windows:      .venv\Scripts\activate
pip install -r requirements.txt
```

## Paso 1 — Recolección automática desde repositorios (opcional)

Si no exportas el CSV a mano, `recolector.py` lo descarga por API (OpenAlex, Crossref o PubMed):

```bash
python recolector.py "spinocerebellar ataxia computer vision" -o data/corpus_mra.csv --from-year 2018 --max 200
python recolector.py "heel-shin ataxia gait pose estimation" -o data/corpus_tre.csv --from-year 2018 --max 200
```

Genera un CSV con `title, abstract, year, source, keywords, doi`, listo para el pipeline.
(Requiere conexión a internet; conviene pasar `--email tu@correo.com` como cortesía a las APIs.)

### Paso 1 (alternativa) — Entrada desde ficheros .md del `paper-analyzer-mcp`

Si ya analizaste tus PDF con el MCP y tienes una **carpeta de ficheros `.md`** (uno por paper,
de `deep_analysis`/`search_keywords`), indícala directamente con `--fuente md-mcp`:

```bash
python run_pipeline.py carpeta_md/ --fuente md-mcp -o salida --title "Revisión MCP"
```

El lector (`lector_md_mcp.py`) es tolerante a las variantes del MCP (PICOTS en inglés o
español, calidad en True/False o 0/1, con o sin metadata). De cada `.md` toma el título, el
resumen ejecutivo, el año/DOI/revista (si están), las keywords (explícitas o derivadas de
PICOTS) y el texto semántico (resumen + PICOTS + fortalezas + limitaciones + relevancia), y
añade a la materia prima dos secciones extra a partir del análisis del MCP:
**5b. Cobertura y ausencias** (enfermedades, técnicas y keywords marcadas como ausentes → brecha
*medida*) y **5c. Rigor metodológico del corpus**, que agrega las tablas de calidad de cada
paper (tolerante a True/False o 0/1, inglés o español) en un índice de rigor medio, el
cumplimiento por criterio (ética, datos/código disponibles, validación, aleatorización,
cegamiento, intervalos de confianza, etc.) y las debilidades metodológicas frecuentes. También
puede convertir la carpeta a CSV:

```bash
python lector_md_mcp.py carpeta_md/ -o corpus_mcp.csv
```

## Uso rápido (un solo comando)

```bash
python run_pipeline.py data/sample_corpus.csv -o salida --title "Corpus de ejemplo"
```

Genera en `salida/`: `materia_prima.md`, `red_coocurrencia.png`, `barras_temas.png`.

**Normalización gramatical (Paso 2, opcional):** añade `--lematizar` para lematizar con spaCy
antes de vectorizar (requiere un modelo, p. ej. `python -m spacy download en_core_web_sm`).
Si no hay modelo instalado, el pipeline avisa y continúa sin lematizar.
```bash
python run_pipeline.py data/corpus_mra.csv -o salida_mra --title "Corpus MRA" --lematizar
```

### Ejecutar el ejemplo incluido (corpus real de Web of Science)

El paquete trae un corpus real (`data/wos_miembros_inferiores.csv`, 77 documentos). Con el
entorno activado:

```bash
python run_pipeline.py data/wos_miembros_inferiores.csv -o salida --title "Miembros inferiores (WoS)" --lematizar
```

Deja en `salida/` la `materia_prima.md` y las dos figuras. Como `requirements.txt` ya instala
spaCy y el modelo `en_core_web_sm`, la lematización (`--lematizar`) funciona sin pasos extra.

Para tus dos investigaciones:

```bash
python run_pipeline.py data/corpus_mra.csv -o salida_mra --title "Corpus MRA (miembro superior)"
python run_pipeline.py data/corpus_tre.csv -o salida_tre --title "Corpus TRE (miembro inferior)"
```

### Minería semántica con BERTopic (opcional, recomendado para el corpus completo)

```bash
pip install bertopic sentence-transformers umap-learn hdbscan
python run_pipeline.py data/corpus_mra.csv -o salida_mra --use-bertopic
```

Si BERTopic no está instalado o falla, el pipeline cae automáticamente a **NMF** (offline).

## Scripts individuales

```bash
python mineria_texto.py data/corpus.csv -o materia_prima.md --title "Corpus" --topics 4
python figuras_mineria.py data/corpus.csv -o figs/ --title "Corpus"
```

## Formato del CSV de entrada

Una fila por documento. Las columnas se **autodetectan** (admite nombres en español e
inglés y varias codificaciones). Reconocidas:

| Contenido | Nombres aceptados (ejemplos) |
|---|---|
| Título | `title`, `titulo`, `Document Title`, `Article Title` |
| Resumen | `abstract`, `resumen`, `summary` |
| Año | `year`, `año`, `Publication Year` |
| Fuente | `source`, `Source title`, `journal`, `revista` |
| Palabras clave | `keywords`, `Author Keywords`, `palabras clave` |

Mínimo necesario: **título o resumen**. Exporta directamente de Scopus, Web of Science,
PubMed o IEEE Xplore (CSV con resúmenes).

## Salida

- **`materia_prima.md`** — 7 secciones (resumen del corpus, términos clave, temas con
  documentos representativos, red de co-ocurrencia, intersecciones poco exploradas =
  candidatas a brecha, tendencia temporal, e instrucciones para el LLM).
- **`red_coocurrencia.png`** — red de co-palabras (nodos = términos, aristas = co-ocurrencia).
- **`barras_temas.png`** — términos principales por tema (NMF).

## Paso final: redactar la cuartilla con el LLM (opencode)

Una vez generado `materia_prima.md`, en opencode:

```
Usando el skill redactar-cuartilla-investigacion, analiza salida/materia_prima.md
y redacta la cuartilla.
```

El skill está en `.opencode/skills/` (se descubre automáticamente si abres este
directorio como proyecto en opencode). La guía completa de integración —incluida la
instalación global y la resolución de problemas— está en `docs/INTEGRACION_OPENCODE.md`.

## Cobertura del flujo de conocimiento (5 pasos)

Paso 1 Recolección (`recolector.py`) · Paso 2 Preprocesamiento con limpieza, stopwords y
lematización opcional (`--lematizar`) · Paso 3 Minería y ATE (`key_terms`) · Paso 4 Análisis
(NMF/BERTopic, co-ocurrencia, lift/PMI) · Paso 5 Visualización (`figuras_mineria.py`). Se añade
un Paso 6 de síntesis asistida por LLM mediante el skill.

## Nota de honestidad

El pipeline y el skill están diseñados para **no inventar nada**: la materia prima
contiene solo lo que se extrae del corpus, y el skill obliga al LLM a redactar únicamente
con esa evidencia, marcando como `[VERIFICAR: …]` cualquier dato no disponible.
