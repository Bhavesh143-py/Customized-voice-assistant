"""
WebSocket Client Example for AI Voice Assistant

This example demonstrates how to connect to the WebSocket server and send audio data.
"""

import asyncio
import websockets
import json
import numpy as np


async def connect_and_test():
    """Connect to the WebSocket server and test basic functionality"""
    
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✓ Connected to {uri}")
            print()
            
            # Test 1: Get server status
            print("Test 1: Checking server status...")
            await websocket.send(json.dumps({"type": "get_status"}))
            response = await websocket.recv()
            print(f"Response: {json.loads(response)}")
            print()
            
            # Test 2: Send a single audio chunk
            print("Test 2: Sending audio chunk...")
            # Generate a simple audio chunk (16kHz sample rate, 0.5 seconds)
            sample_rate = 16000
            duration = 0.5
            num_samples = int(sample_rate * duration)
            
            # Create a simple sine wave
            frequency = 440  # A4 note
            t = np.linspace(0, duration, num_samples)
            audio_chunk = np.sin(2 * np.pi * frequency * t).tolist()
            
            await websocket.send(json.dumps({
                "type": "audio",
                "audio": audio_chunk
            }))
            
            print(f"✓ Sent {len(audio_chunk)} audio samples")
            
            # Test 3: Wait for responses
            print("\nListening for responses (10 seconds timeout)...")
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                print(f"Response: {json.loads(response)}")
            except asyncio.TimeoutError:
                print("No response received within timeout (this is normal if audio wasn't processed)")
            
            print("\n✓ WebSocket test completed successfully")
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        print("\nMake sure the server is running:")
        print("  python app.py")


if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket Client Test")
    print("=" * 60)
    print()
    
    asyncio.run(connect_and_test())
