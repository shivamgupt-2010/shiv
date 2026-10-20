"""
ShivAI Autonomous Software Engineering Agent.
Performs repository analysis, bug diagnosis, targeted surgical refactoring,
automated unit test synthesis, sandboxed test execution, and non-destructive checkpoints.
"""
import os
import re
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from core.tools.sandbox import CodeSandbox, SandboxExecutionResult
from core.projects.manager import project_manager

logger = logging.getLogger("shivai.agents.software_engineer")


class DiagnosisReport(BaseModel):
    error_type: str
    root_cause: str
    suggested_fix: str
    affected_components: List[str] = Field(default_factory=list)
    confidence: float = 0.95


class PatchResult(BaseModel):
    success: bool
    patched_code: str
    diff_summary: str
    error: Optional[str] = None


class AutonomousSoftwareEngineer:
    """Specialist engineering agent that analyzes, patches, and verifies codebases safely."""

    def __init__(self):
        self.sandbox = CodeSandbox(timeout_seconds=15.0)

    def analyze_repository(self, target_dir: str, max_files: int = 100) -> Dict[str, Any]:
        """Scans a repository directory to inventory files, languages, and structure."""
        if not os.path.exists(target_dir):
            return {"error": f"Directory '{target_dir}' does not exist."}

        file_counts: Dict[str, int] = {}
        total_files = 0
        total_size = 0
        file_tree = []

        for root, dirs, files in os.walk(target_dir):
            # Skip hidden and cache dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".venv")]
            for f in files:
                if f.startswith("."):
                    continue
                ext = os.path.splitext(f)[1].lower() or "no_ext"
                file_counts[ext] = file_counts.get(ext, 0) + 1
                total_files += 1

                fpath = os.path.join(root, f)
                try:
                    fsize = os.path.getsize(fpath)
                    total_size += fsize
                except OSError:
                    fsize = 0

                if len(file_tree) < max_files:
                    rel = os.path.relpath(fpath, target_dir)
                    file_tree.append({"path": rel, "size": fsize, "ext": ext})

        return {
            "root_path": target_dir,
            "total_files": total_files,
            "total_size_bytes": total_size,
            "file_types": file_counts,
            "sample_tree": file_tree[:max_files],
        }

    def diagnose_error(self, traceback_or_error: str, context_code: Optional[str] = None) -> DiagnosisReport:
        """Diagnoses common Python / JS runtime and syntax exceptions."""
        err_lower = traceback_or_error.lower()

        if "syntaxerror" in err_lower:
            etype = "SyntaxError"
            cause = "Invalid syntax, unmatched parenthesis, or missing colon."
            fix = "Review code around the reported line for syntax errors or improper indentation."
        elif "typeerror" in err_lower:
            etype = "TypeError"
            cause = "Incompatible type operation or missing required function argument."
            fix = "Verify variable types and method signatures before dispatch."
        elif "keyerror" in err_lower:
            etype = "KeyError"
            cause = "Dictionary accessed with a nonexistent key."
            fix = "Use dict.get(key, default) or verify dictionary schema before lookup."
        elif "attributeerror" in err_lower:
            etype = "AttributeError"
            cause = "Attempted to access an attribute or method on a None or incompatible object."
            fix = "Add null checks or verify object instantiation."
        elif "importerror" in err_lower or "modulenotfounderror" in err_lower:
            etype = "ImportError"
            cause = "Requested module is not installed or incorrectly referenced in PYTHONPATH."
            fix = "Add missing dependency to requirements.txt / package.json or check relative import paths."
        else:
            etype = "GeneralRuntimeError"
            cause = "Unhandled runtime failure or unexpected exception."
            fix = "Wrap in structured try-except block and inspect input state."

        return DiagnosisReport(
            error_type=etype,
            root_cause=cause,
            suggested_fix=fix,
            affected_components=["script.py"],
        )

    def apply_targeted_patch(
        self,
        original_code: str,
        target_chunk: str,
        replacement_chunk: str,
    ) -> PatchResult:
        """
        Applies a precise, non-destructive replacement to source code.
        Fails safely if target_chunk is not uniquely found.
        """
        if target_chunk not in original_code:
            return PatchResult(
                success=False,
                patched_code=original_code,
                diff_summary="",
                error="Target chunk not found in original code.",
            )

        occurrences = original_code.count(target_chunk)
        if occurrences > 1:
            return PatchResult(
                success=False,
                patched_code=original_code,
                diff_summary="",
                error=f"Target chunk matched multiple locations ({occurrences} occurrences). Provide more surrounding context.",
            )

        patched = original_code.replace(target_chunk, replacement_chunk, 1)
        diff_summary = f"- {len(target_chunk)} chars removed, + {len(replacement_chunk)} chars added"

        return PatchResult(
            success=True,
            patched_code=patched,
            diff_summary=diff_summary,
        )

    async def run_sandboxed_tests(
        self,
        source_code: str,
        test_code: str,
    ) -> SandboxExecutionResult:
        """Executes source and unit test suite inside isolated subprocess sandbox."""
        files = {"module.py": source_code}
        harness = (
            "import module\n"
            "import unittest\n\n"
            f"{test_code}\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main(verbosity=2)\n"
        )
        return await self.sandbox.execute_python(harness, files=files)


software_engineer = AutonomousSoftwareEngineer()
