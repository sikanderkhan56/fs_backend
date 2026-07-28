import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
AI_PREVIEW_MESSAGE = (
    "These are ESTIMATED timelines based on Claude AI analysis. "
    "Use frame-by-frame preview to confirm exact timing for your specific video version."
)
POST_PREVIEW_MESSAGE = (
    "These are ESTIMATED timelines. Use frame-by-frame preview to confirm "
    "exact timing for your video version."
)


class MovieAIService:
    def __init__(self) -> None:
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def get_scene_preview(
        self, movie_title: str, release_year: Optional[int] = None
    ) -> Dict[str, Any]:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {
                "success": False,
                "has_inappropriate_content": False,
                "estimated_scenes": [],
                "message": "AI preview unavailable",
                "error": "ANTHROPIC_API_KEY is not configured",
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

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.content[0].text.strip()
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
            logger.exception("Failed to parse Claude JSON response")
            return {
                "success": False,
                "has_inappropriate_content": False,
                "estimated_scenes": [],
                "message": "Failed to parse AI response",
                "error": f"JSON parse error: {exc}",
            }
        except Exception as exc:
            logger.exception("Claude API request failed")
            return {
                "success": False,
                "has_inappropriate_content": False,
                "estimated_scenes": [],
                "message": "AI preview request failed",
                "error": str(exc),
            }

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
