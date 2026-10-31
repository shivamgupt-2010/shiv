"""
SHIV Codespaces Manager.
Provides sandboxed, persistent workspaces for authoring, editing, testing,
and previewing full-stack web applications, websites, and scripts.
Includes file system CRUD, terminal command execution, and live preview rendering.
"""
from __future__ import annotations

import io
import json
import logging
import mimetypes
import os
import shutil
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


logger = logging.getLogger("shivai.codespaces")


class CodespaceMetadata(BaseModel):
    codespace_id: str = Field(default_factory=lambda: f"cs_{uuid.uuid4().hex[:10]}")
    user_id: str
    name: str
    template: str = "html5_app"
    description: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    file_count: int = 0


class FileNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int = 0
    children: Optional[List[FileNode]] = None


class CodespaceCommandResult(BaseModel):
    success: bool
    command: str
    stdout: str
    stderr: str
    exit_code: Optional[int] = None
    execution_time_ms: float = 0.0


class CodespaceManager:
    """Manages creation, file manipulation, terminal execution, and previews for codespaces."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            root = Path(__file__).resolve().parent.parent.parent
            self.base_dir = root / "storage" / "codespaces"
        else:
            self.base_dir = Path(base_dir)

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._meta_cache: Dict[str, CodespaceMetadata] = {}
        self._load_metadata()

    def _get_workspace_path(self, codespace_id: str) -> Path:
        return self.base_dir / codespace_id

    def _get_meta_path(self, codespace_id: str) -> Path:
        return self._get_workspace_path(codespace_id) / ".codespace_meta.json"

    def _load_metadata(self) -> None:
        """Indexes existing codespaces."""
        for ws_dir in self.base_dir.iterdir():
            if ws_dir.is_dir():
                meta_file = ws_dir / ".codespace_meta.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            meta = CodespaceMetadata(**data)
                            self._meta_cache[meta.codespace_id] = meta
                    except Exception as e:
                        logger.warning(f"Failed to read codespace metadata from {meta_file}: {e}")

    def create_codespace(
        self,
        user_id: str,
        name: str,
        template: str = "html5_app",
        description: str = "",
        initial_files: Optional[Dict[str, str]] = None,
    ) -> CodespaceMetadata:
        """Initializes a new isolated codespace workspace from a template or files."""
        codespace_id = f"cs_{uuid.uuid4().hex[:10]}"
        ws_path = self._get_workspace_path(codespace_id)
        ws_path.mkdir(parents=True, exist_ok=True)

        files = initial_files or {}
        if not files:
            files = self._get_template_files(template=template, name=name)

        for rel_path, content in files.items():
            f_path = ws_path / rel_path
            f_path.parent.mkdir(parents=True, exist_ok=True)
            with open(f_path, "w", encoding="utf-8") as f:
                f.write(content)

        meta = CodespaceMetadata(
            codespace_id=codespace_id,
            user_id=user_id,
            name=name,
            template=template,
            description=description,
            file_count=len(files),
        )

        with open(self._get_meta_path(codespace_id), "w", encoding="utf-8") as f:
            json.dump(meta.model_dump(), f, indent=2)

        self._meta_cache[codespace_id] = meta
        logger.info(f"Created codespace '{name}' ({codespace_id}) with template '{template}'")
        return meta

    def _get_template_files(self, template: str, name: str) -> Dict[str, str]:
        """Provides starter files for various application templates."""
        if template == "html5_app":
            return {
                "index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex flex-col items-center justify-center p-6">
  <div class="max-w-md w-full bg-slate-800 p-8 rounded-2xl shadow-xl border border-slate-700 text-center">
    <div class="w-16 h-16 bg-blue-500/20 text-blue-400 rounded-xl flex items-center justify-center mx-auto mb-4">
      <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
    </div>
    <h1 class="text-2xl font-bold mb-2">{name}</h1>
    <p class="text-slate-400 mb-6">Generated and powered by ShivAI Codespaces.</p>
    <button id="counterBtn" class="bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-2.5 rounded-lg transition">Click Me: 0</button>
  </div>
  <script src="app.js"></script>
</body>
</html>""",
                "app.js": """let count = 0;
const btn = document.getElementById('counterBtn');
if (btn) {
  btn.addEventListener('click', () => {
    count++;
    btn.textContent = `Click Me: ${count}`;
  });
}
console.log('App loaded successfully in Shiv Codespaces!');""",
                "README.md": f"# {name}\nBuilt autonomously with SHIV AI Codespaces.\n",
            }

        elif template == "python_fastapi":
            return {
                "main.py": f"""from fastapi import FastAPI

app = FastAPI(title="{name}", description="Built with ShivAI Codespaces")

@app.get("/")
def read_root():
    return {{"status": "online", "app": "{name}", "version": "1.0.0"}}

@app.get("/api/items")
def get_items():
    return [{{"id": 1, "name": "Item Alpha"}}, {{"id": 2, "name": "Item Beta"}}]
""",
                "requirements.txt": "fastapi\nuvicorn\n",
                "README.md": f"# {name}\nFastAPI Microservice created in Shiv Codespaces.\n",
            }

        return {
            "index.html": f"<h1>{name}</h1>\n<p>Starter workspace in Shiv Codespaces.</p>",
            "README.md": f"# {name}\n",
        }

    def get_codespace(self, codespace_id: str) -> Optional[CodespaceMetadata]:
        return self._meta_cache.get(codespace_id)

    def list_codespaces(self, user_id: Optional[str] = None) -> List[CodespaceMetadata]:
        all_cs = list(self._meta_cache.values())
        if user_id:
            return [cs for cs in all_cs if cs.user_id == user_id]
        return all_cs

    def delete_codespace(self, codespace_id: str) -> bool:
        ws_path = self._get_workspace_path(codespace_id)
        if ws_path.exists():
            shutil.rmtree(ws_path, ignore_errors=True)
        if codespace_id in self._meta_cache:
            del self._meta_cache[codespace_id]
            return True
        return False

    def list_files(self, codespace_id: str) -> List[FileNode]:
        """Returns recursive file tree representation of the workspace."""
        ws_path = self._get_workspace_path(codespace_id)
        if not ws_path.exists():
            raise ValueError(f"Codespace '{codespace_id}' not found")

        def _scan(directory: Path, base: Path) -> List[FileNode]:
            nodes = []
            for item in sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if item.name.startswith("."):
                    continue
                rel_path = item.relative_to(base).as_posix()
                if item.is_dir():
                    children = _scan(item, base)
                    nodes.append(FileNode(name=item.name, path=rel_path, is_dir=True, children=children))
                else:
                    nodes.append(FileNode(name=item.name, path=rel_path, is_dir=False, size=item.stat().st_size))
            return nodes

        return _scan(ws_path, ws_path)

    def read_file(self, codespace_id: str, file_path: str) -> str:
        """Reads contents of a text file inside the codespace."""
        ws_path = self._get_workspace_path(codespace_id)
        clean_rel = Path(file_path).as_posix().lstrip("/")
        full_path = (ws_path / clean_rel).resolve()

        # Enforce sandbox containment
        if not str(full_path).startswith(str(ws_path.resolve())):
            raise ValueError("Directory traversal access denied")

        if not full_path.exists() or full_path.is_dir():
            raise FileNotFoundError(f"File '{file_path}' not found")

        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def write_file(self, codespace_id: str, file_path: str, content: str) -> bool:
        """Writes or updates a file inside the codespace."""
        ws_path = self._get_workspace_path(codespace_id)
        clean_rel = Path(file_path).as_posix().lstrip("/")
        full_path = (ws_path / clean_rel).resolve()

        if not str(full_path).startswith(str(ws_path.resolve())):
            raise ValueError("Directory traversal access denied")

        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Update metadata timestamp
        meta = self.get_codespace(codespace_id)
        if meta:
            meta.updated_at = time.time()
            with open(self._get_meta_path(codespace_id), "w", encoding="utf-8") as f:
                json.dump(meta.model_dump(), f, indent=2)

        return True

    def patch_file(self, codespace_id: str, file_path: str, target_chunk: str, replacement_chunk: str) -> bool:
        from core.agents.software_engineer import software_engineer
        """Surgically replaces a chunk of code in an existing file."""
        original = self.read_file(codespace_id, file_path)
        res = software_engineer.apply_targeted_patch(original, target_chunk, replacement_chunk)
        if not res.success:
            raise ValueError(f"Patch failed: {res.message}")
        return self.write_file(codespace_id, file_path, res.patched_code)

    def delete_file(self, codespace_id: str, file_path: str) -> bool:
        """Deletes a file or directory inside the codespace."""
        ws_path = self._get_workspace_path(codespace_id)
        clean_rel = Path(file_path).as_posix().lstrip("/")
        full_path = (ws_path / clean_rel).resolve()

        if not str(full_path).startswith(str(ws_path.resolve())):
            raise ValueError("Directory traversal access denied")

        if full_path.is_file():
            full_path.unlink()
            return True
        elif full_path.is_dir():
            shutil.rmtree(full_path)
            return True
        return False

    async def execute_command(
        self,
        codespace_id: str,
        command: str,
        timeout_seconds: float = 10.0,
    ) -> CodespaceCommandResult:
        """Executes a shell command inside the codespace workspace."""
        ws_path = self._get_workspace_path(codespace_id)
        if not ws_path.exists():
            raise ValueError(f"Codespace '{codespace_id}' not found")

        import asyncio
        start_time = time.perf_counter()

        from core.tools.sandbox import code_sandbox
        env = code_sandbox._get_sanitized_env()
        # Add workspace to path
        env["WORKSPACE_DIR"] = str(ws_path)

        try:
            # Execute command safely in workspace
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(ws_path),
                env=env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
            duration = (time.perf_counter() - start_time) * 1000.0

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            success = process.returncode == 0

            return CodespaceCommandResult(
                success=success,
                command=command,
                stdout=stdout,
                stderr=stderr,
                exit_code=process.returncode,
                execution_time_ms=round(duration, 2),
            )
        except asyncio.TimeoutError:
            duration = (time.perf_counter() - start_time) * 1000.0
            return CodespaceCommandResult(
                success=False,
                command=command,
                stdout="",
                stderr=f"Command timed out after {timeout_seconds}s",
                exit_code=124,
                execution_time_ms=round(duration, 2),
            )
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000.0
            return CodespaceCommandResult(
                success=False,
                command=command,
                stdout="",
                stderr=str(e),
                exit_code=1,
                execution_time_ms=round(duration, 2),
            )

    def get_preview_file(self, codespace_id: str, rel_path: str = "index.html") -> tuple[bytes, str]:
        """Fetches raw content and mime-type of a preview asset."""
        ws_path = self._get_workspace_path(codespace_id)
        clean_rel = Path(rel_path).as_posix().lstrip("/")
        full_path = (ws_path / clean_rel).resolve()

        if not str(full_path).startswith(str(ws_path.resolve())):
            raise ValueError("Access denied")

        if not full_path.exists() or full_path.is_dir():
            # If requesting root or directory, fallback to index.html
            full_path = ws_path / "index.html"
            if not full_path.exists():
                raise FileNotFoundError("index.html not found in codespace")

        mime_type, _ = mimetypes.guess_type(str(full_path))
        mime_type = mime_type or "text/html"

        with open(full_path, "rb") as f:
            return f.read(), mime_type

    def export_as_zip(self, codespace_id: str) -> bytes:
        """Packs the codespace files into a zip archive."""
        ws_path = self._get_workspace_path(codespace_id)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(ws_path):
                for file in files:
                    if file.startswith("."):
                        continue
                    abs_p = Path(root) / file
                    arc_name = abs_p.relative_to(ws_path).as_posix()
                    zf.write(abs_p, arc_name)
        buf.seek(0)
        return buf.getvalue()


# Global CodespaceManager instance
codespace_manager = CodespaceManager()

codespaces_manager = codespace_manager
