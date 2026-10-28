import json
import logging
import re
from typing import Any

import httpx

from backend.app.counselling.guardrails import detect_crisis, sanitize_clinical_language
from backend.app.counselling.prompt import COUNSELLING_SYSTEM_PROMPT, REPAIR_SYSTEM_PROMPT
from backend.app.counselling.schemas import AICounsellingRecommendation

logger = logging.getLogger("student-dropout-system.counselling.gemini")


class GeminiError(Exception):
    """Base exception for Gemini AI client errors."""
    pass


class GeminiTimeoutError(GeminiError):
    """Raised when Gemini call exceeds timeout."""
    pass


class GeminiQuotaError(GeminiError):
    """Raised when Gemini returns HTTP 429 quota/rate limit error."""
    pass


class GeminiSafetyBlockError(GeminiError):
    """Raised when output is blocked by Gemini safety filters."""
    pass


class GeminiValidationError(GeminiError):
    """Raised when Gemini returns malformed or invalid schema output."""
    pass


class GeminiAPIError(GeminiError):
    """Raised when Gemini returns an HTTP 5xx or unhandled status."""
    pass


class GeminiClient:
    """
    HTTP client for Google Gemini REST API.
    Enforces 8.0s timeout, safety checks, structured JSON response parsing,
    and automatic one-time retry on malformed JSON.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-1.5-flash",
        timeout: float = 8.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _extract_json_text(self, text: str) -> str:
        """Strips markdown code fences and whitespace from candidate output."""
        cleaned = text.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fence_match:
            return fence_match.group(1).strip()
        return cleaned

    def _parse_and_validate(self, raw_text: str) -> AICounsellingRecommendation:
        """Parses JSON text into AICounsellingRecommendation with guardrails."""
        json_str = self._extract_json_text(raw_text)
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object from LLM")

        # Sanitize any accidental clinical terminology
        if "summary" in data and isinstance(data["summary"], str):
            sanitized_summary, _ = sanitize_clinical_language(data["summary"])
            data["summary"] = sanitized_summary

        rec = AICounsellingRecommendation(**data)

        # Check for crisis signals in AI output
        if detect_crisis(rec.summary) or any(detect_crisis(a) for a in rec.actions):
            rec = rec.model_copy(update={"escalate_to_hod": True, "refer_to_counsellor": True})

        return rec

    async def _send_request(
        self,
        prompt: str,
        system_instruction: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> str:
        """Dispatches HTTP request to Gemini generateContent endpoint."""
        if not self.api_key:
            raise GeminiError("GEMINI_API_KEY is not configured")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }

        async def _call(client: httpx.AsyncClient) -> str:
            try:
                response = await client.post(url, json=payload, timeout=self.timeout)
            except httpx.TimeoutException as exc:
                raise GeminiTimeoutError(f"Gemini API call timed out after {self.timeout}s") from exc
            except httpx.RequestError as exc:
                raise GeminiAPIError(f"Gemini network request error: {exc}") from exc

            if response.status_code == 429:
                raise GeminiQuotaError("Gemini API rate limit or quota exceeded (HTTP 429)")
            if response.status_code >= 400:
                raise GeminiAPIError(f"Gemini API returned HTTP {response.status_code}: {response.text}")

            resp_json = response.json()

            # Check prompt block or safety filter
            prompt_feedback = resp_json.get("promptFeedback", {})
            if prompt_feedback.get("blockReason"):
                raise GeminiSafetyBlockError(f"Prompt blocked by safety filter: {prompt_feedback.get('blockReason')}")

            candidates = resp_json.get("candidates", [])
            if not candidates:
                raise GeminiAPIError("No generation candidates returned by Gemini")

            first_candidate = candidates[0]
            finish_reason = first_candidate.get("finishReason")
            if finish_reason == "SAFETY":
                raise GeminiSafetyBlockError("Candidate generation blocked by Gemini safety filter")

            content = first_candidate.get("content", {})
            parts = content.get("parts", [])
            if not parts or "text" not in parts[0]:
                raise GeminiAPIError("No text part found in candidate generation")

            return parts[0]["text"]

        if http_client is not None:
            return await _call(http_client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                return await _call(client)

    async def generate_counselling(
        self,
        prompt: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> AICounsellingRecommendation:
        """
        Generates and validates counselling recommendations with single-retry resilience.
        """
        raw_output = await self._send_request(
            prompt=prompt,
            system_instruction=COUNSELLING_SYSTEM_PROMPT,
            http_client=http_client,
        )

        try:
            return self._parse_and_validate(raw_output)
        except Exception as exc:
            logger.warning(
                "Gemini returned invalid JSON or schema (%s). Retrying once with corrective prompt...",
                exc,
            )

        # Retry once on invalid JSON / schema (Scenario S8)
        repair_prompt = f"Previous invalid output:\n{raw_output}\n\nPlease fix the JSON formatting according to the schema."
        retry_output = await self._send_request(
            prompt=repair_prompt,
            system_instruction=REPAIR_SYSTEM_PROMPT,
            http_client=http_client,
        )

        try:
            validated = self._parse_and_validate(retry_output)
            logger.info("Successfully recovered and validated Gemini recommendation on retry.")
            return validated
        except Exception as retry_exc:
            logger.error("Gemini failed schema validation after retry: %s", retry_exc)
            raise GeminiValidationError(f"Invalid JSON from Gemini after retry: {retry_exc}") from retry_exc

    async def generate_text(self, prompt: str) -> str:
        """Generates conversational text response from Gemini API."""
        if not self.api_key:
            raise GeminiError("GEMINI_API_KEY is not configured")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            if response.status_code >= 400:
                raise GeminiAPIError(f"Gemini API returned HTTP {response.status_code}")
            resp_json = response.json()
            candidates = resp_json.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts = candidates[0]["content"].get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"]
            raise GeminiAPIError("No text found in generation response")
