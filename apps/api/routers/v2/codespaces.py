"""
SHIV Codespaces API Router (v2).
Provides full-featured REST API for cloud & local developer workspaces:
File tree manipulation, code editing, terminal command execution, and live web previews.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from apps.api.dependencies import get_current_user_context, UserContext, rate_limit_middleware_check
from core.codespaces.ui import CODESPACES_UI_HTML
from core.codespaces.manager import (
    codespace_manager,
    CodespaceMetadata,
    FileNode,
    CodespaceCommandResult,
)

router = APIRouter(prefix="/v2/codespaces", tags=["SHIV Codespaces IDE"])


class CreateCodespacePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    template: str = Field(default="html5_app", description="html5_app, react_vite, python_fastapi, custom")
    description: str = ""
    initial_files: Optional[Dict[str, str]] = None


class WriteFilePayload(BaseModel):
    path: str
    content: str


class PatchFilePayload(BaseModel):
    path: str
    target_chunk: str
    replacement_chunk: str


class TerminalCommandPayload(BaseModel):
    command: str
    timeout_seconds: float = 15.0


@router.post(
    "",
    response_model=CodespaceMetadata,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def create_codespace(
    payload: CreateCodespacePayload,
    user: UserContext = Depends(get_current_user_context),
) -> CodespaceMetadata:
    """Creates a new isolated codespace workspace."""
    return codespace_manager.create_codespace(
        user_id=user.user_id,
        name=payload.name,
        template=payload.template,
        description=payload.description,
        initial_files=payload.initial_files,
    )


@router.get("", response_model=List[CodespaceMetadata])
async def list_codespaces(
    user: UserContext = Depends(get_current_user_context),
) -> List[CodespaceMetadata]:
    """Lists all codespaces owned by the user."""
    return codespace_manager.list_codespaces(user_id=user.user_id)


@router.get("/{codespace_id}", response_model=CodespaceMetadata)
async def get_codespace(
    codespace_id: str,
    user: UserContext = Depends(get_current_user_context),
) -> CodespaceMetadata:
    meta = codespace_manager.get_codespace(codespace_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Codespace not found")
    return meta


@router.delete("/{codespace_id}")
async def delete_codespace(
    codespace_id: str,
    user: UserContext = Depends(get_current_user_context),
) -> Dict[str, Any]:
    success = codespace_manager.delete_codespace(codespace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Codespace not found")
    return {"status": "deleted", "codespace_id": codespace_id}


@router.get("/{codespace_id}/files", response_model=List[FileNode])
async def list_codespace_files(
    codespace_id: str,
    user: UserContext = Depends(get_current_user_context),
) -> List[FileNode]:
    """Retrieves full recursive file and directory tree."""
    try:
        return codespace_manager.list_files(codespace_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{codespace_id}/files/content")
async def read_codespace_file(
    codespace_id: str,
    path: str = Query(..., description="Relative path of file to read"),
    user: UserContext = Depends(get_current_user_context),
) -> Dict[str, Any]:
    """Reads content of a file in the workspace."""
    try:
        content = codespace_manager.read_file(codespace_id, path)
        return {"codespace_id": codespace_id, "path": path, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File '{path}' not found")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{codespace_id}/files")
async def write_codespace_file(
    codespace_id: str,
    payload: WriteFilePayload,
    user: UserContext = Depends(get_current_user_context),
) -> Dict[str, Any]:
    """Creates or overwrites a file in the workspace."""
    try:
        codespace_manager.write_file(codespace_id, payload.path, payload.content)
        return {"status": "saved", "codespace_id": codespace_id, "path": payload.path}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{codespace_id}/files/patch")
async def patch_codespace_file(
    codespace_id: str,
    payload: PatchFilePayload,
    user: UserContext = Depends(get_current_user_context),
) -> Dict[str, Any]:
    """Applies a surgical code edit replacing target_chunk with replacement_chunk."""
    try:
        codespace_manager.patch_file(
            codespace_id,
            file_path=payload.path,
            target_chunk=payload.target_chunk,
            replacement_chunk=payload.replacement_chunk,
        )
        return {"status": "patched", "codespace_id": codespace_id, "path": payload.path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{codespace_id}/files")
async def delete_codespace_file(
    codespace_id: str,
    path: str = Query(..., description="Relative path to delete"),
    user: UserContext = Depends(get_current_user_context),
) -> Dict[str, Any]:
    try:
        codespace_manager.delete_file(codespace_id, path)
        return {"status": "deleted", "codespace_id": codespace_id, "path": path}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{codespace_id}/terminal", response_model=CodespaceCommandResult)
async def execute_terminal_command(
    codespace_id: str,
    payload: TerminalCommandPayload,
    user: UserContext = Depends(get_current_user_context),
) -> CodespaceCommandResult:
    """Executes a terminal command safely inside the isolated workspace."""
    try:
        return await codespace_manager.execute_command(
            codespace_id,
            command=payload.command,
            timeout_seconds=payload.timeout_seconds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ui", response_class=HTMLResponse)
async def get_codespaces_ui():
    """Renders the standalone interactive SHIV Codespaces Web IDE."""
    return HTMLResponse(content=CODESPACES_UI_HTML)


@router.get("/{codespace_id}/preview", response_class=Response)
@router.get("/{codespace_id}/preview/{subpath:path}", response_class=Response)
async def preview_codespace_app(
    codespace_id: str,
    subpath: str = "index.html",
):
    """Renders the live interactive HTML/JS preview of the codespace application."""
    try:
        data, mime_type = codespace_manager.get_preview_file(codespace_id, rel_path=subpath)
        return Response(content=data, media_type=mime_type)
    except FileNotFoundError:
        return HTMLResponse("<h3>index.html not found in codespace.</h3>", status_code=404)
    except Exception as e:
        return HTMLResponse(f"<h3>Preview error: {e}</h3>", status_code=500)


@router.get("/{codespace_id}/download")
async def download_codespace_bundle(
    codespace_id: str,
    user: UserContext = Depends(get_current_user_context),
):
    """Packages and downloads the entire codespace as a ZIP archive."""
    try:
        zip_bytes = codespace_manager.export_as_zip(codespace_id)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={codespace_id}_bundle.zip"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


