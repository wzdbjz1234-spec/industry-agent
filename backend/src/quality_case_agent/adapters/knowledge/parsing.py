"""Small, deterministic Markdown/PDF parsers.

PDF support is intentionally optional at import time. Deployments that accept PDF files install
``pypdf``; the rest of the application can still run with the local Markdown parser.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Protocol, cast

from quality_case_agent.domain.knowledge.models import DocumentSection


class DocumentParser(Protocol):
    def parse(self, payload: bytes, file_name: str) -> Sequence[DocumentSection]:
        """Parse bytes into citation-preserving sections."""


@dataclass(frozen=True, slots=True)
class MarkdownDocumentParser:
    """Parse headings and paragraphs without depending on a Markdown package."""

    def parse(self, payload: bytes, file_name: str) -> Sequence[DocumentSection]:
        if not file_name.lower().endswith((".md", ".markdown", ".txt")):
            raise ValueError("Markdown parser only accepts .md, .markdown or .txt files")
        text = payload.decode("utf-8-sig").strip()
        if not text:
            raise ValueError("document content must not be empty")
        sections: list[DocumentSection] = []
        current_title = "document"
        current_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                if current_lines:
                    sections.append(DocumentSection(current_title, "\n".join(current_lines).strip()))
                    current_lines = []
                current_title = stripped.lstrip("# ").strip()[:128] or "document"
            elif stripped:
                current_lines.append(line.rstrip())
        if current_lines:
            sections.append(DocumentSection(current_title, "\n".join(current_lines).strip()))
        return tuple(sections or (DocumentSection(current_title, text),))


@dataclass(frozen=True, slots=True)
class PdfDocumentParser:
    """Extract text per page using the optional ``pypdf`` adapter."""

    def parse(self, payload: bytes, file_name: str) -> Sequence[DocumentSection]:
        if not file_name.lower().endswith(".pdf"):
            raise ValueError("PDF parser only accepts .pdf files")
        try:
            import importlib

            PdfReader = cast(Any, importlib.import_module("pypdf").PdfReader)
        except ImportError as exc:  # pragma: no cover - depends on deployment extras
            raise RuntimeError("PDF ingestion requires the optional pypdf dependency") from exc
        reader = PdfReader(BytesIO(payload))
        sections: list[DocumentSection] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                first_line = text.splitlines()[0].strip()[:128] or f"page-{page_number}"
                sections.append(DocumentSection(first_line, text, page_number))
        if not sections:
            raise ValueError("PDF contains no extractable text")
        return tuple(sections)
