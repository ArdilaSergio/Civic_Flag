import json
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from lib.analyze_document import analyze_document
from lib.classify_document import classify_document
from lib.parse_document import DocumentParseError, parse_document
from lib.vercel_helpers import load_env_file


load_env_file()

app = FastAPI()
ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


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
    return FileResponse(PUBLIC / "index.html")


@app.get("/{path:path}")
def frontend_static(path: str):
    asset = (PUBLIC / path).resolve()
    if PUBLIC.resolve() in asset.parents and asset.is_file():
        return FileResponse(asset)
    return FileResponse(PUBLIC / "index.html")
