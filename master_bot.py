import asyncio
import json
import websockets
import ssl
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

SECRET_TOKEN = "a1b2c3d4e5f6g7h8i9j0"

connected_telescopes = set()
norad_list = []

class NoradIDEventHandler(FileSystemEventHandler):
    def __init__(self, filepath, callback):
        super().__init__()
        self.filepath = filepath
        self.callback = callback

    def on_modified(self, event):
        if event.src_path == os.path.abspath(self.filepath):
            print(f"{self.filepath} has been modified. Reloading NORAD IDs.")
            self.callback()

def load_norad_ids(filepath):
    if not os.path.exists(filepath):
        print(f"NORAD IDs file not found at {filepath}. Using empty list.")
        return []
    with open(filepath, 'r') as file:
        data = json.load(file)
        return data.get("norad_ids", [])

def update_norad_list():
    global norad_list
    norad_list = load_norad_ids(norad_config_path)
    print(f"Updated NORAD IDs: {norad_list}")

async def handler(websocket, path):
    # Authenticate the client
    try:
        auth_message = await websocket.recv()
        auth_data = json.loads(auth_message)
        if auth_data.get("token") != SECRET_TOKEN:
            await websocket.send(json.dumps({"error": "Unauthorized"}))
            await websocket.close()
            return
    except:
        await websocket.close()
        return

    # On successful authentication, add to connected set
    connected_telescopes.add(websocket)
    try:
        async for message in websocket:
            print(f"Received from telescope: {message}")
    except:
        pass
    finally:
        connected_telescopes.remove(websocket)

async def broadcast_norad_ids(norad_list):
    msg = {
        "command": "LoadNoradIDs",
        "norad_ids": norad_list
    }
    payload = json.dumps(msg)
    
    for ws in connected_telescopes:
        try:
            await ws.send(payload)
        except:
            pass

async def periodic_broadcast():
    while True:
        await broadcast_norad_ids(norad_list)
        print(f"Broadcasted NORAD IDs to all telescopes: {norad_list}")
        await asyncio.sleep(60)  # Wait a minute

async def main():
    global norad_config_path
    # Path to the NORAD IDs config file
    norad_config_path = "norad_ids.json"
    
    # Initial load
    update_norad_list()
    
    # Set up file watcher
    event_handler = NoradIDEventHandler(norad_config_path, update_norad_list)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(os.path.abspath(norad_config_path)), recursive=False)
    observer.start()
    
    # Start WebSocket server and broadcasting
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Master server listening on port 8765...")
        await periodic_broadcast()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down master server...")