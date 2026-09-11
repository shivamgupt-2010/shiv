"""
Lightweight Task and Capability Classifier.
Identifies required capabilities and suitable agent persona based on user prompt.
"""
from typing import Dict, Any, Tuple


class TaskClassifier:
    """Classifies user prompts into task categories and required model capabilities."""

    @staticmethod
    def classify(prompt: str) -> Tuple[str, Dict[str, bool]]:
        """
        Returns:
            task_type: "coding" | "math" | "planning" | "research" | "general"
            required_capabilities: Dict[str, bool]
        """
        text = prompt.lower()

        # Coding signals
        coding_keywords = [
            "def ", "class ", "function", "code", "bug", "syntax", "refactor",
            "python", "javascript", "typescript", "golang", "c++", "rust", "sql",
            "api", "endpoint", "dockerfile", "git", "algorithm", "exception",
            "import ", "async ", "await ", "const ", "var ", "```"
        ]
        if any(kw in text for kw in coding_keywords):
            return "coding", {"coding": True, "reasoning": True}

        # Math signals
        math_keywords = [
            "calculate", "equation", "formula", "integral", "derivative", "matrix",
            "solve for x", "probability", "statistics", "arithmetic", "algebra",
            "sum of", "square root", "factorial"
        ]
        if any(kw in text for kw in math_keywords):
            return "math", {"reasoning": True}

        # Planning signals
        planning_keywords = [
            "roadmap", "plan", "milestone", "architecture design", "step by step guide",
            "phases", "strategy", "breakdown"
        ]
        if any(kw in text for kw in planning_keywords):
            return "planning", {"reasoning": True}

        # Research signals
        research_keywords = [
            "research", "investigate", "compare and contrast", "in-depth analysis",
            "comprehensive review", "literature"
        ]
        if any(kw in text for kw in research_keywords):
            return "research", {"reasoning": True}

        # General default
        return "general", {"reasoning": False}
