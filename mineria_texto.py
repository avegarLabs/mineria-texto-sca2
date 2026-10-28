#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mineria_texto.py — Minería de texto de un corpus bibliográfico (CSV) y generación
de un esqueleto .md con información referencial, pensado como MATERIA PRIMA para que
un modelo LLM redacte una cuartilla de justificación de la investigación.

Flujo: carga del CSV -> preprocesamiento -> representación (TF-IDF / embeddings) ->
minería (temas, términos clave, co-ocurrencia, intersecciones poco exploradas,
tendencia temporal) -> escritura del esqueleto .md.

Algoritmo recomendado: BERTopic (si está instalado; usa embeddings semánticos).
Alternativa offline por defecto: TF-IDF + NMF + extracción de términos (sin descargas).

Uso:
    python mineria_texto.py entrada.csv -o esqueleto.md
    python mineria_texto.py entrada.csv -o esqueleto.md --topics 4 --use-bertopic
    python mineria_texto.py entrada.csv --title "Corpus MRA (miembro superior)"

Requisitos mínimos: pandas, scikit-learn, numpy.
Opcionales (si se usan): bertopic, sentence-transformers, keybert.
"""

import argparse, sys, re, math, datetime
from collections import defaultdict
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer, ENGLISH_STOP_WORDS
from sklearn.decomposition import NMF

# ---------------------------------------------------------------- stopwords
SPANISH_STOP = """a al algo algunas algunos ante antes como con contra cual cuando de del desde donde dos el
ella ellas ellos en entre era erais eran es esa esas ese eso esos esta estas este esto estos fue fueron ha
hace hacia han hasta la las le les lo los mas más me mi mis mucho muy no nos nosotros o os otra otras otro
otros para pero poco por porque que quien se sea sean segun según si sin sobre son su sus tan te tiene
tienen todo todos tu tus un una unas uno unos y ya mediante cada puede pueden ademas además asi así tras
este esta estos estas""".split()
STOPWORDS = set(ENGLISH_STOP_WORDS) | set(SPANISH_STOP) | {
    "study","studies","using","based","results","method","methods","approach","paper","analysis",
    "data","research","new","novel","via","use","used","review","article","assessment"}

# ---------------------------------------------------------------- CSV loading
TITLE_KEYS   = ["title","titulo","título","document title","article title"]
ABSTRACT_KEYS= ["abstract","resumen","summary"]
YEAR_KEYS    = ["year","año","ano","publication year","pub year","fecha"]
SOURCE_KEYS  = ["source","source title","journal","revista","publication","venue"]
KEYWORD_KEYS = ["keywords","author keywords","palabras clave","index keywords"]

def _find_col(cols, keys):
    low = {c.lower().strip(): c for c in cols}
    for k in keys:
        if k in low: return low[k]
    for c in cols:                         # contains match
        cl = c.lower()
        if any(k in cl for k in keys): return c
    return None

def load_csv(path):
    df = None
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc, engine="python", sep=None)  # sep=None -> sniff
            break
        except Exception:
            continue
    if df is None:
        sys.exit(f"[error] no se pudo leer el CSV: {path}")
    cols = list(df.columns)
    col = {
        "title":   _find_col(cols, TITLE_KEYS),
        "abstract":_find_col(cols, ABSTRACT_KEYS),
        "year":    _find_col(cols, YEAR_KEYS),
        "source":  _find_col(cols, SOURCE_KEYS),
        "keywords":_find_col(cols, KEYWORD_KEYS),
    }
    if not col["title"] and not col["abstract"]:
        sys.exit("[error] el CSV no tiene columna de título ni de resumen reconocible.")
    def g(row, k): 
        c = col[k]
        return "" if (c is None or pd.isna(row.get(c, ""))) else str(row.get(c, "")).strip()
    recs = []
    for _, row in df.iterrows():
        title = g(row,"title"); ab,kw = g(row,"abstract"), g(row,"keywords")
        text = " . ".join(x for x in (title, ab, kw) if x)
        if not text.strip(): continue
        year = g(row,"year")
        ym = re.search(r"(19|20)\d{2}", year)
        recs.append({"title":title or "(sin título)","text":text,
                     "year":int(ym.group()) if ym else None,
                     "source":g(row,"source")})
    if not recs:
        sys.exit("[error] no se encontraron documentos con texto.")
    return recs, col

# ---------------------------------------------------------------- preprocessing / vectors
def clean(t):
    t = t.lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[^a-záéíóúñü0-9\s\-]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

_SPACY_CACHE = {}
def _load_spacy(model):
    if model in _SPACY_CACHE:
        return _SPACY_CACHE[model]
    try:
        import spacy
        nlp = spacy.load(model, disable=["parser", "ner"])
    except Exception:
        nlp = None
    _SPACY_CACHE[model] = nlp
    return nlp

def lemmatize_texts(texts, model=None):
    """Normalización gramatical (lematización) con spaCy. Si no hay modelo instalado,
    devuelve el texto sin cambios y avisa (el pipeline sigue funcionando)."""
    candidates = [model] if model else ["en_core_web_sm", "es_core_news_sm"]
    nlp = None
    for m in candidates:
        if not m:
            continue
        nlp = _load_spacy(m)
        if nlp is not None:
            break
    if nlp is None:
        print("[aviso] lematización solicitada pero no hay modelo spaCy; se omite. "
              "Instala, p. ej.: python -m spacy download en_core_web_sm", file=sys.stderr)
        return texts
    out = []
    for doc in nlp.pipe(texts, batch_size=64):
        out.append(" ".join(t.lemma_.lower() for t in doc
                            if not (t.is_stop or t.is_punct or t.is_space or t.like_num)))
    return out

def vectorize(texts, min_df, lemmatize=False, spacy_model=None):
    cleaned = [clean(t) for t in texts]
    if lemmatize:
        cleaned = lemmatize_texts(cleaned, spacy_model)
    n = len(cleaned)
    mdf = min_df if n >= 2*min_df else 1
    tfidf = TfidfVectorizer(ngram_range=(1,2), stop_words=list(STOPWORDS),
                            min_df=mdf, max_df=0.85, token_pattern=r"[a-záéíóúñü][a-záéíóúñü\-]{2,}")
    X = tfidf.fit_transform(cleaned)
    return X, tfidf, cleaned

# ---------------------------------------------------------------- mining pieces
def key_terms(X, tfidf, top=15):
    s = np.asarray(X.sum(0)).ravel()
    terms = np.array(tfidf.get_feature_names_out())
    return list(terms[s.argsort()[::-1][:top]])

def topics_nmf(X, tfidf, recs, k, n_terms=7, n_docs=3):
    k = max(2, min(k, X.shape[0]-1))
    nmf = NMF(n_components=k, init="nndsvda", random_state=1, max_iter=500).fit(X)
    W = nmf.transform(X); terms = np.array(tfidf.get_feature_names_out())
    out = []
    for i, comp in enumerate(nmf.components_):
        tt = list(terms[comp.argsort()[::-1][:n_terms]])
        docs = W[:, i].argsort()[::-1][:n_docs]
        reps = [recs[d] for d in docs if W[d, i] > 0]
        out.append({"label": " / ".join(tt[:3]), "terms": tt, "reps": reps})
    return out, "NMF (TF-IDF)"

def topics_bertopic(cleaned, recs, k=None):
    from bertopic import BERTopic                      # import diferido (opcional)
    nr = k if k else "auto"
    model = BERTopic(language="multilingual", nr_topics=nr, calculate_probabilities=False, verbose=False)
    labels, _ = model.fit_transform(cleaned)
    info = model.get_topic_info()
    out = []
    for tid in info.Topic:
        if tid == -1: continue
        terms = [w for w, _ in model.get_topic(tid)][:7]
        reps_idx = [i for i, l in enumerate(labels) if l == tid][:3]
        out.append({"label": " / ".join(terms[:3]), "terms": terms,
                    "reps": [recs[i] for i in reps_idx]})
    return out, "BERTopic (embeddings + HDBSCAN + c-TF-IDF)"

def cooccurrence(cleaned, top_terms, min_pair=2, max_pairs=12):
    cv = CountVectorizer(vocabulary=[t for t in top_terms if " " not in t] or top_terms,
                         binary=True, ngram_range=(1,2), token_pattern=r"[a-záéíóúñü][a-záéíóúñü\-]{2,}")
    try: B = cv.fit_transform(cleaned)
    except Exception: return [], []
    vocab = np.array(cv.get_feature_names_out())
    C = (B.T @ B).toarray(); fobs = C.diagonal().copy(); np.fill_diagonal(C, 0)
    n = len(cleaned)
    pairs = []
    for i in range(len(vocab)):
        for j in range(i+1, len(vocab)):
            if C[i, j] >= min_pair:
                pairs.append((vocab[i], vocab[j], int(C[i, j])))
    pairs.sort(key=lambda x: -x[2])
    # intersecciones poco exploradas: términos frecuentes por separado, baja co-ocurrencia (lift bajo)
    gaps = []
    for i in range(len(vocab)):
        for j in range(i+1, len(vocab)):
            fi, fj, fij = fobs[i], fobs[j], C[i, j]
            if fi >= max(3, 0.15*n) and fj >= max(3, 0.15*n):
                lift = (fij*n) / (fi*fj + 1e-9)
                if lift < 0.6:
                    gaps.append((vocab[i], vocab[j], int(fi), int(fj), int(fij), round(lift, 2)))
    gaps.sort(key=lambda x: (x[4], x[5]))        # menor co-ocurrencia / menor lift primero
    return pairs[:max_pairs], gaps[:6]

def temporal(recs):
    ys = [r["year"] for r in recs if r["year"]]
    if not ys: return None
    counts = {}
    for y in ys: counts[y] = counts.get(y, 0)+1
    return dict(sorted(counts.items()))

# ---------------------------------------------------------------- markdown output
def md_escape(s): return s.replace("|", "\\|").strip()

def build_md(title, csvpath, recs, col, kts, topics, method, pairs, gaps, years):
    L = []
    now = datetime.date.today().isoformat()
    L.append(f"# Materia prima para redactar la cuartilla — {title}")
    L.append(f"\n_Generado por `mineria_texto.py` a partir de `{csvpath}` el {now}. "
             f"Este documento es un ESQUELETO con evidencia extraída del corpus; "
             f"no es la cuartilla final, sino la materia prima para que un LLM la redacte._\n")

    L.append("## 1. Resumen del corpus")
    L.append(f"- Documentos analizados: **{len(recs)}**")
    if years:
        L.append(f"- Rango temporal: **{min(years)}–{max(years)}**")
    srcs = {}
    for r in recs:
        if r["source"]: srcs[r["source"]] = srcs.get(r["source"], 0)+1
    if srcs:
        top_s = sorted(srcs.items(), key=lambda x:-x[1])[:5]
        L.append("- Fuentes principales: " + "; ".join(f"{md_escape(s)} ({n})" for s, n in top_s))
    used = [k for k, v in col.items() if v]
    L.append(f"- Campos de texto utilizados: {', '.join(used)}")

    L.append("\n## 2. Términos clave (TF-IDF, 1–2 gramas)")
    L.append(", ".join(kts) if kts else "_(ninguno)_")

    L.append(f"\n## 3. Temas detectados — {method}")
    for i, t in enumerate(topics, 1):
        L.append(f"\n### Tema {i} — {md_escape(t['label'])}")
        L.append("- Términos: " + ", ".join(t["terms"]))
        if t["reps"]:
            L.append("- Documentos representativos:")
            for r in t["reps"]:
                meta = ", ".join(x for x in (str(r["year"]) if r["year"] else "", r["source"]) if x)
                L.append(f"  - \"{md_escape(r['title'])}\"" + (f" ({md_escape(meta)})" if meta else ""))

    L.append("\n## 4. Red de co-ocurrencia (pares de términos más frecuentes)")
    if pairs:
        for a, b, c in pairs:
            L.append(f"- {a} — {b}  (co-ocurren en {c} documentos)")
    else:
        L.append("_(sin pares relevantes)_")

    L.append("\n## 5. Intersecciones poco exploradas (candidatas a brecha)")
    if gaps:
        L.append("_Términos frecuentes por separado que rara vez aparecen juntos "
                 "(lift < 0.6) → posibles vacíos de conocimiento a enunciar como brecha._")
        for a, b, fa, fb, fij, lift in gaps:
            L.append(f"- **{a} × {b}**: aparecen en {fa} y {fb} documentos respectivamente, "
                     f"pero co-ocurren solo en {fij} (lift={lift}).")
    else:
        L.append("_(no se detectaron intersecciones claramente infrarrepresentadas; "
                 "formular la brecha a partir de los temas de la sección 3.)_")

    L.append("\n## 6. Tendencia temporal")
    if years:
        L.append("- Publicaciones por año: " + ", ".join(f"{y}: {n}" for y, n in years.items()))
    else:
        L.append("_(el CSV no incluía año de publicación.)_")

    L.append("\n## 7. Instrucciones para el LLM (esqueleto de la cuartilla)")
    L.append(
"""Redacta una **cuartilla** (~250–300 palabras) de justificación de la investigación,
en español y con tono académico, usando ÚNICAMENTE la evidencia de las secciones 1–6.
Sigue esta estructura:

