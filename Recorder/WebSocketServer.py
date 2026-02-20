import asyncio
import websockets
import json
import numpy as np
import threading
import queue
from faster_whisper import WhisperModel
from Backend.RagAssistant import AIVoiceAssistant
from TTS.TTS_module import run_tts, run_tts_async, run_tts_bytes_async
import base64

# Load Faster Whisper model
model = WhisperModel("base", device="cpu", compute_type="int8")

# Global variables
audio_buffer = []
audio_queue = queue.Queue()
stopped_by_punctuation = False
ai_assistant = None
callback_function = None

class VoiceAssistantHandler:
    def __init__(self):
        self.ai_assistant = AIVoiceAssistant()
        self.transcription_text = ""
        
    def process_transcription(self, text):
        """Handle the transcribed text from Whisper"""
        print(f"User said: {text}")
        response = self.ai_assistant.interact_with_llm(text)
        print(f"AI: {response}")
        return response
    
    def transcribe_audio(self, audio_data):
        """Transcribe audio using Faster Whisper"""
        global audio_buffer, stopped_by_punctuation
        
        try:
            # Convert list to numpy array if needed
            if isinstance(audio_data, list):
                audio_array = np.array(audio_data, dtype=np.float32)
            else:
                audio_array = audio_data
            
            # Transcribe with Faster Whisper
            segments, info = model.transcribe(audio_array, beam_size=5, language="en")
            
            transcribed_text = ""
            for segment in segments:
                text = segment.text.strip()
                if text:
                    transcribed_text += text + " "
                    
                    # Check for sentence-ending punctuation
                    if text.endswith(("?", "!")):
                        stopped_by_punctuation = True
                        break
            
            return transcribed_text.strip()
        except Exception as e:
            print(f"Transcription error: {str(e)}")
            return None


handler = VoiceAssistantHandler()


async def handle_client(websocket, path):
    """Handle WebSocket client connections"""
    print(f"Client connected: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "audio":
                    # Receive audio chunks
                    audio_chunk = data.get("audio")
                    
                    if audio_chunk:
                        audio_buffer.extend(audio_chunk)
                        print(f"📥 Received audio chunk ({len(audio_chunk)} samples). Buffer size: {len(audio_buffer)} samples")
                        
                        # Process audio if we have enough (e.g., 3 seconds at 16kHz)
                        # Each chunk is typically 8000 samples at 16kHz = 0.5 seconds
                        if len(audio_buffer) >= 96000:  # ~6 seconds
                            print(f"🔄 Processing audio buffer ({len(audio_buffer)} samples)...")
                            process_audio_chunk(websocket, asyncio.get_event_loop())
                
                elif message_type == "process_audio":
                    # Explicitly request audio processing
                    if audio_buffer:
                        await process_audio_chunk_async(websocket)
                
                elif message_type == "get_status":
                    # Send status response
                    await websocket.send(json.dumps({
                        "type": "status",
                        "message": "WebSocket server is running"
                    }))
                
                else:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Unknown message type"
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                print(f"Error processing message: {str(e)}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": str(e)
                }))
    
    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected: {websocket.remote_address}")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")


async def process_audio_chunk_async(websocket):
    """Process accumulated audio chunk asynchronously"""
    global audio_buffer, stopped_by_punctuation
    
    if not audio_buffer:
        return
    
    try:
        # Convert to numpy array
        audio_data = np.array(audio_buffer, dtype=np.float32)
        audio_buffer = []
        
        # Transcribe audio
        transcribed_text = handler.transcribe_audio(audio_data)
        
        if transcribed_text:
            # Send transcription to client
            await websocket.send(json.dumps({
                "type": "transcription",
                "text": transcribed_text
            }))
            
            # Process with AI if sentence is complete
            if stopped_by_punctuation or transcribed_text.endswith(("?", "!")):
                stopped_by_punctuation = False
                
                # Get AI response
                ai_response = handler.process_transcription(transcribed_text)
                
                # Send AI response to client
                await websocket.send(json.dumps({
                    "type": "response",
                    "text": ai_response
                }))
                
                # Generate TTS bytes and send to client (non-blocking)
                try:
                    tts_bytes = await run_tts_bytes_async(ai_response)
                    if tts_bytes:
                        print(f"TTS generated: {len(tts_bytes)} bytes; sending to client")
                        b64 = base64.b64encode(tts_bytes).decode('ascii')
                        # Log size of base64 payload (for debugging)
                        print(f"TTS base64 size: {len(b64)} chars")
                        await websocket.send(json.dumps({
                            "type": "tts_audio",
                            "format": "mp3",
                            "audio_b64": b64
                        }))
                except Exception as tts_error:
                    print(f"TTS error: {str(tts_error)}")
    
    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        await websocket.send(json.dumps({
            "type": "error",
            "message": f"Audio processing error: {str(e)}"
        }))


def process_audio_chunk(websocket, loop):
    """Blocking wrapper for async processing"""
    asyncio.run_coroutine_threadsafe(
        process_audio_chunk_async(websocket),
        loop
    )


async def start_websocket_server(host="localhost", port=8765):
    """Start the WebSocket server"""
    print(f"Starting WebSocket server on ws://{host}:{port}")
    # Allow large messages (TTS MP3 base64 can exceed default 1MB)
    async with websockets.serve(handle_client, host, port, max_size=None):
        print(f"WebSocket server is running on ws://{host}:{port}")
        await asyncio.Future()  # Run forever


def run_server(host="localhost", port=8765):
    """Run the WebSocket server"""
    asyncio.run(start_websocket_server(host, port))
