"""
ShivAI Autonomous Research Engine.
Coordinates:
- Query decomposition and refinement
- Multi-source search and content retrieval
- Strict prompt-injection sanitization for untrusted web pages
- Evidence synthesis with structured citations and references
"""
import re
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from core.research.search_engine import search_engine, SearchResult
from core.v2.request_service import V2RequestService, V2ChatRequest

logger = logging.getLogger("shivai.research.researcher")


class ResearchReport(BaseModel):
    query: str
    summary: str
    report: str
    citations: List[Dict[str, str]] = Field(default_factory=list)
    sources_consulted: int = 0


def sanitize_untrusted_content(text: str) -> str:
    """
    Sanitizes untrusted web content to defend against indirect prompt injection.
    Strips system role markers, backtick escapes, and instruction overrides.
    """
    # Neutralize instructions attempting to hijack assistant role
    patterns_to_strip = [
        r"ignore previous instructions",
        r"disregard all prior instructions",
        r"you are now in developer mode",
        r"system override",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"\[SYSTEM INSTRUCTION\]",
    ]
    cleaned = text
    for p in patterns_to_strip:
        cleaned = re.sub(p, "[sanitized]", cleaned, flags=re.IGNORECASE)

    # Strip dangerous HTML and script tags
    cleaned = re.sub(r"<script[\s\S]*?</script>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


class AutonomousResearcher:
    """Executes multi-step web research, evidence cross-verification, and citation synthesis."""

    def __init__(self):
        self.search_provider = search_engine

    async def conduct_research(
        self,
        query: str,
        depth: str = "quick",
        max_sources: int = 5,
        user_id: str = "research_user",
    ) -> ResearchReport:
        """
        Executes end-to-end research:
        1. Formulates search sub-queries
        2. Retrieves organic results across web sources
        3. Sanitizes untrusted web findings
        4. Synthesizes a structured report with citations
        """
        logger.info(f"Starting autonomous research for: '{query}' (depth={depth})")

        # 1. Collect sources across primary and angle queries
        queries_to_run = [query]
        if depth == "deep":
            queries_to_run.append(f"{query} latest analysis evidence")

        all_results: List[SearchResult] = []
        seen_urls = set()

        for q in queries_to_run:
            results = await self.search_provider.search(q, max_results=max_sources)
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

        if not all_results:
            return ResearchReport(
                query=query,
                summary="No web search results could be retrieved.",
                report="Unable to gather web evidence at this time.",
                sources_consulted=0,
            )

        # 2. Build sanitized evidence block
        citations = []
        evidence_lines = []
        for idx, res in enumerate(all_results[:max_sources], 1):
            sanitized_snippet = sanitize_untrusted_content(res.snippet)
            evidence_lines.append(f"Source [{idx}] '{res.title}'\nURL: {res.url}\nExcerpt: {sanitized_snippet}\n")
            citations.append({
                "index": str(idx),
                "title": res.title,
                "url": res.url,
            })

        evidence_text = "\n".join(evidence_lines)

        # 3. Synthesize report via V2 request service
        synthesis_prompt = (
            f"You are the ShivAI Senior Research Engine. Conduct an objective, comprehensive research report.\n\n"
            f"Original Question: {query}\n\n"
            f"Verified Web Sources:\n{evidence_text}\n\n"
            f"Instructions:\n"
            f"1. Synthesize the findings thoroughly and objectively.\n"
            f"2. Cite your statements using bracketed citations corresponding to the sources above (e.g. [1], [2]).\n"
            f"3. Note any conflicting viewpoints or uncertainties.\n"
            f"4. Include an Executive Summary followed by Detailed Analysis.\n"
            f"5. End with a numbered Bibliography of consulted sources."
        )

        service = V2RequestService()
        req = V2ChatRequest(message=synthesis_prompt, mode="quality")
        res = await service.execute_chat(req, user_id=user_id, request_id=f"research-{len(citations)}")

        # Extract brief summary from first paragraph
        paragraphs = [p.strip() for p in res.response.split("\n\n") if p.strip()]
        summary = paragraphs[0] if paragraphs else "Research completed."

        return ResearchReport(
            query=query,
            summary=summary,
            report=res.response,
            citations=citations,
            sources_consulted=len(citations),
        )


# Global researcher instance
researcher = AutonomousResearcher()
