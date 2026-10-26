"""
ShivAI Multimodal Image and Screenshot Processing Subsystem.
Analyzes visual documents, screenshots, and diagrams using Google Gemini multimodal vision.
"""
import base64
import httpx
import logging
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger("shivai.multimodal.processor")


class MultimodalProcessor:
    """Processes images and screenshots via vision models."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

    async def analyze_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submits image and prompt to Gemini Vision endpoint.
        Returns visual analysis, OCR transcription, or answered query.
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Gemini API key not configured for vision processing.",
            }

        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        user_prompt = prompt or "Extract all text (OCR) and thoroughly analyze the contents of this image."

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": user_prompt},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": b64_data,
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(self.endpoint, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    text = ""
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts if "text" in p)
                    return {
                        "success": True,
                        "analysis": text,
                        "mime_type": mime_type,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Vision API returned {resp.status_code}: {resp.text}",
                    }
        except Exception as e:
            logger.error(f"Vision analysis exception: {e}")
            return {
                "success": False,
                "error": str(e),
            }


# Global processor instance
multimodal_processor = MultimodalProcessor()
