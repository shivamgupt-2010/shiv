"""
ShivAI Universal Intent Recognition and Request Classifier.
Categorizes user prompts across 17 distinct operational domains:
1. general_conversation
2. web_research
3. image_understanding
4. image_generation
5. document_analysis
6. video_creation_editing
7. audio_processing
8. design_2d
9. modeling_3d
10. game_development_2d
11. game_development_3d
12. frontend_development
13. fullstack_development
14. coding_debugging
15. data_analysis
16. automation_tool_use
17. project_management

Provides multi-intent detection, confidence scoring, and ambiguity resolution.
"""
import re
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("shivai.orchestration.intent")


class IntentClassification(BaseModel):
    primary_intent: str
    secondary_intents: List[str] = Field(default_factory=list)
    confidence: float = 0.95
    category_scores: Dict[str, float] = Field(default_factory=dict)
    is_ambiguous: bool = False
    clarification_question: Optional[str] = None
    assumptions_made: List[str] = Field(default_factory=list)
    recommended_agent: str = "general"
    required_modality: str = "text"  # text, image, video, audio, threed, code


class UniversalIntentClassifier:
    """Classifies user prompts using keyword heuristics and deterministic pattern matching."""

    CATEGORIES = [
        "general_conversation",
        "web_research",
        "image_understanding",
        "image_generation",
        "document_analysis",
        "video_creation_editing",
        "audio_processing",
        "design_2d",
        "modeling_3d",
        "game_development_2d",
        "game_development_3d",
        "frontend_development",
        "fullstack_development",
        "coding_debugging",
        "data_analysis",
        "automation_tool_use",
        "project_management",
    ]

    AGENT_MAP = {
        "general_conversation": "general",
        "web_research": "researcher",
        "image_understanding": "vision",
        "image_generation": "designer_2d",
        "document_analysis": "researcher",
        "video_creation_editing": "video_editor",
        "audio_processing": "system",
        "design_2d": "designer_2d",
        "modeling_3d": "threed_specialist",
        "game_development_2d": "game_developer",
        "game_development_3d": "game_developer",
        "frontend_development": "engineer",
        "fullstack_development": "app_builder",
        "coding_debugging": "engineer",
        "data_analysis": "analyst",
        "automation_tool_use": "system",
        "project_management": "planner",
    }

    PATTERNS: Dict[str, List[str]] = {
        "video_creation_editing": [
            r"\b(video|clip|trim|render|subtitle|captions|montage|cut video|edit video|mp4|fps|timeline)\b"
        ],
        "image_generation": [
            r"\b(generate image|draw|create image|illustration|picture of|render image|wallpaper|flux|sdxl|photorealistic)\b"
        ],
        "image_understanding": [
            r"\b(describe this image|what is in this photo|ocr|read this diagram|inspect picture)\b"
        ],
        "document_analysis": [
            r"\b(pdf|document|summarize report|analyze paper|extract text from doc|docx)\b"
        ],
        "audio_processing": [
            r"\b(speech|transcribe|audio|voice|tts|stt|whisper|mp3|sound|music|narration)\b"
        ],
        "design_2d": [
            r"\b(poster|banner|logo|social media graphic|canvas|svg|icon|sprite sheet|ui component|flyer|layout)\b"
        ],
        "modeling_3d": [
            r"\b(3d|glb|gltf|mesh|obj|three\.js|procedural mesh|texture map|pbr|blender|3d model)\b"
        ],
        "game_development_2d": [
            r"\b(2d.*game|game.*2d|platformer|phaser|flappy|arcade|canvas.*game|sprite animation|tilemap|top-down|shooter)\b"
        ],
        "game_development_3d": [
            r"\b(3d.*game|game.*3d|unity|godot.*3d|three\.js.*game|fps game|third person|physics world)\b"
        ],
        "fullstack_development": [
            r"\b(full-stack|fullstack|web app|saas|fastapi and react|next\.js app|backend and frontend|build me an app)\b"
        ],
        "frontend_development": [
            r"\b(frontend|react component|tailwind|css layout|html page|landing page|navbar|dashboard ui)\b"
        ],
        "coding_debugging": [
            r"\b(code|function|debug|fix bug|refactor|unit test|script|python|typescript|error traceback)\b"
        ],
        "data_analysis": [
            r"\b(dataset|pandas|statistics|calculate|chart|csv|graph metrics|data trend|correlation)\b"
        ],
        "web_research": [
            r"\b(search web|look up online|latest news|verify fact|citations|find sources|google for)\b"
        ],
        "automation_tool_use": [
            r"\b(automate|cron|webhook|batch process|scrape|tool call|sandbox run)\b"
        ],
        "project_management": [
            r"\b(roadmap|milestone|decompose|project plan|breakdown|sprint|task list)\b"
        ],
    }

    def classify(self, prompt: str) -> IntentClassification:
        """Classifies prompt into primary and secondary categories with confidence scores."""
        clean = prompt.lower().strip()
        scores: Dict[str, float] = {cat: 0.05 for cat in self.CATEGORIES}

        # Check for single-word / ambiguous inputs
        words = clean.split()
        is_generic_short = len(words) <= 2 or clean in {"app", "game", "video", "code", "design", "model", "build"}

        # Calculate pattern matching hits
        for cat, pattern_list in self.PATTERNS.items():
            for pat in pattern_list:
                matches = len(re.findall(pat, clean))
                if matches > 0:
                    scores[cat] += matches * 0.45

        # Check for multi-word or strong keywords
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_cat, top_score = sorted_scores[0]

        is_ambiguous = is_generic_short or top_score < 0.4

        # Fallback to general conversation if no strong hits
        if top_score < 0.2:
            top_cat = "general_conversation"
            top_score = 0.5 if is_generic_short else 0.85

        # Identify secondary intents
        secondary = [c for c, s in sorted_scores[1:4] if s >= 0.35]

        clarification = None
        assumptions = []

        if is_ambiguous:
            clarification = f"Could you provide more details about your {top_cat.replace('_', ' ')} project requirements?"
            assumptions.append(f"Defaulting to standard {top_cat.replace('_', ' ')} prototype template.")

        # Determine required modality
        modality = "text"
        if "video" in top_cat:
            modality = "video"
        elif "image" in top_cat or "design" in top_cat:
            modality = "image"
        elif "audio" in top_cat:
            modality = "audio"
        elif "3d" in top_cat:
            modality = "threed"
        elif any(c in top_cat for c in ["game", "frontend", "fullstack", "coding"]):
            modality = "code"

        agent = self.AGENT_MAP.get(top_cat, "general")

        return IntentClassification(
            primary_intent=top_cat,
            secondary_intents=secondary,
            confidence=min(0.99, round(top_score, 2)),
            category_scores={k: round(v, 2) for k, v in scores.items() if v > 0.05},
            is_ambiguous=is_ambiguous,
            clarification_question=clarification,
            assumptions_made=assumptions,
            recommended_agent=agent,
            required_modality=modality,
        )


intent_classifier = UniversalIntentClassifier()
