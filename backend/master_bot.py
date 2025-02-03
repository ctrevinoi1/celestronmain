import asyncio
import json
import websockets
import ssl
import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread

# --- Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s:%(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

SECRET_TOKEN = "a1b2c3d4e5f6g7h8i9j0"

connected_telescopes = set()
norad_list = []

# --- Flask Setup ---
app = Flask(__name__)
CORS(app)  # Enable CORS for development, configure properly for production

# --- API Endpoints ---
@app.route('/telescopes', methods=['GET'])
def get_telescopes():
    telescopes = [str(ws.remote_address) for ws in connected_telescopes]
    logger.debug(f"Retrieving telescopes list: {telescopes}")
    return jsonify(telescopes)

@app.route('/norad', methods=['GET'])
def get_norad_ids():
    logger.debug(f"Retrieving NORAD IDs: {norad_list}")
    return jsonify(norad_list)

@app.route('/norad', methods=['POST'])
def update_norad_ids():
    global norad_list
    logger.info("Received request to update NORAD IDs")
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
        logger.info(f"Updating NORAD IDs to: {norad_list}")
        update_norad_list_file()  # Update the file as well
        asyncio.run_coroutine_threadsafe(broadcast_norad_ids(norad_list), loop)
        logger.debug("Broadcasted new NORAD IDs to connected telescopes.")
        return jsonify({"message": "NORAD IDs updated", "norad_ids": norad_list})
    except ValueError as e:
        logger.error(f"Value error when updating NORAD IDs: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error when updating NORAD IDs")
        return jsonify({"error": "Failed to update NORAD IDs"}), 500

# --- norad_ids.json File Update ---
def update_norad_list_file():
    try:
        logger.debug(f"Writing NORAD IDs to file {norad_config_path} with data: {norad_list}")
        with open(norad_config_path, 'w') as f:
            json.dump({"norad_ids": norad_list}, f)
        logger.info("norad_ids.json file successfully updated.")
    except Exception as e:
        logger.exception("Failed to update norad_ids.json file")

class NoradIDEventHandler(FileSystemEventHandler):
    def __init__(self, filepath, callback):
        super().__init__()
        self.filepath = filepath
        self.callback = callback
        logger.debug(f"NoradIDEventHandler initialized for file: {filepath}")

    def on_modified(self, event):
        if event.src_path == os.path.abspath(self.filepath):
            logger.info(f"{self.filepath} has been modified. Reloading NORAD IDs.")
            self.callback()

def load_norad_ids(filepath):
    if not os.path.exists(filepath):
        logger.warning(f"NORAD IDs file not found at {filepath}. Using empty list.")
        return []
    try:
        with open(filepath, 'r') as file:
            data = json.load(file)
            logger.debug(f"Loaded NORAD IDs from file {filepath}: {data}")
            return data.get("norad_ids", [])
    except Exception as e:
        logger.exception("Failed to load NORAD IDs from file")
        return []

def update_norad_list():
    global norad_list
    norad_list = load_norad_ids(norad_config_path)
    logger.info(f"Updated NORAD IDs: {norad_list}")

async def handler(websocket):
    """
    Handle incoming WebSocket connections with authentication.
    Newly connected clients must send an access code before being added.
    """
    try:
        logger.info(f"New WebSocket connection from {websocket.remote_address}")
        # Wait for the client to send its access code.
        auth_message = await websocket.recv()
        logger.debug(f"Received authentication message: {auth_message}")
        auth_data = json.loads(auth_message)
        if auth_data.get("access_code") != SECRET_TOKEN:
            logger.warning(f"Unauthorized access attempt from {websocket.remote_address}")
            await websocket.send(json.dumps({"error": "Unauthorized access"}))
            await websocket.close()
            return
    except Exception as e:
        logger.exception("Error during WebSocket authentication")
        await websocket.close()
        return

    # Client is authenticated
    connected_telescopes.add(websocket)
    logger.info(f"Telescope authenticated: {websocket.remote_address} added. Total connections: {len(connected_telescopes)}")
    try:
        async for message in websocket:
            logger.debug(f"Received from telescope {websocket.remote_address}: {message}")
    except Exception as exc:
        logger.exception(f"Error in WebSocket connection from {websocket.remote_address}")
    finally:
        connected_telescopes.discard(websocket)
        logger.info(f"Telescope disconnected: {websocket.remote_address}. Total connections: {len(connected_telescopes)}")

async def broadcast_norad_ids(norad_list):
    msg = {
        "command": "LoadNoradIDs",
        "norad_ids": norad_list
    }
    payload = json.dumps(msg)
    logger.debug(f"Broadcasting NORAD IDs: {norad_list} to {len(connected_telescopes)} telescopes.")
    # Use a copy of the set to avoid runtime errors if a websocket disconnects during iteration.
    for ws in connected_telescopes.copy():
        try:
            await ws.send(payload)
        except Exception as e:
            logger.exception(f"Failed to send NORAD IDs to telescope {ws.remote_address}. Removing connection.")
            connected_telescopes.discard(ws)

async def periodic_broadcast():
    while True:
        await broadcast_norad_ids(norad_list)
        logger.info(f"Broadcasted NORAD IDs to all telescopes: {norad_list}")
        await asyncio.sleep(60)  # Wait a minute

# --- Modified main function ---
async def main():
    global norad_config_path, loop
    norad_config_path = "norad_ids.json"
    logger.info("Starting master server...")
    
    # Initial load
    update_norad_list()
    
    # File watcher setup
    event_handler = NoradIDEventHandler(norad_config_path, update_norad_list)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(os.path.abspath(norad_config_path)), recursive=False)
    observer.start()
    logger.info("Started file observer for norad_ids.json.")
    
    # Start WebSocket server
    async with websockets.serve(handler, "0.0.0.0", 8765):
        logger.info("Master server listening on port 8765 for WebSocket connections...")
        
        # Run Flask app in a separate thread
        def run_flask():
            logger.info("Starting Flask server on port 5000...")
            app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
        flask_thread = Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()

        await periodic_broadcast()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()  # Get the main event loop
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Shutting down master server due to KeyboardInterrupt...")
    except Exception as e:
        logger.exception("Unexpected error in main loop")