import asyncio
import json
import websockets


async def run_test():
    uri = "ws://10.0.243.236:8765"
    message = {"test": "hello from test.py"}
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to {uri}")
            await websocket.send(json.dumps(message))
            print(f"Sent: {message}")

            response = await websocket.recv()
            try:
                parsed = json.loads(response)
            except Exception:
                parsed = response
            print(f"Received: {parsed}")
    except Exception as e:
        print(f"Failed to connect or communicate with {uri}: {e}")


if __name__ == "__main__":
    asyncio.run(run_test())
