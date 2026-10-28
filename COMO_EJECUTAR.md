# Cómo ejecutar el proyecto — guía paso a paso

Pipeline de minería de texto: toma un **CSV** bibliográfico o una **carpeta de ficheros `.md`**
del `paper-analyzer-mcp`, extrae la evidencia (términos, temas, co-ocurrencia, brechas, rigor)
y produce una `materia_prima.md` que un LLM (vía el skill en opencode) convierte en una cuartilla.

---

## 1. Preparación (una sola vez)

Descomprime el ZIP, entra en la carpeta e instala las dependencias.

**Linux / macOS**
```bash
unzip mineria-texto-sca2.zip
cd mineria-texto-sca2
bash install.sh
source .venv/bin/activate
```

**Windows (CMD / PowerShell)**
```bat
cd mineria-texto-sca2
install.bat
.venv\Scripts\activate
```

`install.sh` / `install.bat` crea el entorno virtual `.venv` e instala todo, incluido spaCy y el
modelo `en_core_web_sm` (necesario para `--lematizar`). Cuando el entorno esté activo verás
`(.venv)` al inicio de la línea de comandos.

> Activa siempre el entorno antes de ejecutar: `source .venv/bin/activate` (Linux/macOS) o
> `.venv\Scripts\activate` (Windows).

---

## 2. Ejemplo A — Minería desde un CSV

Coloca tu corpus exportado (p. ej. de Web of Science, con resúmenes) en `data/`, por ejemplo
`data/wos_miembros_inferiores.csv`. El repositorio no incluye datos.

```bash
python run_pipeline.py data/wos_miembros_inferiores.csv -o salida_csv --title "Miembros inferiores (WoS)" --lematizar
```

Genera en `salida_csv/`:
- `materia_prima.md` — resumen del corpus, términos clave (ATE), temas, red de co-ocurrencia,
  intersecciones poco exploradas (candidatas a brecha) y tendencia temporal.
- `red_coocurrencia.png` y `barras_temas.png`.

Con tu propio CSV (exportado de Scopus, Web of Science, PubMed o IEEE, **con resúmenes**):
```bash
python run_pipeline.py data/mi_corpus.csv -o salida_csv --title "Mi corpus"
```

Las columnas se autodetectan (título, resumen, año, fuente, palabras clave), en español o inglés.

---

## 3. Ejemplo B — Minería desde los ficheros `.md` del MCP

Necesitas una **carpeta con los `.md`** que generó tu `paper-analyzer-mcp` (uno por paper).
Supongamos que están en `~/research/analisis_md/`.

```bash
python run_pipeline.py ~/research/analisis_md --fuente md-mcp -o salida_mcp --title "Revisión MCP"
```

La entrada es **la carpeta** (no un fichero), y `--fuente md-mcp` activa el lector. En
`salida_mcp/materia_prima.md` obtienes lo mismo que con el CSV **más dos secciones extra**:
- **5b. Cobertura y ausencias** — enfermedades, técnicas y keywords marcadas como ausentes por
  el MCP (brecha *medida*).
- **5c. Rigor metodológico del corpus** — índice de rigor medio, cumplimiento por criterio
  (ética, datos/código disponibles, validación, aleatorización, cegamiento, intervalos de
  confianza, etc.) y debilidades metodológicas frecuentes.

El lector es tolerante a las variantes del MCP (PICOTS en inglés o español; calidad en
True/False o 0/1).

Variante en dos pasos (para inspeccionar el corpus intermedio):
```bash
python lector_md_mcp.py ~/research/analisis_md -o corpus_mcp.csv
python run_pipeline.py corpus_mcp.csv -o salida_mcp --title "Revisión MCP"
```

---

## 4. (Opcional) Recolectar el CSV por API

Si no exportas el CSV a mano, lo descargas por API (OpenAlex, Crossref o PubMed):

```bash
python recolector.py "spinocerebellar ataxia computer vision" -o data/corpus.csv --from-year 2018 --max 200 --email tu@correo.com
```

Requiere conexión a internet. Luego sigues con el Ejemplo A sobre `data/corpus.csv`.

---

## 5. Paso final (ambos ejemplos) — redactar la cuartilla

Al terminar, el pipeline imprime la instrucción exacta. En **opencode**, abre la carpeta del
proyecto (el skill en `.opencode/skills/` se descubre automáticamente) y pide:

```
Usando el skill redactar-cuartilla-investigacion, analiza salida_csv/materia_prima.md y redacta la cuartilla.
```

(o `salida_mcp/materia_prima.md` para el Ejemplo B). El modelo leerá la materia prima y devolverá
la cuartilla más una nota de trazabilidad, sin inventar datos ni citas. La guía de integración del
skill está en `docs/INTEGRACION_OPENCODE.md`.

---

## Resumen de comandos

| Caso | Comando |
|---|---|
| CSV | `python run_pipeline.py data/wos_miembros_inferiores.csv -o salida_csv --title "..." --lematizar` |
| Carpeta de `.md` | `python run_pipeline.py CARPETA_MD --fuente md-mcp -o salida_mcp --title "..."` |
| Convertir `.md` → CSV | `python lector_md_mcp.py CARPETA_MD -o corpus_mcp.csv` |
| Recolectar por API → CSV | `python recolector.py "consulta" -o data/corpus.csv --from-year 2018` |

### Opciones útiles (cualquiera de los dos modos)

| Opción | Efecto |
|---|---|
| `--title "..."` | nombre descriptivo del corpus en la materia prima |
| `--topics N` | número de temas fijo (por defecto, automático) |
| `--lematizar` | normalización gramatical (lematización con spaCy) |
| `--use-bertopic` | minería semántica con BERTopic (si está instalado; si no, usa NMF) |
| `--no-figures` | no generar las imágenes |
| `--min-df N` | frecuencia mínima de documento para un término |

---

## Notas prácticas

- Activa el entorno virtual antes de cada sesión (`source .venv/bin/activate` o `.venv\Scripts\activate`).
- El núcleo funciona **sin conexión**; solo `recolector.py` (API) y, la primera vez, la descarga
  del modelo spaCy requieren internet.
- Con **pocos documentos (2–3)** la co-ocurrencia y los temas salen pobres: el flujo luce con
  decenas de papers.
- Con `--lematizar` los términos aparecerán lematizados (p. ej. *patients → patient*), con ligeras
  diferencias frente a una corrida sin lematizar.
- Si la versión de spaCy no casa con el modelo, usa: `python -m spacy download en_core_web_sm`.
