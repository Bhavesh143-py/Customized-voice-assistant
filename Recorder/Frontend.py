"""
WebSocket-based Voice Assistant Frontend (Tkinter Removed)

This module has been replaced with a WebSocket server-based architecture.
Use WebSocketServer.py to run the voice assistant server and connect via WebSocket.

For backward compatibility, a simple launcher is provided below.
"""

def show_recorder(on_final_text):
    """
    Legacy function for backward compatibility.
    This now launches the WebSocket server instead of the GUI.
    
    Args:
        on_final_text: Callback function (still used internally by WebSocket handlers)
    """
    from Recorder.WebSocketServer import run_server
    import threading
    
    print("Starting Voice Assistant WebSocket Server...")
    print("Connect to: ws://localhost:8765")
    print()
    print("Example WebSocket client usage:")
    print("  import websockets")
    print("  import json")
    print("  import asyncio")
    print()
    print("  async def connect():")
    print("      async with websockets.connect('ws://localhost:8765') as ws:")
    print("          # Send audio as list of floats")
    print("          await ws.send(json.dumps({'type': 'audio', 'audio': [0.1, 0.2, ...]}))")
    print("          # Receive responses")
    print("          response = await ws.recv()")
    print("          print(json.loads(response))")
    print()
    
    # Run WebSocket server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Voice Assistant Server...")


# Legacy microphone function (kept for compatibility if needed elsewhere)
def get_microphones():
    """Get list of available microphones"""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        return [dev["name"] for dev in devices if dev["max_input_channels"] > 0]
    except Exception as e:
        print(f"Error getting microphones: {e}")
        return []
