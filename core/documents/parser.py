"""
ShivAI Document Ingestion & Parsing Subsystem.
Parses PDFs, plain text, code files, CSVs, and markdown.
Performs semantic chunking with metadata and token estimation.
"""
import io
import re
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("shivai.documents.parser")


class DocumentChunk(BaseModel):
    chunk_index: int
    text: str
    token_estimate: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    filename: str
    file_type: str
    total_characters: int
    total_chunks: int
    chunks: List[DocumentChunk] = Field(default_factory=list)
    full_text: str


class DocumentParser:
    """Parses various file types into structured chunks."""

    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str, filename: str, file_type: str) -> List[DocumentChunk]:
        """Splits long text into overlapping chunks."""
        chunks: List[DocumentChunk] = []
        if not text:
            return chunks

        start = 0
        idx = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            # Try to snap to the nearest newline or sentence boundary
            if end < text_len:
                boundary = text.rfind("\n", start + self.chunk_size // 2, end)
                if boundary != -1:
                    end = boundary + 1

            chunk_content = text[start:end].strip()
            if chunk_content:
                token_est = len(chunk_content) // 4
                chunks.append(
                    DocumentChunk(
                        chunk_index=idx,
                        text=chunk_content,
                        token_estimate=token_est,
                        metadata={
                            "filename": filename,
                            "file_type": file_type,
                            "char_start": start,
                            "char_end": end,
                        },
                    )
                )
                idx += 1

            start += self.chunk_size - self.chunk_overlap

        return chunks

    def parse_pdf(self, file_bytes: bytes, filename: str) -> str:
        """Extracts text from PDF bytes."""
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages_text = []
            for i, page in enumerate(reader.pages):
                t = page.extract_text() or ""
                if t.strip():
                    pages_text.append(f"--- Page {i+1} ---\n{t.strip()}")
            return "\n\n".join(pages_text)
        except ImportError:
            logger.warning("pypdf not yet imported. Trying basic text stream extraction.")
            # Fallback simple string extraction
            clean = re.sub(rb"[^\x20-\x7E\n\r\t]", b" ", file_bytes)
            return clean.decode("ascii", errors="ignore")
        except Exception as e:
            logger.error(f"Error parsing PDF '{filename}': {e}")
            return f"[Error parsing PDF: {e}]"

    def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """Entrypoint for parsing arbitrary files."""
        ext = filename.split(".")[-1].lower() if "." in filename else "txt"
        file_type = ext

        if ext == "pdf":
            full_text = self.parse_pdf(file_bytes, filename)
        else:
            try:
                full_text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                full_text = file_bytes.decode("latin-1", errors="replace")

        chunks = self.chunk_text(full_text, filename, file_type)
        return ParsedDocument(
            filename=filename,
            file_type=file_type,
            total_characters=len(full_text),
            total_chunks=len(chunks),
            chunks=chunks,
            full_text=full_text,
        )


# Global parser instance
document_parser = DocumentParser()
