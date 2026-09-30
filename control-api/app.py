from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/health":
            self.send_error(404)
            return
        body = json.dumps({"status": "ok"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), HealthHandler).serve_forever()
