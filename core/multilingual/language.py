"""
ShivAI Multilingual & Hinglish Language Engine.
Handles:
- Script & language detection (English, Hindi, Hinglish)
- Natural colloquial Hindi & Hinglish dialogue adaptation
- Tone, brevity, and personality customization
"""
import re
from typing import Dict, Any, Tuple


class LanguageEngine:
    """Detects and adapts responses to user linguistic preferences and code-switching."""

    @staticmethod
    def detect_language(text: str) -> str:
        """
        Classifies input language into:
        - 'hindi': Devanagari script predominantly
        - 'hinglish': Latin script with common Hindi words
        - 'english': Standard English
        """
        if not text:
            return "english"

        # Check for Devanagari script
        devanagari_chars = len(re.findall(r"[\u0900-\u097F]", text))
        total_letters = len(re.findall(r"\w", text))

        if total_letters > 0 and (devanagari_chars / total_letters) > 0.3:
            return "hindi"

        # Check for common Romanized Hindi / Hinglish keywords
        hinglish_markers = {
            "kya", "hai", "hain", "kaise", "batao", "mujhe", "karna", "nahi", "nahiin",
            "acha", "theek", "shukriya", "dost", "samajh", "aaya", "karo", "raha",
            "rahi", "bolo", "bhai", "yaar", "kaun", "kahan", "kab", "kyun", "kyu",
            "hogaya", "hota", "hoga", "apna", "apne", "mera", "meri", "hum"
        }
        words = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
        hinglish_overlap = words.intersection(hinglish_markers)
        if len(hinglish_overlap) >= 1:
            return "hinglish"

        return "english"

    @classmethod
    def get_system_prompt_instruction(cls, user_text: str, user_tone: str = "balanced") -> str:
        """Generates dynamic language preservation and tone instructions."""
        detected = cls.detect_language(user_text)

        if detected == "hindi":
            lang_prompt = (
                "Linguistic Directive: The user is speaking Hindi. Respond in natural, fluent, and respectful "
                "Hindi (Devanagari script), matching their vocabulary seamlessly."
            )
        elif detected == "hinglish":
            lang_prompt = (
                "Linguistic Directive: The user is speaking Hinglish (Hindi written in Latin/English script). "
                "Respond in natural, engaging Hinglish with natural Indian conversational flow, mixing Hindi and English smoothly."
            )
        else:
            lang_prompt = (
                "Linguistic Directive: Respond in clear, articulate English."
            )

        if user_tone == "concise":
            tone_prompt = "Style Directive: Be extremely concise, direct, and action-oriented. Avoid unnecessary filler."
        elif user_tone == "technical":
            tone_prompt = "Style Directive: Provide detailed technical depth with exact terminology, code examples, and architecture principles."
        else:
            tone_prompt = "Style Directive: Provide balanced, helpful explanations with high practical clarity."

        return f"{lang_prompt}\n{tone_prompt}"


# Global language engine
language_engine = LanguageEngine()
