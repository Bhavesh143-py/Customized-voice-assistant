# How to Run

## 1. Install dependencies

```bash
pip install -r requirements.txt
```
---

## 2. Start Ollama

Pull models used in the script (not needed if already pulled)

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

Run Ollama service if not already running:

```bash
ollama serve
```

---

## 3. Project Structure

```
agentic_chunker.py
chunking.py
requirements.txt
scraped_text/

```

Text files inside `scraped_text/` are used as the knowledge base.

---
---

## 4. Run the pipeline

Execute the RAG script:

```bash
python chunking.py
```

---

## Notes
* Embeddings: `nomic-embed-text`
* LLM: `qwen2.5:3b`

