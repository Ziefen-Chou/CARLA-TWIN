#!/usr/bin/env python
import socket
import threading
import pickle
import time
import struct
import argparse

# ───────── Configuration ─────────
RECV_PORT = 8999
SEND_IP, SEND_PORT = '127.0.0.1', 9999
MAX_RUNTIME = 600

# Global state for synchronization
initialized = False
state_lock = threading.Lock()
send_sock = None

# ───────── Utility Functions ─────────

def recv_exact(sock, n):
    """Ensures exactly n bytes are read from the socket to prevent TCP fragmentation issues."""
    buf = b''
    while len(buf) < n:
        data = sock.recv(n - len(buf))
        if not data:
            return None
        buf += data
    return buf

# ───────── Receiver Thread ─────────

def listener(conn_in):
    """Listens to CARLA1, updates local state, and handles initialization logic."""
    global initialized, send_sock
    try:
        while True:
            hdr = recv_exact(conn_in, 4)
            if not hdr: 
                break
            ln = struct.unpack('>I', hdr)[0]
            payload = recv_exact(conn_in, ln)
            if not payload: 
                break
            
            data = pickle.loads(payload)

            with state_lock:
                # Handle Init Packet: Synchronize and initialize the twin world
                if isinstance(data, dict) and data.get('init'):
                    send_sock.sendall(len(payload).to_bytes(4, 'big') + payload)
                    initialized = True
                    print(f"[Scheduler] Forwarded initialization packet")
                    continue

                # Forward all vehicle state data immediately to maintain full synchronization
                if initialized:
                    send_sock.sendall(len(payload).to_bytes(4, 'big') + payload)

    except Exception as e:
        print("[Scheduler] Listener error:", e)
    finally:
        conn_in.close()

# ───────── Main Scheduler ─────────

def scheduler():
    global send_sock

    # Setup receiving socket for CARLA1
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('0.0.0.0', RECV_PORT))
    server_sock.listen(1)
    print(f"[Scheduler] Waiting for CARLA1 on port {RECV_PORT}...")
    
    conn_in, _ = server_sock.accept()
    print("[Scheduler] CARLA1 connected")

    # Setup sending socket for CARLA2
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        send_sock.connect((SEND_IP, SEND_PORT))
        print(f"[Scheduler] Connected to CARLA2 at {SEND_IP}:{SEND_PORT}")
    except ConnectionRefusedError:
        print("[Scheduler] Error: Could not connect to CARLA2. Is it running?")
        return

    # Start the listener thread to handle incoming data
    threading.Thread(target=listener, args=(conn_in,), daemon=True).start()

    start_time = time.time()
    try:
        while True:
            # Keep the main thread alive and check for runtime limits
            if time.time() - start_time > MAX_RUNTIME:
                print("[Scheduler] Maximum runtime reached. Shutting down.")
                break
            time.sleep(1)

    except KeyboardInterrupt:
        print("[Scheduler] Interrupted by user")

    finally:
        # Graceful shutdown
        try:
            shutdown_pkt = pickle.dumps({"cmd": "shutdown"})
            send_sock.sendall(len(shutdown_pkt).to_bytes(4, 'big') + shutdown_pkt)
        except:
            pass
        send_sock.close()
        server_sock.close()
        print("[Scheduler] Cleanup complete")

# ───────── Entry Point ─────────
if __name__ == "__main__":
    scheduler()