import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-flash-latest"
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
        prompt = (
            f'Movie content advisor for "{movie_title}"{year_text}.\n'
            "ONLY report scenes that match these rules:\n"
            "\n"
            "INCLUDE:\n"
            "1) Kissing — ONLY romantic mouth-to-mouth kissing or French kissing "
            "(deep/open-mouth kissing between a man and a woman, or any couple).\n"
            "2) Sex — sexual intercourse or clear sexual activity.\n"
            "3) Nudity — a man or woman shown naked, or private parts clearly shown "
            "(breasts, genitals, buttocks).\n"
            "\n"
            "DO NOT INCLUDE (these are allowed / ignore them):\n"
            "- Kisses on the cheek, forehead, hand, or quick peck kisses\n"
            "- Violence, blood, fighting, weapons\n"
            "- Language / profanity\n"
            "- Drug use\n"
            "- Scary or intense non-sexual scenes\n"
            "- Swimwear / underwear that is not full nudity or private-part exposure\n"
            "\n"
            "If none of the INCLUDE scenes exist, return has_inappropriate_content "
            "as false and an empty estimated_scenes array.\n"
            "\n"
            "Return JSON only with keys:\n"
            "- has_inappropriate_content (boolean)\n"
            "- estimated_scenes (array, max 5 objects)\n"
            "Each scene object must have: category, estimated_time, description.\n"
            "Allowed categories ONLY: Kissing, Sexual Content, Nudity.\n"
            "Use approximate times with ~ like ~20:30-23:45.\n"
            "Keep descriptions under 15 words. No markdown."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                # Thinking models consume tokens before visible output;
                # keep this high enough for a complete JSON reply.
                "maxOutputTokens": 2048,
                "temperature": 0.1,
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
        url = f"{GEMINI_API_URL}?key={api_key}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini HTTP {exc.code}: {error_body}") from exc

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

        # Join without newlines so split JSON fragments reassemble cleanly
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
        for scene in estimated_scenes[:5]:
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
