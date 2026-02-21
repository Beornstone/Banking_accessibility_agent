from __future__ import annotations

import json
import os
from typing import Any
from urllib import request


SCHEMA_TEXT = """
Intent JSON schema (one object only):
- {"intent":"CHECK_BALANCE","assistant_say":string}
- {"intent":"TRANSFER_DRAFT","payee_label":string,"amount":number,"currency":"EUR","assistant_say":string}
- {"intent":"CONFIRM","assistant_say":string}
- {"intent":"CANCEL","assistant_say":string}
- {"intent":"CLARIFY","assistant_say":string,"choices":string[]|null}
- {"intent":"HELP","assistant_say":string}
""".strip()


def extract_first_json_object(raw: str) -> str:
    start = raw.find("{")
    if start == -1:
        raise ValueError("No JSON object found")

    depth = 0
    in_string = False
    escaped = False

    for i, char in enumerate(raw[start:], start=start):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]

    raise ValueError("Unbalanced JSON object")


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    def generate_intent(self, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required")

        prompt = self._build_prompt(transcript, payees_allowed, pending_transfer)
        raw = self._generate_text(prompt)
        return extract_first_json_object(raw)

    def repair_intent(self, invalid_output: str, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required")

        repair_prompt = (
            "Your previous output was invalid. Return JSON ONLY and match schema exactly.\n"
            f"Invalid output:\n{invalid_output}\n\n"
            f"Transcript: {transcript}\n"
            f"payees_allowed: {json.dumps(payees_allowed)}\n"
            f"pending_transfer: {json.dumps(pending_transfer)}\n\n"
            f"{SCHEMA_TEXT}"
        )
        raw = self._generate_text(repair_prompt)
        return extract_first_json_object(raw)

    def _build_prompt(self, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        return (
            "You are a banking voice assistant. Output ONLY JSON. "
            "Never invent payees; must select from payees_allowed. "
            "Never execute payments. If missing info, output CLARIFY.\n"
            f"Transcript: {transcript}\n"
            f"payees_allowed: {json.dumps(payees_allowed)}\n"
            f"pending_transfer: {json.dumps(pending_transfer)}\n\n"
            f"{SCHEMA_TEXT}"
        )

    def _generate_text(self, prompt: str) -> str:
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            return response.text or ""
        except ImportError:
            return self._generate_text_http(prompt)

    def _generate_text_http(self, prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }
        data = json.dumps(body).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with request.urlopen(req, timeout=20) as resp:
            payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return (
            payload.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
