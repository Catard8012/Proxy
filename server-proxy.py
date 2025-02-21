#!/usr/bin/env python3
import http.server
import socketserver
import urllib.request
import socket
import select
import sys

PORT = 8888  # Change this if needed

class ServerSideProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        client_ip = self.client_address[0]
        print(f"[SERVER PROXY] New connection from {client_ip}")
        
        # Build the full target URL.
        if self.path.startswith("http://") or self.path.startswith("https://"):
            target_url = self.path
        else:
            target_url = "http://" + self.headers.get("Host", "") + self.path
        
        print(f"[SERVER PROXY] GET request for: {target_url}")
        print(f"[SERVER PROXY] Request headers: {self.headers}")
        
        try:
            req = urllib.request.Request(target_url)
            req.add_header("Connection", "close")
            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                # Relay headers (filtering out ones that may cause issues)
                for header, value in response.getheaders():
                    if header.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(header, value)
                self.end_headers()
                content = response.read()
                self.wfile.write(content)
                print(f"[SERVER PROXY] Proxied {len(content)} bytes.")
        except Exception as e:
            self.send_error(500, f"Error fetching {target_url}: {e}")
            print(f"[SERVER PROXY] Error fetching {target_url}: {e}")

    def do_CONNECT(self):
        client_ip = self.client_address[0]
        print(f"[SERVER PROXY] New CONNECT from {client_ip} for {self.path}")
        try:
            host, port = self.path.split(":")
            port = int(port)
        except Exception as e:
            self.send_error(400, "Bad CONNECT request")
            print(f"[SERVER PROXY] Malformed CONNECT request from {client_ip}: {self.path}")
            return

        try:
            remote_socket = socket.create_connection((host, port))
            self.send_response(200, "Connection Established")
            self.end_headers()
            print(f"[SERVER PROXY] Tunnel established for {self.path}")

            # Set sockets to non-blocking mode
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
            print(f"[SERVER PROXY] Tunnel closed for {self.path}")
        except Exception as e:
            try:
                self.send_error(500, f"Error establishing tunnel: {e}")
            except Exception:
                pass
            print(f"[SERVER PROXY] CONNECT error for {self.path} from {client_ip}: {e}")

    def log_message(self, format, *args):
        # Suppress default logging
        return

def run_server():
    # Bind to your PC's IP (192.168.68.81) so it listens only on that interface.
    with socketserver.ThreadingTCPServer(("-----ENTER-SERVER-IP-----", PORT), ServerSideProxyHandler) as httpd:
        print(f"[SERVER PROXY] Running on -----ENTER-SERVER-IP-----:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[SERVER PROXY] Shutting down.")
            httpd.server_close()
            sys.exit(0)

if __name__ == "__main__":
    run_server()
