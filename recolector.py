#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recolector.py — Paso 1 del flujo (Recopilación): ingesta automática de literatura
científica desde repositorios vía API, hacia un CSV compatible con el pipeline.

Fuentes soportadas (sin clave de API):
  - openalex   (https://api.openalex.org)        [por defecto; cobertura amplia]
  - crossref   (https://api.crossref.org)
  - pubmed     (NCBI E-utilities; biomédico)

Salida: un CSV con columnas  title, abstract, year, source, keywords, doi
que consumen directamente mineria_texto.py / run_pipeline.py.

Uso:
    python recolector.py "spinocerebellar ataxia computer vision" -o data/corpus_mra.csv --max 200
    python recolector.py "heel-shin ataxia gait pose estimation" -o data/corpus_tre.csv \
           --source openalex --from-year 2018 --max 300
    python recolector.py "ataxia" -o data/pm.csv --source pubmed --email tu@correo.com

Requiere: requests (incluido en requirements.txt).
"""
import argparse, csv, sys, time, re
import requests

UA = {"User-Agent": "mineria-texto-sca2/1.0 (investigacion; mailto:%s)"}


# ----------------------------------------------------------------- OpenAlex
def fetch_openalex(query, max_n, from_year, mailto):
    out, per = [], 200
    cursor = "*"
    base = "https://api.openalex.org/works"
    while len(out) < max_n:
        params = {
            "search": query,
            "per-page": min(per, max_n - len(out)),
            "cursor": cursor,
            "mailto": mailto or "anon@example.org",
        }
        filt = "has_abstract:true"
        if from_year:
            filt += f",from_publication_date:{from_year}-01-01"
        params["filter"] = filt
        r = requests.get(base, params=params, headers={"User-Agent": UA["User-Agent"] % (mailto or "anon")}, timeout=30)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            break
        for w in results:
            out.append({
                "title": w.get("title") or "",
                "abstract": _openalex_abstract(w.get("abstract_inverted_index")),
                "year": w.get("publication_year") or "",
                "source": (((w.get("primary_location") or {}).get("source") or {}).get("display_name")) or "",
                "keywords": "; ".join(c.get("display_name", "") for c in (w.get("concepts") or [])[:6]),
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            })
        cursor = (data.get("meta") or {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.2)
    return out[:max_n]


def _openalex_abstract(inv):
    """Reconstruye el abstract desde el inverted index de OpenAlex."""
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


# ----------------------------------------------------------------- Crossref
def fetch_crossref(query, max_n, from_year, mailto):
    out, rows = [], 100
    base = "https://api.crossref.org/works"
    offset = 0
    while len(out) < max_n:
        params = {"query": query, "rows": min(rows, max_n - len(out)), "offset": offset,
                  "select": "title,abstract,issued,container-title,subject,DOI",
                  "mailto": mailto or "anon@example.org"}
        if from_year:
            params["filter"] = f"from-pub-date:{from_year}-01-01"
        r = requests.get(base, params=params, headers={"User-Agent": UA["User-Agent"] % (mailto or "anon")}, timeout=30)
        r.raise_for_status()
        items = (r.json().get("message") or {}).get("items", [])
        if not items:
            break
        for it in items:
            ab = re.sub(r"<[^>]+>", " ", it.get("abstract", "") or "").strip()
            yr = ""
            try:
                yr = (it.get("issued", {}).get("date-parts", [[None]])[0][0]) or ""
            except Exception:
                pass
            out.append({
                "title": " ".join(it.get("title", []) or []),
                "abstract": ab,
                "year": yr,
                "source": " ".join(it.get("container-title", []) or []),
                "keywords": "; ".join(it.get("subject", []) or []),
                "doi": it.get("DOI", ""),
            })
        offset += rows
        time.sleep(0.3)
    return out[:max_n]


# ----------------------------------------------------------------- PubMed (E-utilities)
def fetch_pubmed(query, max_n, from_year, email):
    eu = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    term = query + (f" AND {from_year}:3000[dp]" if from_year else "")
    s = requests.get(f"{eu}/esearch.fcgi", params={
        "db": "pubmed", "term": term, "retmax": max_n, "retmode": "json",
        "email": email or "anon@example.org"}, timeout=30)
    s.raise_for_status()
    ids = (s.json().get("esearchresult") or {}).get("idlist", [])
    out = []
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        f = requests.get(f"{eu}/efetch.fcgi", params={
            "db": "pubmed", "id": ",".join(batch), "retmode": "xml",
            "email": email or "anon@example.org"}, timeout=60)
        f.raise_for_status()
        out.extend(_parse_pubmed_xml(f.text))
        time.sleep(0.4)
    return out[:max_n]


def _parse_pubmed_xml(xml):
    import xml.etree.ElementTree as ET
    recs = []
    try:
        root = ET.fromstring(xml)
    except Exception:
        return recs
    for art in root.findall(".//PubmedArticle"):
        t = art.findtext(".//ArticleTitle") or ""
        ab = " ".join(e.text or "" for e in art.findall(".//Abstract/AbstractText"))
        yr = art.findtext(".//JournalIssue/PubDate/Year") or ""
        src = art.findtext(".//Journal/Title") or ""
        kws = "; ".join(e.text or "" for e in art.findall(".//MeshHeading/DescriptorName"))
        doi = ""
        for idn in art.findall(".//ArticleId"):
            if idn.get("IdType") == "doi":
                doi = idn.text or ""
        recs.append({"title": t, "abstract": ab, "year": yr, "source": src, "keywords": kws, "doi": doi})
    return recs


FETCHERS = {"openalex": fetch_openalex, "crossref": fetch_crossref, "pubmed": fetch_pubmed}


def main():
    ap = argparse.ArgumentParser(description="Recolección de literatura por API -> CSV (Paso 1).")
    ap.add_argument("query", help="consulta de búsqueda (texto o cadena booleana)")
    ap.add_argument("-o", "--output", default="corpus.csv", help="CSV de salida")
    ap.add_argument("-s", "--source", default="openalex", choices=list(FETCHERS), help="repositorio/API")
    ap.add_argument("--max", type=int, default=200, help="máximo de registros")
    ap.add_argument("--from-year", type=int, default=None, help="año mínimo de publicación")
    ap.add_argument("--email", default=None, help="correo (cortesía para OpenAlex/Crossref/PubMed)")
    args = ap.parse_args()

    print(f">> Recolectando de {args.source}: \"{args.query}\" (máx {args.max}) ...", file=sys.stderr)
    try:
        recs = FETCHERS[args.source](args.query, args.max, args.from_year, args.email)
    except requests.RequestException as e:
        sys.exit(f"[error] fallo de red/API: {e}")
    recs = [r for r in recs if (r["title"] or r["abstract"]).strip()]
    if not recs:
        sys.exit("[error] sin resultados; prueba otra consulta o repositorio.")
    cols = ["title", "abstract", "year", "source", "keywords", "doi"]
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in recs:
            w.writerow({k: r.get(k, "") for k in cols})
    print(f"[ok] {len(recs)} registros -> {args.output}")
    print(f"     siguiente: python run_pipeline.py {args.output} -o salida --title \"{args.query}\"")


if __name__ == "__main__":
    main()
