from __future__ import annotations

import json
import os
from typing import Protocol
from urllib import error, request


class LLMClient(Protocol):
    def complete_json(self, *, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        ...

    def repair_json(self, *, invalid_output: str, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        ...


SCHEMA_DESCRIPTION = {
    "oneOf": [
        {"intent": "CHECK_BALANCE", "assistant_say": "string"},
        {
            "intent": "TRANSFER_DRAFT",
            "payee_label": "string(from payees_allowed)",
            "amount": "number > 0 and <= 10000",
            "currency": "EUR",
            "assistant_say": "string",
        },
        {"intent": "CONFIRM", "assistant_say": "string"},
        {"intent": "CANCEL", "assistant_say": "string"},
        {"intent": "CLARIFY", "assistant_say": "string", "choices": "string[] | null"},
        {"intent": "HELP", "assistant_say": "string"},
    ]
}


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    def complete_json(self, *, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        prompt = self._build_prompt(transcript, payees_allowed, pending_transfer)
        return self._generate(prompt)

    def repair_json(self, *, invalid_output: str, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        prompt = (
            "Your previous response was invalid. Return ONLY one valid JSON object that matches the schema.\n"
            f"Invalid output:\n{invalid_output}\n\n"
            + self._build_prompt(transcript, payees_allowed, pending_transfer)
        )
        return self._generate(prompt)

    def _build_prompt(self, transcript: str, payees_allowed: list[str], pending_transfer: dict | None) -> str:
        return (
            "You are a banking voice assistant. Output ONLY JSON. "
            "Never invent payees; must select from payees_allowed. "
            "Never execute payments. If missing info, output CLARIFY.\n"
            f"payees_allowed={json.dumps(payees_allowed)}\n"
            f"pending_transfer={json.dumps(pending_transfer)}\n"
            f"transcript={json.dumps(transcript)}\n"
            f"schema={json.dumps(SCHEMA_DESCRIPTION)}\n"
        )

    def _generate(self, prompt: str) -> str:
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            return response.text or ""
        except ImportError:
            return self._generate_http(prompt)

    def _generate_http(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return ""
        return parts[0].get("text", "")
