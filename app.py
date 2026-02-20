from Recorder.WebSocketServer import run_server


def main():
    """Start the AI Voice Assistant WebSocket Server"""
    print("=" * 60)
    print("AI Voice Assistant - WebSocket Server")
    print("=" * 60)
    print()
    print("Server starting on: ws://localhost:8765")
    print()
    print("To connect a client, use a WebSocket client library:")
    print("  * Python: websockets")
    print("  * JavaScript: WebSocket API (built-in)")
    print("  * Other languages: available in most major languages")
    print()
    print("Example message format:")
    print("  {'type': 'audio', 'audio': [list of float samples]}")
    print("  {'type': 'process_audio'}  # Force processing")
    print("  {'type': 'get_status'}     # Check server status")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    try:
        run_server()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
