from __future__ import annotations

import json
import time
from typing import Any, cast

import httpx

from app.core.config import Settings
from app.core.exceptions import ServiceUnavailableError
from app.schemas.analysis import AIAnalysisResult


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def analyze_error_group(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AIAnalysisResult:
        if not self._settings.ai_openai_api_key or not self._settings.ai_openai_base_url:
            raise ServiceUnavailableError("AI provider is not configured.")

        endpoint = self._settings.ai_openai_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.ai_openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.ai_model,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.ai_request_timeout_seconds
            ) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ServiceUnavailableError("AI analysis timed out.") from exc
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError("AI analysis request failed.") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        body = cast(dict[str, Any], response.json())

        try:
            raw_content = (
                body["choices"][0]["message"]["content"]
                if isinstance(body.get("choices"), list)
                else ""
            )
            content_obj = cast(dict[str, Any], json.loads(raw_content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ServiceUnavailableError("AI provider returned malformed output.") from exc

        content_obj.setdefault("provider", "openai_compatible")
        content_obj.setdefault("model", self._settings.ai_model)
        content_obj.setdefault("latency_ms", latency_ms)
        return AIAnalysisResult.model_validate(content_obj)
