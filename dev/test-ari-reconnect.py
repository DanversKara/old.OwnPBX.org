#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""ARI event stream: a dead connection must be detected and reconnected.

Regression test for the Nov 1 and Nov 8 inbound outages. The old run()
called WebSocketApp.run_forever() once with no ping: if the socket died
silently (half-open TCP, no close frame), run_forever() blocked forever,
the process stayed alive, the status server kept answering, and no call
event ever arrived again — inbound dead, nothing in the logs.

    python3 dev/test-ari-reconnect.py   # run from the repo root; exits non-zero on failure
"""
import base64, hashlib, os, socket, sys, threading, time
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "pbx-brain"))
from ari_client import ARIClient
fails = []
def check(n, ok, x=""):
    print(("PASS " if ok else "FAIL ") + n, "" if ok else x); ok or fails.append(n)

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

class SilentServer:
    """Minimal websocket server: completes the handshake, then either goes
    silent (never answers pings, never sends anything) or closes at once."""
    def __init__(self, mode):
        self.mode = mode
        self.count = 0
        self.lock = threading.Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(8)
        self.stop = False
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while not self.stop:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            req = b""
            while b"\r\n\r\n" not in req:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                req += chunk
            key = ""
            for line in req.decode("latin-1").split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
            accept = base64.b64encode(
                hashlib.sha1((key + GUID).encode()).digest()).decode()
            conn.sendall(("HTTP/1.1 101 Switching Protocols\r\n"
                          "Upgrade: websocket\r\n"
                          "Connection: Upgrade\r\n"
                          "Sec-WebSocket-Accept: %s\r\n\r\n" % accept).encode())
            with self.lock:
                self.count += 1
            if self.mode == "close":
                conn.close()
                return
            # silent: hold the socket open, never read, never answer pings.
            while not self.stop:
                time.sleep(0.2)
        except OSError:
            return
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def close(self):
        self.stop = True
        try:
            self.sock.close()
        except OSError:
            pass

def count_after(server, want, deadline_s):
    end = time.time() + deadline_s
    while time.time() < end:
        with server.lock:
            if server.count >= want:
                return server.count
        time.sleep(0.2)
    with server.lock:
        return server.count

# ------------------------------------------------------------ 1. silent socket
srv = SilentServer("silent")
c = ARIClient("http://127.0.0.1:%d/ari/" % srv.port, "user", "pass")
threading.Thread(target=lambda: c.run("pbx-brain", ping_interval=2,
                                     ping_timeout=1), daemon=True).start()
n = count_after(srv, 3, 25)
check("silent socket: client reconnects (got %d connections)" % n, n >= 3)
srv.close()

# ------------------------------------------------------------ 2. clean close
srv2 = SilentServer("close")
c2 = ARIClient("http://127.0.0.1:%d/ari/" % srv2.port, "user", "pass")
threading.Thread(target=lambda: c2.run("pbx-brain", ping_interval=2,
                                      ping_timeout=1), daemon=True).start()
n2 = count_after(srv2, 3, 10)
check("closed socket: client reconnects (got %d connections)" % n2, n2 >= 3)
srv2.close()

print("FAILED: %s" % ", ".join(fails) if fails else "ALL PASS")
sys.exit(1 if fails else 0)
