import asyncio
import websockets
import json
import sounddevice as sd
import numpy as np
import queue


class WebSocketAudioClient:

    def __init__(self, uri="ws://localhost:8765", device=None):

        self.uri = uri
        self.device = device
        self.sample_rate = 16000
        self.chunk_size = 8000

        self.websocket = None
        self.audio_queue = queue.Queue()
        self.is_running = False

    # =====================================================
    # Handle server responses
    # =====================================================
    async def process_responses(self):

        try:
            async for message in self.websocket:

                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "transcription":
                    print(f"\n🎤 You said: {data.get('text')}")

                elif msg_type == "response":
                    print(f"\n🤖 AI: {data.get('text')}\n")

                elif msg_type == "status":
                    print(f"✓ {data.get('message')}")

        except Exception as e:
            print(f"Response error: {e}")

    # =====================================================
    # Send Audio
    # =====================================================
    async def send_audio(self):

        while self.is_running:

            try:
                chunk = self.audio_queue.get(timeout=0.5)

                message = json.dumps({
                    "type": "audio",
                    "audio": chunk.tolist()
                })

                await self.websocket.send(message)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Send error: {e}")

    # =====================================================
    # Microphone Streaming
    # =====================================================
    async def stream_audio(self):

        def callback(indata, frames, time, status):
            if status:
                print(status)

            # Convert to Python float list
            audio_chunk = indata.flatten().astype(np.float32)
            self.audio_queue.put(audio_chunk)

        with sd.InputStream(
                device=self.device,
                samplerate=self.sample_rate,
                channels=1,
                blocksize=self.chunk_size,
                dtype=np.float32,
                callback=callback):

            print("\n🎙 Speak normally. Stop after sentence.")
            print("Press Ctrl+C to exit.\n")

            while self.is_running:
                await asyncio.sleep(0.1)

    # =====================================================
    # Connect
    # =====================================================
    async def connect(self):

        async with websockets.connect(self.uri) as websocket:

            self.websocket = websocket
            self.is_running = True

            print(f"✅ Connected to {self.uri}")

            await websocket.send(json.dumps({
                "type": "get_status"
            }))

            await asyncio.gather(
                self.process_responses(),
                self.stream_audio(),
                self.send_audio()
            )

    def run(self):
        try:
            asyncio.run(self.connect())
        except KeyboardInterrupt:
            print("\nClient stopped.")
            self.is_running = False


if __name__ == "__main__":
    client = WebSocketAudioClient()
    client.run()
