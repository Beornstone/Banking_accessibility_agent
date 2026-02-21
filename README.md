# Voice Banking Agent Router (FastAPI)

Minimal backend router for transcript-to-intent + UI action.

## Environment

- `GEMINI_API_KEY` (required)
- `GEMINI_MODEL` (optional, default: `gemini-1.5-flash`)

## Run

```bash
pip install -r requirements.txt
GEMINI_API_KEY=your_key uvicorn src.main:app --reload
```

## API

`POST /agent/turn`

Request:

```json
{"session_id":"abc123","transcript":"send 20 to James"}
```

Response contains:
- `assistant_say`
- strict `intent` union
- `ui_action` for frontend (`GO_HOME`, `OPEN_BALANCE`, `OPEN_TRANSFER`, `HIGHLIGHT_SEND`)
- `debug`

## Tests

```bash
pytest -q
```
