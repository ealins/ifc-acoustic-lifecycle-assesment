"""
Start the Lifecycle Assessment Flask API server in the background.
Run this file directly:  python run_server.py
Or import and call start_server() from tests.
"""
import threading
import time
import sys

from flask_app import app

SERVER_READY = False

def run_server(port: int = 5001):
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

def start_server(port: int = 5001, wait: float = 2.0):
    """Start the Flask server in a daemon thread and wait until ready."""
    global SERVER_READY
    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()
    time.sleep(wait)
    SERVER_READY = True
    print(f"SERVER_READY on port {port}")
    sys.stdout.flush()

if __name__ == "__main__":
    start_server()
    # Keep the main thread alive
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
