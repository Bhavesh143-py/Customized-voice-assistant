# Quick Start Guide - WebSocket Voice Assistant

## What Changed?

✨ **Old**: Tkinter GUI application
✨ **New**: WebSocket API server that can accept connections from any client

## Getting Started (3 Steps)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Start the Server
```bash
python app.py
```

You should see:
```
============================================================
AI Voice Assistant - WebSocket Server
============================================================

Server starting on: ws://localhost:8765
...
Press Ctrl+C to stop the server
```

### Step 3: Connect a Client (Choose One)

#### Option A: Built-in Audio Client (Recommended)
```bash
python websocket_audio_client.py
```

This will:
- Connect to the WebSocket server
- Capture audio from your default microphone
- Stream it to the server for processing
- Display transcriptions and responses

#### Option B: Test Client
```bash
python test_websocket_client.py
```

This will:
- Connect to the server
- Check status
- Send a test audio chunk
- Display responses
- Disconnect

#### Option C: Custom Client
Create your own WebSocket client in your preferred language/framework.

## Common Commands

### Run Server with Custom Port
```bash
# Edit app.py and change:
run_server(host="0.0.0.0", port=9000)  # Then run
python app.py
```

### List Available Microphones
```bash
python websocket_audio_client.py --list-devices
```

### Use Specific Microphone
```bash
python websocket_audio_client.py --device 2
```

### Connect from Different Machine
```bash
# On machine with server:
python app.py

# On remote machine:
python websocket_audio_client.py --uri ws://SERVER_IP:8765
```

## Example: Simple Manual Test

```python
import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://localhost:8765") as ws:
        # Send test message
        await ws.send(json.dumps({"type": "get_status"}))
        response = await ws.recv()
        print(json.loads(response))

asyncio.run(test())
```

## Audio Format

- **Sample Rate**: 16 kHz
- **Format**: 32-bit float
- **Range**: -1.0 to 1.0
- **Channels**: Mono

## Message Types

| Type | Purpose | Example |
|------|---------|---------|
| `audio` | Stream audio samples | `{"type": "audio", "audio": [0.1, 0.2, ...]}` |
| `process_audio` | Force processing | `{"type": "process_audio"}` |
| `get_status` | Check server | `{"type": "get_status"}` |

## Troubleshooting

**Server won't start**
- Port 8765 might be in use
- Try: `python app.py` (should show error details)

**Client can't connect**
- Make sure server is running
- Check: `python websocket_audio_client.py`

**No responses from server**
- Try `test_websocket_client.py` to verify server works
- Check server logs for errors

## Next Steps

- 📖 Read [WEBSOCKET_API.md](WEBSOCKET_API.md) for detailed API documentation
- 🔧 Check [Recorder/WebSocketServer.py](Recorder/WebSocketServer.py) to customize server behavior
- 🎨 Build your own client in your preferred language/framework

## Architecture

```
┌─────────────────┐
│  Audio Client   │
│ (Microphone)    │
└────────┬────────┘
         │
         │ WebSocket
         │ JSON messages
         │
┌────────▼────────────────────┐
│   WebSocket Server          │
│   (Recorder/                │
│    WebSocketServer.py)      │
│                             │
│  • Audio buffering          │
│  • Whisper transcription    │
│  • LLM processing           │
│  • TTS generation           │
└────────┬────────────────────┘
         │
    ┌────┴──────┬──────────┐
    │            │          │
    ▼            ▼          ▼
  LLM         Qdrant     gTTS
(Ollama)    (Vector DB) (Audio)
```

---

**Enjoy your new WebSocket-based voice assistant! 🚀**
