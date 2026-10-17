"""
ShivAI Sandboxed Code and File Execution Environment.
Provides a strictly restricted subprocess execution environment with:
- Isolated ephemeral workspaces
- Process isolation (separate process, never in-process)
- Hard timeout enforcement (5 seconds max)
- Environment variable sanitization (zero secrets or API keys passed to sandbox)
- Output size limits and automatic workspace directory cleanup
"""
import os
import sys
import shutil
import asyncio
import tempfile
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("shivai.tools.sandbox")


class SandboxExecutionResult(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: Optional[int] = None
    execution_time_ms: float = 0.0
    timed_out: bool = False
    files_created: list[str] = Field(default_factory=list)


class CodeSandbox:
    """Executes code and file operations in a restricted, isolated ephemeral workspace."""

    def __init__(self, timeout_seconds: float = 5.0, max_output_chars: int = 50000):
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def _get_sanitized_env(self) -> Dict[str, str]:
        """
        Creates a minimal sanitized environment dictionary.
        Strictly excludes any API keys, credentials, tokens, or database URLs.
        """
        allowed_vars = {"PATH", "SYSTEMROOT", "TEMP", "TMP", "PYTHONPATH"}
        sanitized = {}
        for k, v in os.environ.items():
            k_upper = k.upper()
            # Drop any environment variable containing secret keywords
            if any(secret in k_upper for secret in ["KEY", "SECRET", "TOKEN", "AUTH", "PASS", "DATABASE"]):
                continue
            if k in allowed_vars or k.startswith("LC_"):
                sanitized[k] = v
        sanitized["PYTHONUNBUFFERED"] = "1"
        return sanitized

    async def execute_python(
        self,
        code: str,
        files: Optional[Dict[str, str]] = None,
    ) -> SandboxExecutionResult:
        """
        Runs Python code inside a dedicated temporary workspace directory.
        Captures output, enforces strict timeout, and deletes workspace upon completion.
        """
        import time
        start_time = time.perf_counter()
        workspace_dir = tempfile.mkdtemp(prefix="shivai_sandbox_")

        try:
            # Write input files if provided
            if files:
                for fname, fcontent in files.items():
                    # Prevent directory traversal
                    clean_name = os.path.basename(fname)
                    file_path = os.path.join(workspace_dir, clean_name)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(fcontent)

            # Write script
            script_path = os.path.join(workspace_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Launch isolated subprocess
            env = self._get_sanitized_env()
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace_dir,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_seconds,
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")[: self.max_output_chars]
                stderr = stderr_bytes.decode("utf-8", errors="replace")[: self.max_output_chars]
                exit_code = process.returncode
                timed_out = False
                success = (exit_code == 0)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
                stdout = ""
                stderr = f"Execution exceeded maximum allowed time limit of {self.timeout_seconds}s."
                exit_code = -1
                timed_out = True
                success = False

            # Inspect files created in sandbox
            created = [
                f for f in os.listdir(workspace_dir)
                if f not in ("script.py", *(files.keys() if files else []))
            ]

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return SandboxExecutionResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time_ms=round(elapsed_ms, 2),
                timed_out=timed_out,
                files_created=created,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return SandboxExecutionResult(
                success=False,
                stdout="",
                stderr=f"Sandbox error: {str(e)}",
                exit_code=-1,
                execution_time_ms=round(elapsed_ms, 2),
            )
        finally:
            # Clean up ephemeral workspace directory
            try:
                shutil.rmtree(workspace_dir, ignore_errors=True)
            except Exception:
                pass


# Global sandbox instance
code_sandbox = CodeSandbox()
