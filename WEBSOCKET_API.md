# WebSocket API Migration - Voice Assistant Update

## Summary of Changes

The tkinter GUI has been completely removed and replaced with a WebSocket-based API architecture. This allows for:
- Remote connections over the network
- Easy integration with web frontends, mobile apps, and other clients
- Asynchronous audio streaming
- Better scalability

## Files Modified/Created

### New Files:
- **`Recorder/WebSocketServer.py`** - Main WebSocket server implementation
- **`test_websocket_client.py`** - Test client to validate the WebSocket server

### Modified Files:
- **`Recorder/Frontend.py`** - Removed tkinter GUI, now contains a legacy wrapper
- **`app.py`** - Updated to start the WebSocket server instead of GUI
- **`requirements.txt`** - Added `websockets==13.1` dependency

## Running the Server

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Server
```bash
python app.py
```

The server will start on `ws://localhost:8765` and display a welcome message with connection instructions.

## WebSocket API Protocol

### Connection
```
ws://localhost:8765
ws://hostname:8765  # Remote connections
```

### Message Format (JSON)

All messages are sent as JSON objects.

#### Audio Message
Send audio samples to be transcribed:
```json
{
  "type": "audio",
  "audio": [0.1, 0.2, -0.15, 0.3, ...]
}
```

- **type**: "audio"
- **audio**: Array of float values (PCM samples at 16kHz)
- Audio samples should be in range [-1.0, 1.0]

#### Process Audio Message
Force processing of accumulated audio:
```json
{
  "type": "process_audio"
}
```

#### Status Check Message
Check if server is running:
```json
{
  "type": "get_status"
}
```

### Server Responses (JSON)

#### Transcription Response
```json
{
  "type": "transcription",
  "text": "what is the weather today"
}
```

#### AI Response
```json
{
  "type": "response",
  "text": "Today the weather is sunny with a high of 75 degrees..."
}
```

#### Status Response
```json
{
  "type": "status",
  "message": "WebSocket server is running"
}
```

#### Error Response
```json
{
  "type": "error",
  "message": "Error description"
}
```

## Example Client Usage

### Python Client Example
```python
import asyncio
import websockets
import json
import sounddevice as sd
import numpy as np

async def stream_audio():
    uri = "ws://localhost:8765"
    
    async with websockets.connect(uri) as websocket:
        # Capture audio from microphone
        def audio_callback(indata, frames, time, status):
            # Send audio over WebSocket
            audio_data = indata.flatten().tolist()
            message = json.dumps({"type": "audio", "audio": audio_data})
            asyncio.create_task(websocket.send(message))
        
        # Start recording
        with sd.InputStream(callback=audio_callback, channels=1, 
                          samplerate=16000, blocksize=8000):
            print("Recording... (Press Ctrl+C to stop)")
            
            # Listen for responses
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                if data["type"] == "transcription":
                    print(f"You said: {data['text']}")
                elif data["type"] == "response":
                    print(f"AI: {data['text']}")
                elif data["type"] == "error":
                    print(f"Error: {data['message']}")

# Run the client
asyncio.run(stream_audio())
```

### JavaScript/Web Client Example
```javascript
const socket = new WebSocket('ws://localhost:8765');

socket.onopen = () => {
    console.log('Connected to WebSocket server');
    
    // Send test audio
    const audioData = [0.1, 0.2, -0.15, 0.3];
    socket.send(JSON.stringify({
        type: 'audio',
        audio: audioData
    }));
};

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'transcription') {
        console.log('Transcription:', data.text);
    } else if (data.type === 'response') {
        console.log('AI Response:', data.text);
    } else if (data.type === 'error') {
        console.error('Error:', data.message);
    }
};

socket.onerror = (error) => {
    console.error('WebSocket error:', error);
};

socket.onclose = () => {
    console.log('Disconnected from WebSocket server');
};
```

## Testing

### Quick Test with Provided Script
```bash
python test_websocket_client.py
```

This will:
1. Connect to the WebSocket server
2. Check server status
3. Send a test audio chunk (sine wave)
4. Display any responses

## Audio Specifications

- **Sample Rate**: 16,000 Hz
- **Bit Depth**: 32-bit float
- **Channel**: Mono (1 channel)
- **Range**: [-1.0, 1.0] (normalized PCM)

## Server Configuration

The server runs on:
- **Host**: 0.0.0.0 (all interfaces)
- **Port**: 8765
- **Protocol**: WebSocket (WS)

To change these, edit `app.py`:
```python
run_server(host="0.0.0.0", port=8765)
```

## Features

✓ **Asynchronous Audio Processing** - Handle multiple clients concurrently
✓ **Real-time Transcription** - Whisper-based speech-to-text
✓ **AI Response Generation** - LLM-powered conversational response
✓ **Text-to-Speech** - Automatic TTS for AI responses
✓ **Error Handling** - Graceful error messages
✓ **Automatic Sentence Detection** - Stops processing at sentence boundaries (? or !)

## Dependencies

Key dependencies added:
- `websockets==13.1` - WebSocket protocol implementation

Existing dependencies used:
- `faster-whisper` - Speech recognition
- `llama-index` - RAG with LLM
- `gTTS` - Text-to-speech
- `numpy` - Numerical operations

## Notes

- The server maintains audio buffer state for continuous processing
- Sentences ending with "?" or "!" trigger immediate processing
- Multiple clients can connect simultaneously
- The server includes automatic TTS playback for AI responses
- Legacy `show_recorder()` function is preserved for backward compatibility

## Troubleshooting

### Server won't start
- Check that port 8765 is not in use
- Ensure all dependencies are installed: `pip install -r requirements.txt`

### Connection refused
- Make sure the server is running: `python app.py`
- Check firewall settings if connecting remotely
- Use correct IP address instead of localhost for remote connections

### Audio not being processed
- Send `{"type": "process_audio"}` to force processing
- Ensure audio chunks contain sufficient data
- Check server logs for errors

### No TTS output
- Verify `gTTS` is installed
- Check system audio is working
- Review server logs for TTS errors
