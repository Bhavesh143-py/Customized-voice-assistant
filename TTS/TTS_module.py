"""
Text-to-Speech Module using Piper (Streaming, No Files)
Linux compatible (uses aplay)
"""

import subprocess
import shlex
import asyncio
import logging

logger = logging.getLogger(__name__)

MODEL_PATH = "TTS/models/en_US-amy-medium.onnx"


def run_tts(text: str) -> bool:
    if not text or not text.strip():
        return False

    try:
        # Piper process
        piper_cmd = f"piper --model {MODEL_PATH} --output_raw"
        piper = subprocess.Popen(
            shlex.split(piper_cmd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        # Send text
        piper.stdin.write(text.encode("utf-8"))
        piper.stdin.close()

        # Playback (Linux)
        player = subprocess.Popen(
            ["aplay", "-f", "S16_LE", "-r", "22050", "-c", "1"],
            stdin=piper.stdout
        )

        player.wait()
        piper.wait()

        return True

    except Exception as e:
        logger.error(f"Piper TTS Error: {e}")
        return False


async def run_tts_async(text: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_tts, text)