1. **Contexto del problema** — la enfermedad/fenómeno y la limitación del método o escala
   de referencia que motiva el estudio.
2. **Estado del arte sintetizado** — resume en 2–3 frases los temas detectados (sección 3),
   mencionando los términos clave (sección 2) como hilos del campo.
3. **Brecha** — enuncia explícitamente el vacío, apoyándote en las intersecciones poco
   exploradas (sección 5) y en lo ausente entre los temas.
4. **Objetivo** — el objetivo de la investigación que cubre esa brecha.

Reglas:
- No inventes datos, cifras ni citas que no estén en este documento.
- Usa los términos y temas listados; no introduzcas afirmaciones no respaldadas por el corpus.
- Una sola cuartilla, en prosa continua.""")
    return "\n".join(L) + "\n"

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Minería de texto de un CSV -> esqueleto .md para un LLM.")
    ap.add_argument("csv", help="fichero CSV de entrada (con título y/o resumen)")
    ap.add_argument("-o","--output", default="esqueleto_cuartilla.md", help="fichero .md de salida")
    ap.add_argument("-t","--topics", type=int, default=0, help="número de temas (0 = automático)")
    ap.add_argument("--title", default=None, help="nombre descriptivo del corpus")
    ap.add_argument("--min-df", type=int, default=2, help="frecuencia mínima de documento para un término")
    ap.add_argument("--use-bertopic", action="store_true", help="usar BERTopic si está instalado")
    ap.add_argument("--lematizar", action="store_true", help="normalización gramatical (lematización con spaCy)")
    ap.add_argument("--spacy-model", default=None, help="modelo spaCy (p. ej. en_core_web_sm, es_core_news_sm)")
    args = ap.parse_args()

    recs, col = load_csv(args.csv)
    n = len(recs)
    k = args.topics or max(3, min(8, round(n/8)))
    X, tfidf, cleaned = vectorize([r["text"] for r in recs], args.min_df,
                                  lemmatize=args.lematizar, spacy_model=args.spacy_model)
    kts = key_terms(X, tfidf)

    topics, method = None, None
    if args.use_bertopic:
        try:
            topics, method = topics_bertopic(cleaned, recs, k=(args.topics or None))
        except Exception as e:
            print(f"[aviso] BERTopic no disponible o falló ({e}); se usa NMF.", file=sys.stderr)
    if topics is None:
        topics, method = topics_nmf(X, tfidf, recs, k)

    pairs, gaps = cooccurrence(cleaned, kts)
    years = temporal(recs)
    title = args.title or args.csv.rsplit("/",1)[-1]

    md = build_md(title, args.csv, recs, col, kts, topics, method, pairs, gaps, years)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[ok] {n} documentos · {len(topics)} temas ({method}) · salida -> {args.output}")

if __name__ == "__main__":
    main()
