#!/usr/bin/env python3
import http.server
import socketserver
import threading
import subprocess
import sys
import urllib.request
import socket
import select
import os

PORT = 8888  # Must match the server-side port

class ClientProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Build the full target URL.
        if self.path.startswith("http://") or self.path.startswith("https://"):
            target_url = self.path
        else:
            target_url = "http://" + self.headers.get('Host', '') + self.path

        print(f"[CLIENT PROXY] GET request for: {target_url}")

        try:
            req = urllib.request.Request(target_url)
            req.add_header("Connection", "close")
            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                for header, value in response.getheaders():
                    if header.lower() not in ["transfer-encoding", "connection"]:
                        self.send_header(header, value)
                self.end_headers()
                content = response.read()
                self.wfile.write(content)
                print(f"[CLIENT PROXY] Proxied {len(content)} bytes.")
        except Exception as e:
            self.send_error(500, f"Error fetching {target_url}: {e}")
            print(f"[CLIENT PROXY] Error fetching {target_url}: {e}")

    def do_CONNECT(self):
        print(f"[CLIENT PROXY] CONNECT for: {self.path}")
        try:
            host, port = self.path.split(":")
            port = int(port)
        except Exception as e:
            self.send_error(400, "Bad CONNECT request")
            print(f"[CLIENT PROXY] Malformed CONNECT request: {self.path}")
            return
        try:
            remote_socket = socket.create_connection((host, port))
            self.send_response(200, "Connection Established")
            self.end_headers()

            self.connection.setblocking(0)
            remote_socket.setblocking(0)
            while True:
                r, _, _ = select.select([self.connection, remote_socket], [], [])
                if self.connection in r:
                    data = self.connection.recv(8192)
                    if not data:
                        break
                    remote_socket.sendall(data)
                if remote_socket in r:
                    data = remote_socket.recv(8192)
                    if not data:
                        break
                    self.connection.sendall(data)
        except Exception as e:
            try:
                self.send_error(500, f"Error establishing tunnel: {e}")
            except Exception:
                pass
            print(f"[CLIENT PROXY] CONNECT error for {self.path}: {e}")

    def log_message(self, format, *args):
        return

def run_client_proxy():
    # Bind to all interfaces locally.
    with socketserver.ThreadingTCPServer(("", PORT), ClientProxyHandler) as httpd:
        print(f"[CLIENT PROXY] Running on port {PORT}")
        httpd.serve_forever()

def open_chrome():
    url_to_open = "http://example.com"
    temp_profile = "/tmp/chrome-proxy-session"
    if not os.path.exists(temp_profile):
        os.makedirs(temp_profile)
    try:
        subprocess.Popen([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"--proxy-server=-----ENTER-SERVER-IP-----:{PORT}",
            "--new-window",
            f"--user-data-dir={temp_profile}",
            url_to_open
        ])
        print("[CLIENT PROXY] Chrome launched with proxy configuration in a new session.")
    except Exception as e:
        print("[CLIENT PROXY] Failed to launch Chrome. Verify the path and installation.")
        print(e)
        sys.exit(1)

if __name__ == "__main__":
    # Start the local client-side proxy.
    client_thread = threading.Thread(target=run_client_proxy, daemon=True)
    client_thread.start()
    # Launch Chrome to use your server-side proxy.
    open_chrome()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n[CLIENT PROXY] Exiting.")
        sys.exit(0)
