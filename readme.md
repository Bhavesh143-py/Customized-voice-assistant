# AI Voice RAG

This document explains how to run the project locally on Windows: start an Ollama model instance (Qwen 3B), start a Qdrant vector database via Docker, then run the app inside a Python virtual environment.

## Prerequisites
- Python 3.9+ installed and on PATH
- Docker Desktop (or docker CLI) installed and running
- Ollama installed and configured (see https://ollama.com for installers and docs)

Note: The project expects Ollama to be reachable on the default local endpoint and Qdrant on `http://localhost:6333`.

## 1) Start Ollama and ensure the Qwen 3B model is available
1. If you haven't installed Ollama, follow the official instructions at https://ollama.com.
2. Pull the model used by this project (RagAssistant references `qwen2.5:3b`):

```powershell
ollama pull qwen2.5:3b
```

3. Start the Ollama daemon (serves models locally). In a terminal run:

```powershell
ollama serve
```

Keep this terminal open (or run it in the background). The project uses the `Ollama` LLM class configured for model `qwen2.5:3b`.

## 2) Start Qdrant (Docker)
Run Qdrant using Docker. This command maps the default REST port and persists storage to a named volume:

```powershell
# pulls the qdrant image (if needed) and runs it
docker run -d \
  --name qdrant_local \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

Verify Qdrant is up by visiting: `http://localhost:6333` or using `curl http://localhost:6333/`.

The code in `Backend/RagAssistant.py` expects Qdrant at `http://localhost:6333` and uses `prefer_grpc=False`.

## 3) Create and activate Python virtual environment, install deps
1. From project root, create a venv and activate it (PowerShell):

```powershell
python -m venv venv
# PowerShell activation
.\venv\Scripts\Activate.ps1
# (or for cmd.exe) .\venv\Scripts\activate.bat
```

2. Install required Python packages:

```powershell
pip install -r requirements.txt
```

## 4) Run the application
With Ollama serving and Qdrant running, and the venv activated, start the app:

```powershell
python app.py
```

This will run the project's entrypoint. The backend `Backend/RagAssistant.py` uses:

- Ollama model: `qwen2.5:3b` (set via `Ollama(model="qwen2.5:3b")`)
- Qdrant URL: `http://localhost:6333` (set via `_qdrant_url` in the assistant)

If your environment uses different hosts/ports, update `Backend/RagAssistant.py` or set up forwarding so both services are reachable locally.

## Troubleshooting
- If Ollama fails to pull or serve the model, check Ollama logs and ensure you have sufficient disk and CPU resources.
- If Docker fails to start Qdrant, ensure Docker Desktop is running and that the ports 6333/6334 are free.
- If Python errors occur, confirm `requirements.txt` installed successfully and that the venv is activated in the same shell.

## Useful commands recap

```powershell
# Pull Ollama model
ollama pull qwen2.5:3b
# Start Ollama daemon
ollama serve
# Run Qdrant in Docker
docker run -d --name qdrant_local -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant
# Create venv, activate, install deps
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Run app
python app.py
```

If you'd like, I can also add a short `docker-compose.yml` and a Windows PowerShell start script to orchestrate Ollama + Qdrant + venv activation. Want me to add those?

## Docker (run in a container)

These instructions build a Linux container image for the project and run it. The Dockerfile filters out a couple of Windows-only packages (for example `pywin32`) from `requirements.txt` before installation so the image is portable across OSes running Docker.

Build the image from the project root:

```bash
docker build -t ai-voice-rag:latest .
```

Run the container (this will run `python app.py` inside the container):

```bash
# optional: expose ports if your app listens on one
docker run --rm -it \
  --name ai-voice-rag \
  -v "$(pwd)":/app \
  ai-voice-rag:latest
```

Notes:
- If your environment requires Ollama or Qdrant to run on the host, run those services on the host or make them available via networking (e.g. host networking, or start them in other containers and connect via a Docker network).
- The Docker image is Linux-based; on Windows use Docker Desktop / WSL2 to run it.
