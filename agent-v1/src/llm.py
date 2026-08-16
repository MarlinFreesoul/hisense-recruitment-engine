"""DeepSeek LLM 客户端(OpenAI 兼容端点)

读 key 顺序:环境变量 DEEPSEEK_API_KEY → ~/.config/deepseek/api_key
提供 chat_json():调用 chat completions,开启 JSON 模式,返回 dict(失败返回 None)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests

BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4-flash"


def _api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key.strip()
    p = Path.home() / ".config" / "deepseek" / "api_key"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "未找到 DeepSeek API key(设 DEEPSEEK_API_KEY 或 ~/.config/deepseek/api_key)"
    )


def chat_json(
    system: str, user: str, model: str = DEFAULT_MODEL, retries: int = 2
) -> dict | None:
    """调用 DeepSeek 返回解析后的 JSON dict,失败重试,最终失败返回 None。"""
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 4000,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    key = _api_key()
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=90,
            )
            if r.status_code != 200:
                if attempt < retries:
                    continue
                return None
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception:
            if attempt < retries:
                continue
            return None
    return None
