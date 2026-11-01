"""Presentation Layer: Markdown Tearsheet Renderer for Maritime Risk Audits.

Formats complete CorridorAuditResult instances into institutional underwriter tearsheets
with unclamped POT-GPD tail metrics, operational posture, and macro regime multipliers.
"""

from __future__ import annotations

from typing import Any


class MarkdownTearsheetRenderer:
    """Customer-facing Markdown tearsheet renderer conforming to ReportRendererPort."""

    def render(self, bundle: Any) -> str:
        """Render complete audit result into institutional Markdown tearsheet."""
        if hasattr(bundle, "to_markdown_string"):
            return str(bundle.to_markdown_string())
        if hasattr(bundle, "to_markdown"):
            return str(bundle.to_markdown())
        return str(bundle)


def render_tearsheet(result: Any) -> str:
    """Helper function to render a tearsheet from CorridorAuditResult."""
    renderer = MarkdownTearsheetRenderer()
    return renderer.render(result)


__all__ = ["MarkdownTearsheetRenderer", "render_tearsheet"]
