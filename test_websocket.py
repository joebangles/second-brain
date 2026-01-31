"""Quick test script for the WebSocket endpoint."""
import asyncio
import json
import websockets

async def test_connection():
    uri = "ws://localhost:8000/ws/transcribe"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as ws:
            print("Connected!")
            
            # Send start message
            start_msg = {"type": "start", "sampleRate": 16000, "language": "en"}
            await ws.send(json.dumps(start_msg))
            print(f"Sent: {start_msg}")
            
            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print(f"Received: {response}")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed: {e}")
    except asyncio.TimeoutError:
        print("Timeout waiting for response")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
