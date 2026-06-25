import json

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from lib.analyze_document import analyze_document
from lib.classify_document import classify_document
from lib.parse_document import DocumentParseError, parse_document
from lib.static_assets import INDEX_HTML, MAIN_JS, STYLES_CSS
from lib.vercel_helpers import load_env_file


load_env_file()

app = FastAPI()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/parse")
async def parse_endpoint(file: UploadFile = File(...)):
    try:
        parsed = parse_document(file.filename, await file.read())
        relevance = classify_document(parsed.text)
        return {
            "metadata": parsed.metadata.to_dict(),
            "text_length": len(parsed.text),
            "preview": parsed.text[:900],
            "relevance": relevance.to_dict(),
        }
    except DocumentParseError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": f"Text extraction failed: {exc}"}, status_code=500)


@app.post("/api/analyze")
async def analyze_endpoint(file: UploadFile = File(...), issues: str = Form("[]")):
    try:
        selected_issues = json.loads(issues)
    except json.JSONDecodeError:
        selected_issues = []

    try:
        parsed = parse_document(file.filename, await file.read())
        relevance = classify_document(parsed.text)
        return analyze_document(parsed.text, parsed.metadata, relevance, selected_issues)
    except DocumentParseError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"error": f"Analysis failed: {exc}"}, status_code=500)


@app.get("/")
def frontend_index():
    return HTMLResponse(INDEX_HTML)


@app.get("/{path:path}")
def frontend_static(path: str):
    if path == "main.js":
        return Response(MAIN_JS, media_type="text/javascript")
    if path == "styles.css":
        return Response(STYLES_CSS, media_type="text/css")
    return HTMLResponse(INDEX_HTML)
