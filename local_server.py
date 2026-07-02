"""Local-only development server for Civic Flag.

Vercel deploys the Python functions in /api. This file intentionally avoids
Vercel's reserved entrypoint names such as server.py, app.py, and main.py.
"""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import cgi
import json
import os
import sys

from lib.analyze_document import analyze_document
from lib.classify_document import classify_document
from lib.parse_document import DocumentParseError, parse_document, parse_extracted_text
from lib.vercel_helpers import load_env_file


ROOT = Path(__file__).parent.resolve()


load_env_file(ROOT / ".env")
PUBLIC = ROOT / "public"
PORT = int(os.environ.get("PORT", "5173"))


class CivicFlagHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        if path == "/":
            return str(PUBLIC / "index.html")
        if path.startswith("/src/"):
            return str(ROOT / path.lstrip("/"))
        if path.startswith("/demo_data/"):
            return str(ROOT / path.lstrip("/"))
        return str(PUBLIC / path.lstrip("/"))

    def do_POST(self):
        if self.path == "/api/parse":
            self.handle_parse()
            return
        if self.path == "/api/analyze":
            self.handle_analyze()
            return
        if self.path == "/api/parse-text":
            self.handle_parse_text()
            return
        if self.path == "/api/analyze-text":
            self.handle_analyze_text()
            return
        self.send_json({"error": "Not found"}, status=404)

    def parse_form(self):
        content_type = self.headers.get("content-type")
        if not content_type:
            raise ValueError("Missing content type.")
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
        )
        file_item = form["file"] if "file" in form else None
        if file_item is None or not getattr(file_item, "filename", ""):
            raise ValueError("No file was uploaded.")
        issues = []
        if "issues" in form:
            try:
                issues = json.loads(form["issues"].value)
            except json.JSONDecodeError:
                issues = []
        return file_item, issues

    def parse_json_body(self):
        length = int(self.headers.get("content-length", "0") or "0")
        if not length:
            raise ValueError("Missing request body.")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def handle_parse(self):
        try:
            file_item, _issues = self.parse_form()
            parsed = parse_document(file_item.filename, file_item.file.read())
            relevance = classify_document(parsed.text)
            self.send_json(
                {
                    "metadata": parsed.metadata.to_dict(),
                    "text_length": len(parsed.text),
                    "preview": parsed.text[:900],
                    "relevance": relevance.to_dict(),
                }
            )
        except (ValueError, DocumentParseError) as exc:
            self.send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self.send_json({"error": f"Text extraction failed: {exc}"}, status=500)

    def handle_analyze(self):
        try:
            file_item, issues = self.parse_form()
            parsed = parse_document(file_item.filename, file_item.file.read())
            relevance = classify_document(parsed.text)
            result = analyze_document(parsed.text, parsed.metadata, relevance, issues)
            self.send_json(result)
        except (ValueError, DocumentParseError) as exc:
            self.send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self.send_json({"error": f"Analysis failed: {exc}"}, status=500)

    def handle_parse_text(self):
        try:
            data = self.parse_json_body()
            parsed = parse_extracted_text(data.get("filename", "uploaded-document.pdf"), data.get("text", ""))
            relevance = classify_document(parsed.text)
            self.send_json(
                {
                    "metadata": parsed.metadata.to_dict(),
                    "text_length": len(parsed.text),
                    "preview": parsed.text[:900],
                    "relevance": relevance.to_dict(),
                }
            )
        except (ValueError, json.JSONDecodeError, DocumentParseError) as exc:
            self.send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self.send_json({"error": f"Text extraction failed: {exc}"}, status=500)

    def handle_analyze_text(self):
        try:
            data = self.parse_json_body()
            parsed = parse_extracted_text(data.get("filename", "uploaded-document.pdf"), data.get("text", ""))
            relevance = classify_document(parsed.text)
            result = analyze_document(parsed.text, parsed.metadata, relevance, data.get("issues", []))
            self.send_json(result)
        except (ValueError, json.JSONDecodeError, DocumentParseError) as exc:
            self.send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self.send_json({"error": f"Analysis failed: {exc}"}, status=500)

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), CivicFlagHandler)
    print(f"Civic Flag running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Civic Flag.")
        sys.exit(0)
