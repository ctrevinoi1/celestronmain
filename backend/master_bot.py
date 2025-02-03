import asyncio
import json
import websockets
import ssl
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread

SECRET_TOKEN = "a1b2c3d4e5f6g7h8i9j0"

connected_telescopes = set()
norad_list = []

# --- Flask Setup ---
app = Flask(__name__)
CORS(app)  # Enable CORS for development, configure properly for production

# --- API Endpoints ---
@app.route('/telescopes', methods=['GET'])
def get_telescopes():
    # Basic representation of connected telescopes (you might want more info)
    telescopes = [str(ws.remote_address) for ws in connected_telescopes]
    return jsonify(telescopes)

@app.route('/norad', methods=['GET'])
def get_norad_ids():
    return jsonify(norad_list)

@app.route('/norad', methods=['POST'])
def update_norad_ids():
    global norad_list
    try:
        data = request.get_json()
        new_norad_list = data.get("norad_ids", [])
        
        # Validate input (optional, but recommended)
        if not isinstance(new_norad_list, list):
            raise ValueError("Invalid NORAD ID list format")
        for norad_id in new_norad_list:
            if not isinstance(norad_id, int):
                raise ValueError("NORAD IDs must be integers")
        
        norad_list = new_norad_list
        update_norad_list_file()  # Update the file as well
        asyncio.run_coroutine_threadsafe(broadcast_norad_ids(norad_list), loop)
        return jsonify({"message": "NORAD IDs updated", "norad_ids": norad_list})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Failed to update NORAD IDs"}), 500

# --- norad_ids.json File Update ---
def update_norad_list_file():
    with open(norad_config_path, 'w') as f:
        json.dump({"norad_ids": norad_list}, f)

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

async def handler(websocket):
    """
    Handle incoming WebSocket connections with authentication.
    Newly connected clients must send an access code before being added.
    """
    try:
        # Wait for the client to send its access code.
        auth_message = await websocket.recv()
        auth_data = json.loads(auth_message)
        if auth_data.get("access_code") != SECRET_TOKEN:
            await websocket.send(json.dumps({"error": "Unauthorized access"}))
            await websocket.close()
            return
    except Exception as e:
        await websocket.close()
        return

    # Client is authenticated
    connected_telescopes.add(websocket)
    try:
        async for message in websocket:
            print(f"Received from telescope: {message}")
    except Exception as exc:
        print(f"Error in connection: {exc}")
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

# --- Modified main function ---
async def main():
    global norad_config_path, loop
    norad_config_path = "norad_ids.json"
    
    # Initial load
    update_norad_list()
    
    # File watcher setup
    event_handler = NoradIDEventHandler(norad_config_path, update_norad_list)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(os.path.abspath(norad_config_path)), recursive=False)
    observer.start()
    
    # Start WebSocket server
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("Master server listening on port 8765...")
        
        # Run Flask app in a separate thread
        flask_thread = Thread(target=lambda: app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False))
        flask_thread.daemon = True
        flask_thread.start()

        await periodic_broadcast()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()  # Get the main event loop
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Shutting down master server...")