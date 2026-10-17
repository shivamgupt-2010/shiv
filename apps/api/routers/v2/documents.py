"""
ShivAI V2 Document & Multimodal Analysis Endpoints.
Exposes POST /v2/documents/analyze.
"""
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, status, HTTPException
from pydantic import BaseModel, Field

from apps.api.dependencies import get_current_user_context, UserContext, rate_limit_middleware_check
from core.documents.parser import document_parser, ParsedDocument
from core.multimodal.processor import multimodal_processor
from core.v2.request_service import V2RequestService, V2ChatRequest

router = APIRouter(tags=["V2 Document & Multimodal Analysis"])


class DocumentAnalysisResponse(BaseModel):
    filename: str
    file_type: str
    total_characters: int
    chunks_count: int
    analysis: str


@router.post(
    "/v2/documents/analyze",
    response_model=DocumentAnalysisResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_middleware_check)],
)
@router.post(
    "/api/v2/documents/analyze",
    response_model=DocumentAnalysisResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
    dependencies=[Depends(rate_limit_middleware_check)],
)
async def analyze_document_or_image(
    file: UploadFile = File(..., description="Document (PDF, code, txt) or Image (PNG, JPG, WEBP)"),
    prompt: Optional[str] = Form(default=None, description="Specific instructions or query regarding the document"),
    user: UserContext = Depends(get_current_user_context),
) -> DocumentAnalysisResponse:
    """
    Parses and analyzes uploaded documents (PDF, Markdown, Source Code) or images.
    Returns structured content breakdown and AI-driven analysis.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    filename = file.filename or "uploaded_file"
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    # Image analysis
    if ext in ("png", "jpg", "jpeg", "webp", "gif"):
        mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
        result = await multimodal_processor.analyze_image(
            image_bytes=file_bytes,
            mime_type=mime,
            prompt=prompt,
        )
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Vision analysis failed."))

        return DocumentAnalysisResponse(
            filename=filename,
            file_type="image",
            total_characters=len(file_bytes),
            chunks_count=1,
            analysis=result.get("analysis", ""),
        )

    # Document / Code / PDF parsing
    parsed = document_parser.parse(file_bytes, filename)
    user_query = prompt or "Summarize the key information and structure of this document."

    # Build context from chunks
    preview_text = parsed.full_text[:12000] # Fit in standard context
    doc_prompt = (
        f"Document Name: {filename} ({parsed.file_type})\n\n"
        f"--- Document Excerpt ---\n{preview_text}\n\n"
        f"User Query: {user_query}\n\n"
        f"Provide a clear, accurate, and structured analysis based strictly on the document provided."
    )

    service = V2RequestService()
    req = V2ChatRequest(message=doc_prompt, mode="quality")
    res = await service.execute_chat(req, user_id=user.user_id, request_id="doc-analysis")

    return DocumentAnalysisResponse(
        filename=filename,
        file_type=parsed.file_type,
        total_characters=parsed.total_characters,
        chunks_count=parsed.total_chunks,
        analysis=res.response,
    )
