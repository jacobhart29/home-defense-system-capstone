import websockets
import asyncio
import json
import socket


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()

    return ip

async def handler(websocket):
    data = await websocket.recv()
    print(f"Received data: {data}")

    response = {"status": "success", "response": data}
    await websocket.send(json.dumps(response))

async def main():
    try:
        local_ip = get_local_ip()
    except Exception:
        local_ip = "127.0.0.1"

    async with websockets.serve(handler, local_ip, 8765):
        print(f"WebSocket server started on ws://{local_ip}:8765")
        await asyncio.Future() 

if __name__ == "__main__":
    asyncio.run(main())