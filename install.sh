#!/usr/bin/env bash
# Instalación del entorno para el pipeline de minería de texto.
set -e

echo ">> Creando entorno virtual (.venv) ..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo ">> Actualizando pip e instalando dependencias (núcleo) ..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Listo. Para empezar:"
echo "  source .venv/bin/activate"
echo "  python run_pipeline.py data/corpus.csv -o salida --title \"Mi corpus\""
echo ""
echo "(Opcional) Minería semántica con BERTopic:"
echo "  pip install bertopic sentence-transformers umap-learn hdbscan"
echo "  python run_pipeline.py data/corpus.csv -o salida --use-bertopic"
