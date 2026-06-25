# Civic Flag

Civic Flag is an MVP civic document review tool. Upload a public agenda, staff report, board packet, policy memo, planning document, or nonprofit/public-interest document, choose issues of interest, and the app returns structured "Civic Flags" with summaries, evidence, urgency, and suggested follow-up.

## Run Locally

From this folder:

```bash
python3 server.py
```

Then open:

```text
http://localhost:5173
```

If your shell does not have Python on the path, use the bundled runtime in the Codex desktop app:

```bash
/Users/sergioardila/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 server.py
```

## Environment Variables

This MVP uses the OpenAI API for AI civic document review when `OPENAI_API_KEY` is set. If no key is present, it falls back to a clearly labeled local keyword mode so the app still works, but results may be limited.

Required for real AI analysis:

```bash
OPENAI_API_KEY=your_api_key_here
```

You can put this in a `.env` file in the project folder. The local server loads `.env` automatically when it starts.

Optional model override:

```bash
OPENAI_MODEL=gpt-5.4-mini
```

AI calls are isolated in `lib/analyze_document.py` in `analyze_document_with_ai`. The fallback is isolated in `analyze_document_with_keyword_fallback`. The reusable prompt is in `lib/prompt_templates.py`. The OpenAI path uses structured JSON output so the app receives the same fields every time.

## Deploy To Vercel

This project is ready for Vercel as a static frontend plus Python API functions:

- Static files are served from `public/`.
- `/api/parse` is handled by `api/parse.py`.
- `/api/analyze` is handled by `api/analyze.py`.
- Python dependencies are listed in `requirements.txt`.
- The Python runtime is pinned with `.python-version`.

Deployment steps:

1. Push this repo to GitHub.
2. Import the repo in Vercel.
3. Add these Environment Variables in the Vercel project settings:

```bash
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5.4-mini
```

`OPENAI_MODEL` is optional. Do not upload `.env` to Vercel or commit it to GitHub.

4. Deploy. Vercel will serve the frontend and route API requests to the Python functions.

## What Works Now

- Upload support for PDF, DOC, DOCX, and TXT.
- Text extraction for TXT, DOCX, and PDF.
- Best-effort readable text extraction for legacy DOC files.
- Metadata detection for document title, meeting/event date, jurisdiction, agency/governing body, document type, and uploaded file name.
- Civic/policy relevance check before generating flags.
- Topic selection with default issues and custom issues.
- OpenAI structured-output analysis when an API key is configured, shown in the UI as "AI analysis mode".
- Clearly labeled keyword fallback when no API key is configured, shown in the UI as "Fallback keyword mode".
- Structured Civic Flags with related issues, source excerpts, urgency, community impact, follow-up, public comment angle, and confidence.
- Civic Brief with summary, main issues found, top flags, next action, suggested audience, and caveats.
- Prepared Deliverables with executive summary, priority review list, follow-up questions, public comment talking points, outreach list, and monitoring notes.
- Vercel deployment structure with Python API functions.

## Test With A Real Document

1. Start the app.
2. Upload a public agenda, staff report, board packet, policy memo, planning document, or nonprofit/public-interest document.
3. Select issues of interest or add custom issues.
4. Click `Start Reviewing`.
5. Check the `Document Insights` mode indicator. Use `AI analysis mode` for semantic review. `Fallback keyword mode` means no API key is configured.

## Current Limitations

- Real AI analysis requires `OPENAI_API_KEY`; otherwise the app uses the local keyword fallback and labels that mode clearly.
- Legacy `.doc` parsing is best-effort because old binary Word files vary widely.
- PDF extraction depends on embedded text. Scanned image PDFs may return little or no usable text.
- Metadata detection is conservative and returns `Not detected` when unsure.

## Suggested Next Improvements

- Add OCR for scanned PDFs.
- Add page-aware PDF excerpts and citations.
- Add export to PDF/Word for Civic Briefs.
- Add saved issue profiles for teams.
- Add batch monitoring for recurring agendas.
