import json
import logging
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

import certifi

logger = logging.getLogger(__name__)

GEMINI_MODELS = (
    "gemini-flash-lite-latest",  # faster / usually available on free tier
    "gemini-flash-latest",
)
GEMINI_API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
AI_PREVIEW_MESSAGE = (
    "These are ESTIMATED timelines based on Gemini AI analysis. "
    "Use frame-by-frame preview to confirm exact timing for your specific video version."
)
POST_PREVIEW_MESSAGE = (
    "These are ESTIMATED timelines. Use frame-by-frame preview to confirm "
    "exact timing for your video version."
)

# Thinking models can be slow; allow retries for transient timeouts / overload.
GEMINI_TIMEOUT_SECONDS = 90
GEMINI_MAX_ATTEMPTS = 3


class MovieAIService:
    def get_scene_preview(
        self, movie_title: str, release_year: Optional[int] = None
    ) -> Dict[str, Any]:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            return {
                "success": False,
                "has_inappropriate_content": False,
                "estimated_scenes": [],
                "message": "AI preview unavailable",
                "error": "GEMINI_API_KEY is not configured",
            }

        year_text = f" ({release_year})" if release_year else ""
        prompt = f"""You are a movie content filter for "{movie_title}"{year_text}.

Task: List ONLY scenes with kissing, sex, or nudity. Ignore everything else.

INCLUDE only these 3 categories:
1) Kissing — mouth-to-mouth or French kiss only (man-woman, man-man, or woman-woman).
2) Sexual Content — intercourse or clear sexual activity.
3) Nudity — naked body, breasts, hips/buttocks, or private parts clearly shown (man or woman).

EXCLUDE completely (do not list):
- Cheek / forehead / hand kisses, quick pecks
- Violence, guns, killing, fighting, blood
- Language, drugs, horror, or any non-sexual content
- Swimwear or underwear without clear private-part exposure

Rules:
- Be consistent: for the same movie/year, return the same scenes and times every time.
- List scenes in chronological order.
- Times must be approximate with ~ (example: ~01:12:00-01:14:30).
- Max 8 scenes. Short descriptions (under 12 words).
- If none of the INCLUDE scenes exist: has_inappropriate_content=false and estimated_scenes=[].

Return JSON only:
{{
  "has_inappropriate_content": true,
  "estimated_scenes": [
    {{"category": "Kissing", "estimated_time": "~00:45:00-00:46:00", "description": "Mouth-to-mouth romantic kiss"}}
  ]
}}

category must be exactly one of: Kissing, Sexual Content, Nudity."""

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 2048,
                "temperature": 0,
                "topP": 1,
                "topK": 1,
                "responseMimeType": "application/json",
            },
        }

        try:
            raw_text = self._call_gemini(api_key, payload)
            parsed = self._parse_json_response(raw_text)

            return {
                "success": True,
                "has_inappropriate_content": bool(
                    parsed.get("has_inappropriate_content", False)
                ),
                "estimated_scenes": parsed.get("estimated_scenes", []),
                "message": AI_PREVIEW_MESSAGE,
                "error": None,
            }
        except json.JSONDecodeError as exc:
            logger.exception("Failed to parse Gemini JSON response")
            return {
                "success": False,
                "has_inappropriate_content": False,
                "estimated_scenes": [],
                "message": "Failed to parse AI response",
                "error": f"JSON parse error: {exc}",
            }
        except Exception as exc:
            logger.exception("Gemini API request failed")
            return {
                "success": False,
                "has_inappropriate_content": False,
                "estimated_scenes": [],
                "message": "AI preview request failed",
                "error": str(exc),
            }

    def _call_gemini(self, api_key: str, payload: Dict[str, Any]) -> str:
        data = json.dumps(payload).encode("utf-8")
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        last_error: Optional[Exception] = None

        for model in GEMINI_MODELS:
            url = f"{GEMINI_API_URL_TEMPLATE.format(model=model)}?key={api_key}"
            for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):
                request = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(
                        request,
                        timeout=GEMINI_TIMEOUT_SECONDS,
                        context=ssl_context,
                    ) as response:
                        body = json.loads(response.read().decode("utf-8"))
                    logger.info("Gemini success with model=%s", model)
                    return self._extract_text(body)
                except urllib.error.HTTPError as exc:
                    error_body = exc.read().decode("utf-8", errors="replace")
                    last_error = RuntimeError(
                        f"Gemini HTTP {exc.code} ({model}): {error_body}"
                    )
                    # Try next model on model-not-found / overload / quota
                    if exc.code in (404, 429, 503):
                        if (
                            exc.code in (429, 503)
                            and attempt < GEMINI_MAX_ATTEMPTS
                        ):
                            wait_seconds = 2 ** attempt
                            logger.warning(
                                "Gemini HTTP %s on %s (attempt %s/%s). "
                                "Retrying in %ss",
                                exc.code,
                                model,
                                attempt,
                                GEMINI_MAX_ATTEMPTS,
                                wait_seconds,
                            )
                            time.sleep(wait_seconds)
                            continue
                        logger.warning(
                            "Gemini HTTP %s on %s — trying next model",
                            exc.code,
                            model,
                        )
                        break
                    raise last_error from exc
                except (socket.timeout, TimeoutError, urllib.error.URLError) as exc:
                    last_error = exc
                    if attempt < GEMINI_MAX_ATTEMPTS:
                        wait_seconds = 2 ** attempt
                        logger.warning(
                            "Gemini timeout on %s (attempt %s/%s): %s. "
                            "Retrying in %ss",
                            model,
                            attempt,
                            GEMINI_MAX_ATTEMPTS,
                            exc,
                            wait_seconds,
                        )
                        time.sleep(wait_seconds)
                        continue
                    logger.warning(
                        "Gemini timed out on %s — trying next model", model
                    )
                    break

        raise RuntimeError(
            str(last_error)
            if last_error
            else "Gemini request timed out. Please try again in a moment."
        )

    def _extract_text(self, body: Dict[str, Any]) -> str:
        candidates = body.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {body}")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        parts = candidate.get("content", {}).get("parts") or []
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        if not text_parts:
            raise RuntimeError(
                f"Gemini returned empty text (finishReason={finish_reason}): {body}"
            )

        text = "".join(text_parts).strip()
        if finish_reason and finish_reason not in ("STOP", "MAX_TOKENS"):
            logger.warning("Gemini finishReason=%s", finish_reason)
        return text

    def _parse_json_response(self, raw_text: str) -> Dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("Response is not a JSON object", cleaned, 0)

        estimated_scenes = parsed.get("estimated_scenes", [])
        if not isinstance(estimated_scenes, list):
            estimated_scenes = []

        normalized_scenes: List[Dict[str, str]] = []
        for scene in estimated_scenes[:8]:
            if not isinstance(scene, dict):
                continue
            normalized_scenes.append(
                {
                    "category": str(scene.get("category", "Other")),
                    "estimated_time": str(scene.get("estimated_time", "")),
                    "description": str(scene.get("description", "")),
                }
            )

        return {
            "has_inappropriate_content": parsed.get("has_inappropriate_content", False),
            "estimated_scenes": normalized_scenes,
        }


ai_service = MovieAIService()
