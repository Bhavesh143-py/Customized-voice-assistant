import asyncio
import websockets
import json
import numpy as np
from faster_whisper import WhisperModel
from Backend.RagAssistant import AIVoiceAssistant
from TTS.TTS_module import run_tts_async

# =========================================================
# Load Whisper
# =========================================================
model = WhisperModel("base", device="cpu", compute_type="int8")

# =========================================================
# Globals
# =========================================================
audio_buffer = []
stopped_by_punctuation = False


# =========================================================
# Assistant Handler
# =========================================================
class VoiceAssistantHandler:

    def __init__(self):
        self.ai_assistant = AIVoiceAssistant()

    def process_transcription(self, text):
        print(f"\n🧑 User said: {text}")
        response = self.ai_assistant.interact_with_llm(text)
        print(f"🤖 AI: {response}")
        return response

    def transcribe_audio(self, audio_data):
        global stopped_by_punctuation

        try:
            segments, _ = model.transcribe(
                audio_data,
                beam_size=5,
                language="en"
            )

            full_text = ""

            for segment in segments:
                text = segment.text.strip()
                if text:
                    full_text += text + " "
                    if text.endswith(("?", "!", ".")):
                        stopped_by_punctuation = True
                        break

            return full_text.strip()

        except Exception as e:
            print(f"Transcription error: {e}")
            return None


handler = VoiceAssistantHandler()


# =========================================================
# WebSocket Logic
# =========================================================
async def handle_client(websocket, path):

    global audio_buffer, stopped_by_punctuation

    print(f"\n✅ Client connected: {websocket.remote_address}")

    try:
        async for message in websocket:

            data = json.loads(message)
            msg_type = data.get("type")

            # -------------------------------------------------
            # Receive audio
            # -------------------------------------------------
            if msg_type == "audio":

                audio_chunk = data.get("audio")

                if audio_chunk:
                    audio_buffer.extend(audio_chunk)

                    print(f"📥 Buffer size: {len(audio_buffer)} samples")

                    # Process when buffer large enough (~6 sec)
                    if len(audio_buffer) >= 96000:
                        await process_audio(websocket)

            # -------------------------------------------------
            # Manual trigger
            # -------------------------------------------------
            elif msg_type == "process_audio":
                if audio_buffer:
                    await process_audio(websocket)

            # -------------------------------------------------
            # Status check
            # -------------------------------------------------
            elif msg_type == "get_status":
                await websocket.send(json.dumps({
                    "type": "status",
                    "message": "WebSocket server is running"
                }))

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")


# =========================================================
# Process Audio
# =========================================================
async def process_audio(websocket):

    global audio_buffer, stopped_by_punctuation

    if not audio_buffer:
        return

    audio_np = np.array(audio_buffer, dtype=np.float32)
    audio_buffer = []

    transcription = handler.transcribe_audio(audio_np)

    if not transcription:
        return

    await websocket.send(json.dumps({
        "type": "transcription",
        "text": transcription
    }))

    if stopped_by_punctuation or transcription.endswith(("?", "!", ".")):
        stopped_by_punctuation = False

        ai_response = handler.process_transcription(transcription)

        await websocket.send(json.dumps({
            "type": "response",
            "text": ai_response
        }))

        # 🔊 Piper TTS
        await run_tts_async(ai_response)


# =========================================================
# Start Server
# =========================================================
async def start_websocket_server(host="0.0.0.0", port=8765):

    print(f"\n🚀 WebSocket server running at ws://{host}:{port}")

    async with websockets.serve(handle_client, host, port):
        await asyncio.Future()


def run_server():
    asyncio.run(start_websocket_server())
