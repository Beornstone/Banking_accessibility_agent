# Voice Banking Agent Router

Minimal FastAPI backend for routing voice transcript turns into strict intent JSON and frontend UI actions.

## Setup

```bash
pip install -r requirements.txt
```

## Environment Variables

- `GEMINI_API_KEY` (required)
- `GEMINI_MODEL` (optional, default `gemini-1.5-flash`)

## Run

```bash
GEMINI_API_KEY=your_key uvicorn src.main:app --reload
```

## Example request

```bash
curl -X POST http://127.0.0.1:8000/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-1","transcript":"send 20 to James"}'
```
