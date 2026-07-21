from __future__ import annotations

import json
import tempfile
from uuid import uuid4
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Image
from mcp.types import CallToolResult, TextContent

from .canvas import canvas_catalog
from .inspection import create_contact_sheet, inspect_photo_set as scan_photo_set
from .models import Canvas, CarouselPlan
from .project import (
    create_project,
    create_project_folder,
    load_project,
    project_artifact_path,
    require_project_artifact_path,
    save_project,
    update_project,
)
from .render import export_carousel as write_carousel, render_preview
from .templates import template_catalog

mcp = FastMCP(
    "PostCLI",
    instructions=(
        "Local-first photo carousel composer. Before proposing a plan, inspect the assets and list both templates "
        "and canvas presets. Propose three plans using returned asset IDs, then choose one before create_carousel. "
        "Include a concise caption recommendation for each slide. Use the original local paths and a selected "
        "canvas size when creating the project."
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
    output = (
        Path(contact_sheet_path).expanduser()
        if contact_sheet_path
        else Path(tempfile.gettempdir()) / f"postcli-contact-sheet-{uuid4().hex}.png"
    )
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
    """Create an editable local project in a new dedicated project folder.

    ``project_path`` names the new folder (or a legacy ``.postcli.json`` name whose stem becomes the folder name).
    Plans reference inspected asset IDs and may include a concise caption recommendation for each slide.
    """
    assets = scan_photo_set(asset_paths)
    parsed_plan = CarouselPlan.model_validate(plan)
    project = create_project(parsed_plan, assets, Canvas(width=canvas_width, height=canvas_height))
    saved_path = create_project_folder(project, project_path)
    return {
        "project_path": str(saved_path),
        "project_directory": str(saved_path.parent),
        "slide_count": len(project.slides),
        "assets": [asset.model_dump() for asset in assets],
    }


@mcp.tool()
def update_carousel(project_path: str, operation: str, slide_index: int | None = None, values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Apply a validated project edit.

    Operations are: ``set_canvas`` (values: width, height, optional background), ``reorder_slide`` (from_index,
    to_index), ``reorder_assets`` (from_index, to_index), ``move_asset`` (asset_index, direction -1 or 1),
    ``swap_template`` (template_id; overflow carries forward), ``set_assets`` (asset_ids), ``set_palette``
    (palette), ``set_caption`` (text), ``adjust_asset`` (asset_id plus any focus_x, focus_y, zoom, brightness,
    contrast), ``duplicate_slide``, and ``delete_slide``. Except for
    ``set_canvas`` and ``reorder_slide``, provide a valid slide_index.
    """
    project = load_project(project_path)
    update_project(project, operation, slide_index, values)
    saved_path = save_project(project, project_path)
    return {"project_path": str(saved_path), "slide_count": len(project.slides)}


@mcp.tool()
def render_carousel_preview(project_path: str, preview_path: str | None = None, slide_index: int = 0) -> Image:
    """Render one slide to the project's previews folder and return it for review."""
    project = load_project(project_path)
    if not 0 <= slide_index < len(project.slides):
        raise ValueError("Slide index is out of range.")
    destination = (
        require_project_artifact_path(project_path, preview_path)
        if preview_path
        else project_artifact_path(project_path, "previews", f"slide-{slide_index + 1:02d}.png")
    )
    rendered = render_preview(project, destination, slide_index)
    return Image(path=rendered)


@mcp.tool()
def export_carousel(project_path: str, output_directory: str | None = None, image_format: str = "png") -> dict[str, Any]:
    """Export all slides under the project's exports folder as numbered PNG or JPEG files."""
    project = load_project(project_path)
    destination = (
        require_project_artifact_path(project_path, output_directory)
        if output_directory
        else project_artifact_path(project_path, "exports", "")
    )
    outputs = write_carousel(project, destination, image_format)
    return {"files": [str(path) for path in outputs], "count": len(outputs)}


def run() -> None:
    mcp.run(transport="stdio")
