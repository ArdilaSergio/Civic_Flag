from http.server import BaseHTTPRequestHandler

from lib.classify_document import classify_document
from lib.parse_document import DocumentParseError, parse_document
from lib.vercel_helpers import load_env_file, parse_multipart_form, send_json


load_env_file()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            file_item, _issues = parse_multipart_form(self)
            parsed = parse_document(file_item.filename, file_item.file.read())
            relevance = classify_document(parsed.text)
            send_json(
                self,
                {
                    "metadata": parsed.metadata.to_dict(),
                    "text_length": len(parsed.text),
                    "preview": parsed.text[:900],
                    "relevance": relevance.to_dict(),
                },
            )
        except (ValueError, DocumentParseError) as exc:
            send_json(self, {"error": str(exc)}, status=400)
        except Exception as exc:
            send_json(self, {"error": f"Text extraction failed: {exc}"}, status=500)
