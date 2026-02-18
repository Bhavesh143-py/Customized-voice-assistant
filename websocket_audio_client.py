"""
WebSocket Audio Client for Streaming Audio to the AI Voice Assistant

This module provides a ready-to-use client that captures audio from your microphone
and streams it to the WebSocket server in real-time.
"""

import asyncio
import websockets
import json
import sounddevice as sd
import numpy as np
import threading
import queue


class WebSocketAudioClient:
    """WebSocket client for streaming audio to the voice assistant"""
    
    def __init__(self, uri="ws://localhost:8765", device=None, chunk_size=8000):
        """
        Initialize the WebSocket audio client
        
        Args:
            uri (str): WebSocket server URI
            device (int | str | None): Audio device index or name. If None, uses default
            chunk_size (int): Audio chunk size in samples (8000 = ~0.5 sec at 16kHz)
        """
        self.uri = uri
        self.device = device
        self.chunk_size = chunk_size
        self.sample_rate = 16000
        self.is_running = False
        self.websocket = None
        self.audio_queue = queue.Queue()  # Thread-safe queue for audio data
        
    async def process_responses(self):
        """Process incoming messages from the server"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get("type")
                    
                    if message_type == "transcription":
                        print(f"\n🎤 You said: {data.get('text', '')}")
                    elif message_type == "response":
                        print(f"\n🤖 AI: {data.get('text', '')}\n")
                    elif message_type == "status":
                        print(f"✓ {data.get('message', '')}")
                    elif message_type == "error":
                        print(f"✗ Error: {data.get('message', '')}")
                    else:
                        print(f"Server: {data}")
                        
                except json.JSONDecodeError:
                    print(f"Invalid JSON from server: {message}")
                    
        except asyncio.CancelledError:
            print("Response handler stopped")
        except Exception as e:
            print(f"Error processing responses: {e}")
    
    async def send_audio_from_queue(self):
        """Continuously send audio data from queue to WebSocket server"""
        try:
            while self.is_running:
                try:
                    # Get audio data from queue (with timeout to allow checking is_running)
                    audio_chunk = self.audio_queue.get(timeout=0.5)
                    
                    if audio_chunk is not None and self.websocket:
                        try:
                            message = json.dumps({
                                "type": "audio",
                                "audio": audio_chunk.tolist()
                            })
                            await self.websocket.send(message)
                            print(f"📤 Sent audio chunk ({len(audio_chunk)} samples)")
                        except Exception as e:
                            print(f"Error sending audio: {e}")
                except queue.Empty:
                    # No audio data available, continue
                    pass
        except Exception as e:
            print(f"Error in send_audio_from_queue: {e}")
    
    async def stream_audio(self):
        """Stream audio from microphone to WebSocket server"""
        
        def audio_callback(indata, frames, time_info, status):
            """Callback for audio stream (runs in separate thread)"""
            if status:
                print(f"⚠️  Audio status: {status}")
            
            # Flatten and normalize audio
            audio_chunk = indata.flatten().astype(np.float32)
            
            # Put audio data in thread-safe queue
            self.audio_queue.put(audio_chunk)
        
        try:
            with sd.InputStream(
                device=self.device,
                samplerate=self.sample_rate,
                channels=1,
                blocksize=self.chunk_size,
                dtype=np.float32,
                callback=audio_callback
            ):
                print(f"🎤 Streaming audio from microphone...")
                print("   Speak clearly and naturally. Stop speaking at sentence end (? or !)")
                print("   Press Ctrl+C to stop\n")
                
                # Keep streaming
                while self.is_running:
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            print(f"Error in audio stream: {e}")
    
    async def connect(self):
        """Connect to WebSocket server and start streaming"""
        try:
            async with websockets.connect(self.uri) as websocket:
                self.websocket = websocket
                print(f"✓ Connected to {self.uri}")
                
                # Check server status
                await websocket.send(json.dumps({"type": "get_status"}))
                
                self.is_running = True
                
                # Run response processor, audio streamer, and audio sender concurrently
                response_task = asyncio.create_task(self.process_responses())
                audio_task = asyncio.create_task(self.stream_audio())
                sender_task = asyncio.create_task(self.send_audio_from_queue())
                
                # Wait for either task to complete
                done, pending = await asyncio.wait(
                    [response_task, audio_task, sender_task],
                    return_when=asyncio.FIRST_EXCEPTION
                )
                
                # Cancel remaining tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
        except ConnectionRefusedError:
            print(f"✗ Could not connect to {self.uri}")
            print("  Make sure the server is running: python app.py")
        except Exception as e:
            print(f"✗ Connection error: {e}")
        finally:
            self.is_running = False
            self.websocket = None
    
    def run(self):
        """Run the client (blocking call)"""
        try:
            asyncio.run(self.connect())
        except KeyboardInterrupt:
            print("\n\nShutting down client...")
            self.is_running = False


def list_audio_devices():
    """List available audio devices"""
    print("\nAvailable Audio Devices:")
    print("-" * 60)
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            print(f"  [{i}] {device['name']}")
    print("-" * 60)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="WebSocket Audio Client for AI Voice Assistant"
    )
    parser.add_argument(
        "--uri",
        default="ws://localhost:8765",
        help="WebSocket server URI (default: ws://localhost:8765)"
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Audio device index (use --list-devices to see available devices)"
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=8000,
        help="Audio chunk size in samples (default: 8000)"
    )
    
    args = parser.parse_args()
    
    if args.list_devices:
        list_audio_devices()
        return
    
    print("=" * 60)
    print("WebSocket Audio Client - AI Voice Assistant")
    print("=" * 60)
    
    client = WebSocketAudioClient(
        uri=args.uri,
        device=args.device,
        chunk_size=args.chunk_size
    )
    
    try:
        client.run()
    except KeyboardInterrupt:
        print("\nClient stopped")
    finally:
        print("Goodbye!")


if __name__ == "__main__":
    main()
