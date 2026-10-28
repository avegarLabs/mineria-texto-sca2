#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lector_md_mcp.py — Lector de los ficheros .md generados por paper-analyzer-mcp.

Toma una CARPETA con los .md de análisis (uno por paper) y los convierte en el mismo
formato interno que consume el pipeline de minería (un "documento" = un paper). Es
tolerante a las variantes del MCP: claves PICOTS en inglés o español, calidad en
True/False o 0/1, con o sin metadata (año/DOI/revista).

De cada .md extrae:
  - title     : del encabezado '#' (sin prefijos "Deep Analysis:" / "Análisis Detallado:")
  - abstract  : sección "Resumen ejecutivo"
  - year/doi/source/keywords : del bloque PICOTS si existen (si no, se dejan vacíos)
  - text      : resumen + valores PICOTS + fortalezas + limitaciones + relevancia
                (todo lo semántico que ya destiló el LLM en el .md)
Además recopila señales de cobertura/ausencia (enfermedad, herramienta CV, modelo ML,
keywords marcadas como "0 menciones"/"sin coincidencia") para la materia prima.

Uso directo (convierte a CSV compatible con el pipeline):
    python lector_md_mcp.py carpeta_md/ -o corpus_mcp.csv

También se usa como módulo desde run_pipeline.py (--fuente md-mcp).
"""
import argparse, csv, os, re, glob, sys, unicodedata

TITLE_PREFIXES = re.compile(r"^\s*(deep analysis|análisis detallado|analisis detallado|"
                            r"deep_analysis|resultados de búsqueda de keywords[^:]*)\s*:\s*",
                            re.IGNORECASE)

# claves PICOTS -> campo normalizado (acepta inglés y español)
PICOTS_MAP = {
    "year": "year", "año": "year", "ano": "year",
    "doi": "doi",
    "source": "source", "revista": "source", "journal": "source",
    "keywords": "keywords", "palabras clave": "keywords", "author keywords": "keywords",
    "disease": "_disease", "enfermedad": "_disease",
    "cv_tool": "_cv", "instrumento de recolección": "_cv", "sensors": "_cv",
    "ml_model": "_ml", "metodología ml": "_ml", "modelos comparados": "_ml",
    "motor_task": "_task", "tarea motora": "_task",
    "título": "_titlemeta", "title": "_titlemeta",
}

ABSENT_RE = re.compile(r"(?:sin coincidencia|0 menciones|sin menci|no se reporta|"
                       r"ausencia|no enfocado|not found)", re.IGNORECASE)

def _norm(s):
    """minúsculas sin acentos."""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()

# Criterio canónico (etiqueta de salida) -> patrones (normalizados, EN/ES)
QUALITY_MAP = [
    ("Tamaño de muestra reportado", ["sample size", "muestra report", "tamano de muestra"]),
    ("Grupo control", ["control"]),
    ("Aleatorización", ["random", "aleator"]),
    ("Cegamiento", ["blind", "cegad"]),
    ("Método de validación", ["validation", "validacion"]),
    ("Pruebas estadísticas", ["statistical", "estadistic"]),
    ("Intervalos de confianza", ["confidence interval", "intervalos conf", "intervalo de conf"]),
    ("Limitaciones discutidas", ["limitation", "limitacion"]),
    ("Aprobación ética", ["ethic", "etica"]),
    ("Datos disponibles", ["data available", "datos dispon"]),
    ("Código disponible", ["code available", "codigo dispon"]),
    ("Conflicto de interés declarado", ["conflict", "conflicto"]),
    ("Financiación declarada", ["funding", "financ"]),
]

def _map_quality(criterion):
    c = _norm(criterion)
    for canon, pats in QUALITY_MAP:
        if any(p in c for p in pats):
            return canon
    return None

def _score(v):
    """True/1/sí -> 1 ; False/0/no -> 0 ; otro -> None (no evaluable como booleano)."""
    t = _norm(v)
    if t in ("true", "1", "si", "yes", "verdadero"):
        return 1
    if t in ("false", "0", "no", "falso"):
        return 0
    return None

def _parse_quality(block):
    q = {}
    for line in block.splitlines():
        if line.count("|") < 2:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        crit, val = cells[0], cells[1]
        if _norm(crit) in ("criterio", "") or set(crit) <= {"-", " "}:
            continue
        canon = _map_quality(crit)
        sc = _score(val)
        if canon and sc is not None:
            q[canon] = sc
    return q


def _read(path):
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return open(path, encoding=enc).read()
        except Exception:
            continue
    return ""


def _section(md, name):
    """Devuelve el cuerpo de una sección '## name' hasta el siguiente '## '."""
    m = re.search(rf"^##\s*{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", md,
                  re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _section_fuzzy(md, *names):
    for n in names:
        m = re.search(rf"^##\s*[^\n]*{re.escape(n)}[^\n]*$(.*?)(?=^##\s|\Z)", md,
                      re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if m:
            return m.group(1).strip()
    return ""


def _parse_picots(block):
    """Lee una tabla markdown | campo | valor | -> dict normalizado + crudo."""
    fields, raw = {}, {}
    for line in block.splitlines():
        if line.count("|") < 2:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        k, v = cells[0].lower(), cells[1]
        if k in ("campo", "---", "") or set(k) <= {"-", " "}:
            continue
        raw[k] = v
        if k in PICOTS_MAP:
            fields[PICOTS_MAP[k]] = v
    return fields, raw


def parse_md(path):
    md = _read(path)
    if not md.strip():
        return None
    # título
    h1 = re.search(r"^\s*#\s+(.+)$", md, re.MULTILINE)
    title = TITLE_PREFIXES.sub("", h1.group(1)).strip() if h1 else os.path.basename(path)

    resumen = _section_fuzzy(md, "Resumen ejecutivo", "Resumen")
    pic_block = _section_fuzzy(md, "Datos del estudio", "PICOTS")
    fields, raw = _parse_picots(pic_block)
    fort = _section_fuzzy(md, "Fortalezas")
    limit = _section_fuzzy(md, "Limitaciones")
    relev = _section_fuzzy(md, "Relevancia para la investigación", "Relevancia")
    quality = _parse_quality(_section_fuzzy(md, "Evaluación de calidad", "Evaluacion de calidad", "quality"))

    # título de metadata si el H1 era un nombre de fichero
    if (title.lower().endswith(".pdf") or re.fullmatch(r"\d+\.pdf", title, re.I)) and fields.get("_titlemeta"):
        title = fields["_titlemeta"]

    # keywords: explícitas o derivadas de PICOTS semántico
    kws = fields.get("keywords", "")
    if not kws:
        kws = "; ".join(x for x in (fields.get("_disease"), fields.get("_cv"),
                                    fields.get("_ml"), fields.get("_task")) if x)

    # texto para minería: todo lo semántico destilado por el LLM
    text = " . ".join(x for x in (
        title, resumen,
        fields.get("_disease", ""), fields.get("_cv", ""), fields.get("_ml", ""),
        fields.get("_task", ""), kws, fort, limit, relev) if x)

    # señales de cobertura / ausencia
    disease = fields.get("_disease", "")
    cv = fields.get("_cv", "")
    absent = [raw_k for raw_k, raw_v in raw.items() if ABSENT_RE.search(raw_v)]

    return {
        "title": title or os.path.basename(path),
        "abstract": resumen,
        "text": text,
        "year": re.sub(r"\D", "", fields.get("year", ""))[:4],
        "source": fields.get("source", ""),
        "keywords": kws,
        "doi": fields.get("doi", ""),
        "_disease": disease, "_cv": cv, "_absent": absent, "_quality": quality,
        "_file": os.path.basename(path),
    }


def load_mcp_folder(folder):
    """Devuelve (recs, col, coverage) listos para el pipeline."""
    paths = sorted(glob.glob(os.path.join(folder, "*.md")))
    if not paths:
        sys.exit(f"[error] no se encontraron ficheros .md en: {folder}")
    recs = []
    for p in paths:
        r = parse_md(p)
        if r and (r["text"].strip()):
            recs.append(r)
    if not recs:
        sys.exit("[error] los .md no contenían texto analizable.")
    # coverage: enfermedad x herramienta + ausencias agregadas
    cov = {"disease": {}, "cv": {}, "absent": {}, "quality": {}, "rigor": []}
    for r in recs:
        if r["_disease"]:
            cov["disease"][r["_disease"]] = cov["disease"].get(r["_disease"], 0) + 1
        if r["_cv"]:
            cov["cv"][r["_cv"]] = cov["cv"].get(r["_cv"], 0) + 1
        for a in r["_absent"]:
            cov["absent"][a] = cov["absent"].get(a, 0) + 1
        q = r.get("_quality", {})
        if q:
            cov["rigor"].append(sum(q.values()) / len(q))
            for k, v in q.items():
                cell = cov["quality"].setdefault(k, [0, 0])
                cell[0] += v; cell[1] += 1
    col = {"title": "title", "abstract": "abstract", "year": "year",
           "source": "source", "keywords": "keywords"}
    return recs, col, cov


def coverage_markdown(cov, n):
    """Sección extra de materia prima: cobertura y ausencias (propio del MCP)."""
    L = ["\n## 5b. Cobertura y ausencias (extraído del análisis MCP)"]
    if cov["disease"]:
        top = sorted(cov["disease"].items(), key=lambda x: -x[1])
        L.append("- Enfermedades cubiertas: " + "; ".join(f"{k} ({v})" for k, v in top))
    if cov["cv"]:
        top = sorted(cov["cv"].items(), key=lambda x: -x[1])[:8]
        L.append("- Herramientas / técnicas: " + "; ".join(f"{k} ({v})" for k, v in top))
    if cov["absent"]:
        top = sorted(cov["absent"].items(), key=lambda x: -x[1])[:10]
        L.append("- Ausencias señaladas por el MCP (candidatas a brecha, nº de papers): "
                 + "; ".join(f"{k} ({v})" for k, v in top))
    if len(L) == 1:
        L.append("_(sin señales de cobertura/ausencia en los .md.)_")

    if cov.get("quality"):
        L.append("\n## 5c. Rigor metodológico del corpus (de las tablas de calidad del MCP)")
        if cov.get("rigor"):
            mean = sum(cov["rigor"]) / len(cov["rigor"])
            L.append(f"- Índice de rigor medio: **{mean*100:.0f}%** de los criterios de calidad "
                     f"cumplidos por paper (n={len(cov['rigor'])}).")
        rows = sorted(cov["quality"].items(), key=lambda x: -(x[1][0] / x[1][1]))
        L.append("- Cumplimiento por criterio (papers que lo cumplen / evaluados):")
        for k, (met, ass) in rows:
            L.append(f"  - {k}: {met}/{ass} ({100*met/ass:.0f}%)")
        weak = [k for k, (met, ass) in cov["quality"].items() if ass >= 2 and met / ass < 0.5]
        if weak:
            L.append("- Debilidades metodológicas frecuentes del corpus (candidatas a señalar en la discusión): "
                     + "; ".join(weak))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Carpeta de .md del MCP -> CSV compatible con el pipeline.")
    ap.add_argument("folder", help="carpeta con los .md generados por paper-analyzer-mcp")
    ap.add_argument("-o", "--output", default="corpus_mcp.csv")
    args = ap.parse_args()
    recs, _, cov = load_mcp_folder(args.folder)
    cols = ["title", "abstract", "year", "source", "keywords", "doi"]
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in recs:
            w.writerow({k: r.get(k, "") for k in cols})
    print(f"[ok] {len(recs)} ficheros .md -> {args.output}")
    if cov["disease"] or cov["cv"] or cov["absent"]:
        print("     cobertura detectada:",
              f"{len(cov['disease'])} enfermedades, {len(cov['cv'])} técnicas, "
              f"{len(cov['absent'])} ausencias.")


if __name__ == "__main__":
    main()
