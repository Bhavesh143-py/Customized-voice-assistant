## Setup
pip install -r requirements.txt
ollama serve
ollama pull nomic-embed-text

## Build Vector DB
python chunking.py

## Query
python query.py

