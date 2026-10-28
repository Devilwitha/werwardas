"""Bewertung mit einem lokalen Vision-Modell über Ollama (z. B. qwen2.5vl, llava, gemma3)."""

from __future__ import annotations

import base64
import json

import requests
from PIL import Image

from . import AnalyzerError, Result, build_prompt, clamp_score
from ..camera import to_jpeg

SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer"}, "reason": {"type": "string"}},
    "required": ["score", "reason"],
}


class OllamaAnalyzer:
    name = "ollama"

    def __init__(self, cfg: dict, hint: str):
        self.cfg = cfg
        self.prompt = build_prompt(hint)

    def analyze(self, img: Image.Image) -> Result:
        image_b64 = base64.b64encode(to_jpeg(img, max_width=1024)).decode()
        payload = {
            "model": self.cfg["model"],
            "stream": False,
            "format": SCHEMA,
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": self.prompt, "images": [image_b64]}],
        }
        url = self.cfg["url"].rstrip("/") + "/api/chat"
        try:
            resp = requests.post(url, json=payload, timeout=float(self.cfg["timeout_seconds"]))
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            data = json.loads(content)
        except requests.RequestException as exc:
            raise AnalyzerError(f"Ollama nicht erreichbar ({url}): {exc}") from exc
        except (KeyError, ValueError) as exc:
            raise AnalyzerError(f"Unerwartete Antwort von Ollama: {exc}") from exc
        return Result(round(clamp_score(data.get("score"))), str(data.get("reason", "")).strip(), self.name)
