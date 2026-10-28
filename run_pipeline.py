#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_pipeline.py — Pipeline completo de minería de texto para un corpus CSV.

Ejecuta en un solo paso:
  1) la minería (mineria_texto.py) -> materia_prima.md
  2) las figuras (figuras_mineria.py) -> red_coocurrencia.png + barras_temas.png

y deja todo en una carpeta de salida por corpus, lista para que un LLM (vía el skill
'redactar-cuartilla-investigacion' en opencode) redacte la cuartilla.

Uso:
    python run_pipeline.py data/sample_corpus.csv -o salida --title "Corpus MRA"
    python run_pipeline.py corpus_tre.csv -o salida_tre --topics 4 --use-bertopic
"""
import argparse, os, sys
from mineria_texto import (load_csv, vectorize, key_terms, topics_nmf, topics_bertopic,
                           cooccurrence, temporal, build_md)
from figuras_mineria import fig_cooccurrence_network, fig_topic_bars
from lector_md_mcp import load_mcp_folder, coverage_markdown


def main():
    ap = argparse.ArgumentParser(description="Pipeline: CSV -> materia_prima.md + figuras.")
    ap.add_argument("entrada", help="CSV de entrada, o CARPETA de .md si --fuente md-mcp")
    ap.add_argument("--fuente", choices=["csv", "md-mcp"], default="csv",
                    help="origen: csv (por defecto) o md-mcp (carpeta de .md del paper-analyzer-mcp)")
    ap.add_argument("-o", "--outdir", default="salida", help="carpeta de salida")
    ap.add_argument("-t", "--topics", type=int, default=0, help="nº de temas (0 = automático)")
    ap.add_argument("--title", default=None, help="nombre descriptivo del corpus")
    ap.add_argument("--min-df", type=int, default=2)
    ap.add_argument("--use-bertopic", action="store_true", help="usar BERTopic si está instalado")
    ap.add_argument("--lematizar", action="store_true", help="normalización gramatical (lematización con spaCy)")
    ap.add_argument("--spacy-model", default=None, help="modelo spaCy (en_core_web_sm, es_core_news_sm)")
    ap.add_argument("--no-figures", action="store_true", help="omitir las figuras")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    if args.fuente == "md-mcp":
        recs, col, cov = load_mcp_folder(args.entrada)
    else:
        recs, col = load_csv(args.entrada); cov = None
    n = len(recs)
    k = args.topics or max(3, min(8, round(n / 8)))
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
    title = args.title or os.path.basename(args.entrada)

    md = build_md(title, args.entrada, recs, col, kts, topics, method, pairs, gaps, years)
    if cov is not None:
        cov_md = coverage_markdown(cov, len(recs))
        if "\n## 6. Tendencia temporal" in md:
            md = md.replace("\n## 6. Tendencia temporal", cov_md + "\n\n## 6. Tendencia temporal", 1)
        else:
            md += "\n" + cov_md + "\n"
    md_path = os.path.join(args.outdir, "materia_prima.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    figs = []
    if not args.no_figures:
        p1 = fig_cooccurrence_network(cleaned, kts, args.outdir, title)
        p2 = fig_topic_bars(X, tfidf, k, args.outdir, title)
        figs = [p for p in (p1, p2) if p]

    print(f"\n[ok] {n} documentos · {len(topics)} temas ({method})")
    print(f"      materia prima -> {md_path}")
    for f in figs:
        print(f"      figura        -> {f}")
    print("\nSiguiente paso (en opencode):")
    print(f'  "Usando el skill redactar-cuartilla-investigacion, analiza {md_path} '
          f'y redacta la cuartilla."')


if __name__ == "__main__":
    main()
