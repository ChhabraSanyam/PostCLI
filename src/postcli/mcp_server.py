from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Image
from mcp.types import CallToolResult, TextContent

from .canvas import canvas_catalog
from .inspection import create_contact_sheet, inspect_photo_set as scan_photo_set
from .models import Canvas, CarouselPlan
from .project import create_project, load_project, save_project, update_project
from .render import export_carousel as write_carousel, render_preview
from .templates import template_catalog

mcp = FastMCP(
    "PostCLI",
    instructions=(
        "Local-first photo carousel composer. Before proposing a plan, inspect the assets and list both templates "
        "and canvas presets. Propose three plans using returned asset IDs, then choose one before create_carousel. "
        "Captions are per-slide metadata recommendations; never treat them as text overlays. Use the original local "
        "paths and a selected canvas size when creating the project."
    ),
)


@mcp.tool()
def list_templates() -> list[dict[str, object]]:
    """List adaptive photo-collage templates, including their intent and maximum slot count."""
    return template_catalog()


@mcp.tool()
def list_canvas_presets() -> list[dict[str, object]]:
    """List social-media canvas presets, including IDs, dimensions, and intended use."""
    return canvas_catalog()


@mcp.tool()
def inspect_photo_set(paths: list[str], contact_sheet_path: str | None = None) -> CallToolResult:
    """Inspect local image paths and return dimensions plus a labelled contact-sheet image for subject-aware planning."""
    assets = scan_photo_set(paths)
    output = Path(contact_sheet_path).expanduser() if contact_sheet_path else Path.cwd() / ".postcli-contact-sheet.png"
    sheet = create_contact_sheet(assets, output)
    metadata = {"assets": [asset.model_dump() for asset in assets], "contact_sheet_path": str(sheet), "notice": "Original photos remain local. Use the labelled contact sheet to identify subjects before proposing a layout."}
    # Return explicit MCP content blocks. A list[Any] response makes FastMCP
    # attempt JSON serialization of its Image helper instead of emitting an
    # image-content block over stdio.
    return CallToolResult(
        content=[
            TextContent(type="text", text=json.dumps(metadata)),
            Image(path=sheet).to_image_content(),
        ]
    )


@mcp.tool()
def create_carousel(plan: dict[str, Any], asset_paths: list[str], project_path: str, canvas_width: int = 1080, canvas_height: int = 1350) -> dict[str, Any]:
    """Create an editable local project from a selected plan, original asset paths, and canvas dimensions.

    Plans reference inspected asset IDs. Per-slide ``caption`` values are saved as metadata and are not rendered over photos.
    """
    assets = scan_photo_set(asset_paths)
    parsed_plan = CarouselPlan.model_validate(plan)
    project = create_project(parsed_plan, assets, Canvas(width=canvas_width, height=canvas_height))
    saved_path = save_project(project, project_path)
    return {"project_path": str(saved_path), "slide_count": len(project.slides), "assets": [asset.model_dump() for asset in assets]}


@mcp.tool()
def update_carousel(project_path: str, operation: str, slide_index: int | None = None, values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply a validated project edit.

    Operations are: ``set_canvas`` (values: width, height, optional background), ``reorder_slide`` (from_index,
    to_index), ``reorder_assets`` (from_index, to_index), ``swap_template`` (template_id), ``set_assets``
    (asset_ids), ``set_palette`` (palette), ``set_caption`` (text metadata), ``adjust_asset`` (asset_id plus any
    focus_x, focus_y, zoom, brightness, contrast), ``duplicate_slide``, and ``delete_slide``. Except for
    ``set_canvas`` and ``reorder_slide``, provide a valid slide_index.
    """
    project = load_project(project_path)
    update_project(project, operation, slide_index, values)
    saved_path = save_project(project, project_path)
    return {"project_path": str(saved_path), "slide_count": len(project.slides)}


@mcp.tool()
def render_carousel_preview(project_path: str, preview_path: str, slide_index: int = 0) -> Image:
    """Render one slide to a local PNG and return it for review; caption metadata is not overlaid."""
    project = load_project(project_path)
    rendered = render_preview(project, preview_path, slide_index)
    return Image(path=rendered)


@mcp.tool()
def export_carousel(project_path: str, output_directory: str, image_format: str = "png") -> dict[str, Any]:
    """Export all carousel slides as numbered PNG or JPEG files."""
    project = load_project(project_path)
    outputs = write_carousel(project, output_directory, image_format)
    return {"files": [str(path) for path in outputs], "count": len(outputs)}


def run() -> None:
    mcp.run(transport="stdio")
