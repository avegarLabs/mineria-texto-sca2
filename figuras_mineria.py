#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
figuras_mineria.py — Genera las figuras de la minería de texto a partir del mismo CSV
que consume mineria_texto.py:
  1) Red de co-ocurrencia de términos (análisis de co-palabras / bibliométrico).
  2) Barras de temas (pesos de los términos principales por tema, NMF).

Reutiliza las funciones de mineria_texto.py (debe estar en la misma carpeta).

Uso:
    python figuras_mineria.py entrada.csv -o figs/ --title "Corpus MRA"
    python figuras_mineria.py entrada.csv -o figs/ --topics 4
"""
import argparse, os, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import NMF

from mineria_texto import load_csv, vectorize, key_terms, cooccurrence

INK="#16314F"; TEAL="#2A9D8F"; AMBER="#E9A23B"; CORAL="#E76F51"; GREY="#6B7785"
plt.rcParams["font.family"]="DejaVu Sans"


def fig_cooccurrence_network(cleaned, kts, out, title):
    """Red de co-ocurrencia: nodos = términos (tamaño ~ frecuencia),
    aristas = co-ocurrencia entre términos (grosor ~ nº de documentos)."""
    import networkx as nx
    from sklearn.feature_extraction.text import CountVectorizer
    single = [t for t in kts if " " not in t] or kts
    cv = CountVectorizer(vocabulary=single, binary=True,
                         token_pattern=r"[a-záéíóúñü][a-záéíóúñü\-]{2,}")
    B = cv.fit_transform(cleaned); vocab = np.array(cv.get_feature_names_out())
    C = (B.T @ B).toarray(); freq = C.diagonal().copy(); np.fill_diagonal(C, 0)

    G = nx.Graph()
    for i, t in enumerate(vocab):
        G.add_node(t, freq=int(freq[i]))
    for i in range(len(vocab)):
        for j in range(i+1, len(vocab)):
            if C[i, j] >= 2:
                G.add_edge(vocab[i], vocab[j], w=int(C[i, j]))
    G.remove_nodes_from([n for n in list(G.nodes) if G.degree(n) == 0])
    if G.number_of_nodes() == 0:
        print("[aviso] red de co-ocurrencia vacía (corpus pequeño); se omite la figura.")
        return None

    fig, ax = plt.subplots(figsize=(9.5, 7.2))
    pos = nx.spring_layout(G, k=0.9, seed=7, weight="w")
    degrees = dict(G.degree())
    sizes = [300 + 520*G.nodes[n]["freq"]/max(1, max(freq)) for n in G.nodes]
    ncolors = [degrees[n] for n in G.nodes]
    widths = [0.6 + 1.9*G[u][v]["w"]/max(1, max(d["w"] for *_ , d in G.edges(data=True)))
              for u, v in G.edges]
    nx.draw_networkx_edges(G, pos, width=widths, edge_color=GREY, alpha=0.45, ax=ax)
    nodes = nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=ncolors,
                                   cmap="YlGnBu", edgecolors=INK, linewidths=1.2, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=9, font_color=INK, ax=ax)
    cb = fig.colorbar(nodes, ax=ax, fraction=0.035, pad=0.02); cb.set_label("grado (conexiones)", fontsize=9)
    ax.set_title(f"Red de co-ocurrencia de términos — {title}", fontsize=12.5, fontweight="bold", color=INK)
    ax.axis("off")
    p = os.path.join(out, "red_coocurrencia.png")
    plt.tight_layout(); plt.savefig(p, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    return p


def fig_topic_bars(X, tfidf, k, out, title, n_terms=6):
    """Barras de temas: por cada tema NMF, los términos principales y su peso."""
    k = max(2, min(k, X.shape[0]-1))
    nmf = NMF(n_components=k, init="nndsvda", random_state=1, max_iter=500).fit(X)
    terms = np.array(tfidf.get_feature_names_out())
    cols = [TEAL, AMBER, CORAL, "#6A4C93", "#2E7D5B", "#B5322A", "#C77A1F", "#1F6FB0"]
    ncols = 2; nrows = int(np.ceil(k/ncols))
    fig, axs = plt.subplots(nrows, ncols, figsize=(11, 2.5*nrows), squeeze=False)
    for i in range(nrows*ncols):
        ax = axs[i//ncols][i % ncols]
        if i >= k: ax.axis("off"); continue
        comp = nmf.components_[i]; idx = comp.argsort()[::-1][:n_terms]
        tt = terms[idx][::-1]; vv = comp[idx][::-1]
        ax.barh(range(len(tt)), vv, color=cols[i % len(cols)], zorder=3)
        ax.set_yticks(range(len(tt))); ax.set_yticklabels(tt, fontsize=9.5, color=INK)
        ax.set_title(f"Tema {i+1}: {' / '.join(terms[idx][:3])}", fontsize=10.5, fontweight="bold", color=INK)
        ax.set_xlabel("peso (NMF)", fontsize=8.5); ax.grid(axis="x", alpha=0.25, zorder=0)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
        for s in ("left", "bottom"): ax.spines[s].set_color(GREY)
    fig.suptitle(f"Temas detectados (NMF) — {title}", fontsize=13, fontweight="bold", color=INK, y=1.0)
    p = os.path.join(out, "barras_temas.png")
    plt.tight_layout(rect=[0, 0, 1, 0.98]); plt.savefig(p, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    return p


def main():
    ap = argparse.ArgumentParser(description="Figuras de la minería de texto (red de co-ocurrencia + barras de temas).")
    ap.add_argument("csv")
    ap.add_argument("-o", "--outdir", default="figs")
    ap.add_argument("-t", "--topics", type=int, default=0)
    ap.add_argument("--min-df", type=int, default=2)
    ap.add_argument("--title", default=None)
    ap.add_argument("--lematizar", action="store_true")
    ap.add_argument("--spacy-model", default=None)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    recs, _ = load_csv(args.csv)
    n = len(recs); k = args.topics or max(3, min(8, round(n/8)))
    X, tfidf, cleaned = vectorize([r["text"] for r in recs], args.min_df,
                                  lemmatize=args.lematizar, spacy_model=args.spacy_model)
    kts = key_terms(X, tfidf, top=18)
    title = args.title or args.csv.rsplit("/", 1)[-1]

    p1 = fig_cooccurrence_network(cleaned, kts, args.outdir, title)
    p2 = fig_topic_bars(X, tfidf, k, args.outdir, title)
    print(f"[ok] figuras -> {p1}  |  {p2}")


if __name__ == "__main__":
    main()
