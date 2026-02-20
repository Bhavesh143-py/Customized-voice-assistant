"""
Text-to-Speech Module using gTTS and Pygame

Converts text to speech and plays it through the system speaker.
Works with both standalone usage and the WebSocket server.
"""

from gtts import gTTS
import pygame
import uuid
import os
import logging

logger = logging.getLogger(__name__)


def run_tts(text: str, lang: str = "en", verbose: bool = False) -> bool:
    """
    Convert text to speech and play it through speakers
    
    Args:
        text (str): Text to convert to speech
        lang (str): Language code (default: "en" for English)
        verbose (bool): Print status messages (default: False)
    
    Returns:
        bool: True if successful, False if error occurred
    
    Example:
        run_tts("Hello, how are you?")
    """
    if not text or not text.strip():
        if verbose:
            print("⚠️  Empty text provided to TTS")
        return False
    
    filename = None
    try:
        # Generate temporary mp3 file
        filename = f"{uuid.uuid4()}.mp3"
        
        if verbose:
            print(f"🔊 Generating speech for: {text[:50]}...")
        
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(filename)
        
        if verbose:
            print(f"✓ Generated TTS file: {filename}")
        
        # Initialize pygame mixer and play audio
        pygame.mixer.init()
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        
        if verbose:
            print("▶️  Playing audio...")
        
        # Wait until playback finishes
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        
        pygame.mixer.quit()
        
        if verbose:
            print("✓ Audio playback completed")
        
        return True
        
    except Exception as e:
        logger.error(f"TTS Error: {str(e)}")
        if verbose:
            print(f"✗ TTS Error: {str(e)}")
        return False
        
    finally:
        # Cleanup temporary file
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                logger.warning(f"Failed to delete TTS file {filename}: {e}")


async def run_tts_async(text: str, lang: str = "en") -> bool:
    """
    Async wrapper for TTS (non-blocking for WebSocket server)
    
    Args:
        text (str): Text to convert to speech
        lang (str): Language code (default: "en" for English)
    
    Returns:
        bool: True if successful, False if error occurred
    
    Note:
        This runs TTS in a way that doesn't block the async event loop.
        Useful for WebSocket servers.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_tts, text, lang)


if __name__ == "__main__":
    # Test the TTS module
    test_text = "Hello, this is a test of the text to speech system. How are you doing today?"
    print("Testing TTS module...")
    success = run_tts(test_text, verbose=True)
    print(f"Test result: {'✓ Passed' if success else '✗ Failed'}")
