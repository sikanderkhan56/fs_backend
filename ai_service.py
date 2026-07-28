import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
AI_PREVIEW_MESSAGE = (
    "These are ESTIMATED timelines based on Gemini AI analysis. "
    "Use frame-by-frame preview to confirm exact timing for your specific video version."
)
POST_PREVIEW_MESSAGE = (
    "These are ESTIMATED timelines. Use frame-by-frame preview to confirm "
    "exact timing for your video version."
)


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
        prompt = f"""You are a movie content advisor. Analyze the movie "{movie_title}"{year_text}.

Provide ESTIMATED timelines for inappropriate scenes (do NOT provide exact timings).
Include categories: Violence, Language/Profanity, Sexual Content, Drug Use, Other

Format response as JSON ONLY (no other text):
{{
    "has_inappropriate_content": true/false,
    "estimated_scenes": [
        {{"category": "Violence", "estimated_time": "~20:30-23:45", "description": "Fight scene"}}
    ]
}}

IMPORTANT:
- Use ~ symbol for estimates (e.g., ~1:30:00)
- Times should be APPROXIMATE, not exact
- Only include clearly inappropriate scenes
- Return ONLY valid JSON"""

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 500,
                "temperature": 0.2,
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
        url = f"{GEMINI_API_URL}?key={api_key}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini HTTP {exc.code}: {error_body}") from exc

        candidates = body.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {body}")

        parts = candidates[0].get("content", {}).get("parts") or []
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        if not text_parts:
            raise RuntimeError(f"Gemini returned empty text: {body}")

        return "\n".join(text_parts).strip()

    def _parse_json_response(self, raw_text: str) -> Dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise json.JSONDecodeError("Response is not a JSON object", cleaned, 0)

        estimated_scenes = parsed.get("estimated_scenes", [])
        if not isinstance(estimated_scenes, list):
            estimated_scenes = []

        normalized_scenes: List[Dict[str, str]] = []
        for scene in estimated_scenes:
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
