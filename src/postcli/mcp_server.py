from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from uuid import uuid4
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Image
from mcp.types import CallToolResult, TextContent

from .canvas import canvas_catalog
from .inspection import create_contact_sheet, inspect_photo_set as scan_photo_set
from .models import Asset, Canvas, CarouselPlan
from .project import (
    create_project,
    create_project_folder,
    load_project,
    project_path as manifest_path,
    project_artifact_path,
    require_project_artifact_path,
    save_project,
    update_project,
)
from .render import export_carousel as write_carousel, render_preview
from .templates import template_catalog


def _caption_recommendations(project) -> list[dict[str, object]]:
    """Expose slide captions in tool results so agents can present them to the user."""
    return [{"slide_index": index, "caption": slide.caption} for index, slide in enumerate(project.slides)]


def _music_recommendations(project) -> list[dict[str, str]]:
    """Expose vibe-matched music suggestions in tool results for the agent's chat response."""
    return [recommendation.model_dump() for recommendation in project.music_recommendations]


@dataclass
class CarouselWorkflow:
    assets: list[Asset]
    options: list[CarouselPlan] | None = None
    selected_option: int | None = None
    creation_confirmed: bool = False
    project_manifest: Path | None = None
    previews_rendered: bool = False
    export_confirmed: bool = False


workflows: dict[str, CarouselWorkflow] = {}


def _workflow(workflow_id: str) -> CarouselWorkflow:
    try:
        return workflows[workflow_id]
    except KeyError as error:
        raise ValueError("Unknown or expired workflow. Start again with inspect_photo_set.") from error


def _workflow_for_project(source: str) -> CarouselWorkflow | None:
    manifest = manifest_path(source)
    return next((workflow for workflow in workflows.values() if workflow.project_manifest == manifest), None)


mcp = FastMCP(
    "PostCLI",
    instructions=(
        "Local-first photo carousel composer. Follow this required conversation flow: (1) inspect photos and list "
        "templates/canvas presets; (2) register exactly three plans with submit_carousel_options; (3) write a "
        "normal, user-visible chat message that presents all three options, three post-caption options, and three "
        "music recommendations (song, artist, vibe rationale), then ask the user to choose a template option; "
        "(4) wait for that answer, then call select_carousel_option; (5) write another normal chat message that "
        "summarizes the chosen layout/caption/music and asks for a final proceed confirmation; (6) wait for a clear "
        "yes, call confirm_carousel_creation, then create_carousel. Never hide the required recommendations in "
        "tool arguments, working notes, or project metadata, and never call create_carousel before the explicit "
        "confirmation. After creation, call render_carousel_previews before asking whether the user wants edits. "
        "Wait for their reply; edits invalidate any previous export approval. Only after an explicit user request "
        "to export may you call confirm_carousel_export and export_carousel. Never export directly."
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
    workflow_id = uuid4().hex
    workflows[workflow_id] = CarouselWorkflow(assets=assets)
    metadata = {
        "workflow_id": workflow_id,
        "assets": [asset.model_dump() for asset in assets],
        "contact_sheet_path": str(sheet),
        "notice": "Original photos remain local. Use the labelled contact sheet to identify subjects before proposing a layout.",
        "next_step": "Call list_templates/list_canvas_presets, submit exactly three options, then present them in a normal chat response and wait for the user's selection.",
    }
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
def submit_carousel_options(workflow_id: str, options: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate and register exactly three carousel options before presenting them to the user in chat.

    Each option is a ``CarouselPlan`` and should include per-slide captions, caption recommendations, and music
    recommendations. Do not select or create a project in this call.
    """
    workflow = _workflow(workflow_id)
    if len(options) != 3:
        raise ValueError("Exactly three carousel options are required before asking the user to choose.")
    plans = [CarouselPlan.model_validate(option) for option in options]
    if any(not any(slide.caption or slide.headline for slide in plan.slides) for plan in plans):
        raise ValueError("Each option needs at least one caption recommendation before it can be shown to the user.")
    if sum(len(plan.music_recommendations) for plan in plans) < 3:
        raise ValueError("Provide at least three music recommendations across the three options before asking the user to choose.")
    # Validate each candidate against the inspected local asset set before it is shown to the user.
    for plan in plans:
        create_project(plan, workflow.assets)
    workflow.options = plans
    workflow.selected_option = None
    workflow.creation_confirmed = False
    return {
        "workflow_id": workflow_id,
        "option_names": [plan.name for plan in plans],
        "next_step": (
            "In a normal chat response, show all three options plus three post-caption options and three music "
            "recommendations. Ask which option the user prefers, then wait for their reply."
        ),
    }


@mcp.tool()
def select_carousel_option(workflow_id: str, option_number: int, user_feedback: str) -> dict[str, Any]:
    """Record an option a user chose in chat; call only after they have stated their preference."""
    workflow = _workflow(workflow_id)
    if not workflow.options:
        raise ValueError("Submit three options before recording a user selection.")
    if not 1 <= option_number <= 3:
        raise ValueError("option_number must be 1, 2, or 3.")
    if not user_feedback.strip():
        raise ValueError("Include the user's selection or feedback from the chat.")
    workflow.selected_option = option_number - 1
    workflow.creation_confirmed = False
    selected = workflow.options[workflow.selected_option]
    return {
        "workflow_id": workflow_id,
        "selected_option": option_number,
        "selected_plan": selected.model_dump(),
        "next_step": (
            "In normal chat, summarize this selected layout, its caption recommendation, and music recommendation. "
            "Ask the user whether to proceed with creating the project, then wait for a clear yes."
        ),
    }


@mcp.tool()
def confirm_carousel_creation(workflow_id: str, user_approval: str) -> dict[str, Any]:
    """Record explicit user approval after they reviewed the selected direction in chat."""
    workflow = _workflow(workflow_id)
    if workflow.selected_option is None:
        raise ValueError("The user must select one of the three options before confirming creation.")
    if not user_approval.strip():
        raise ValueError("Include the user's explicit approval from the chat.")
    workflow.creation_confirmed = True
    return {"workflow_id": workflow_id, "next_step": "Call create_carousel to create the approved project folder."}


@mcp.tool()
def create_carousel(workflow_id: str, project_path: str, canvas_width: int = 1080, canvas_height: int = 1350) -> dict[str, Any]:
    """Create a project only after a three-option selection and explicit user confirmation.

    ``project_path`` names the new folder (or a legacy ``.postcli.json`` name whose stem becomes the folder name).
    The selected plan's captions and song suggestions are saved as editable metadata; captions are never rendered
    onto source photos.
    """
    workflow = _workflow(workflow_id)
    if workflow.selected_option is None or not workflow.options:
        raise ValueError("The user must choose one of three submitted options before creation.")
    if not workflow.creation_confirmed:
        raise ValueError("Ask for and record the user's final approval before creation.")
    project = create_project(
        workflow.options[workflow.selected_option],
        workflow.assets,
        Canvas(width=canvas_width, height=canvas_height),
    )
    saved_path = create_project_folder(project, project_path)
    workflow.project_manifest = saved_path
    workflow.previews_rendered = False
    workflow.export_confirmed = False
    return {
        "project_path": str(saved_path),
        "project_directory": str(saved_path.parent),
        "slide_count": len(project.slides),
        "assets": [asset.model_dump() for asset in workflow.assets],
        "caption_recommendations": _caption_recommendations(project),
        "music_recommendations": _music_recommendations(project),
        "next_step": "Call render_carousel_previews, show every preview in chat, and ask the user whether they want any edits before exporting.",
    }


@mcp.tool()
def render_carousel_previews(workflow_id: str) -> CallToolResult:
    """Render every approved slide for user review before asking whether to edit or export."""
    workflow = _workflow(workflow_id)
    if workflow.project_manifest is None:
        raise ValueError("Create the approved project before rendering its previews.")
    project = load_project(workflow.project_manifest)
    previews = [
        render_preview(
            project,
            project_artifact_path(workflow.project_manifest, "previews", f"slide-{index + 1:02d}.png"),
            index,
        )
        for index in range(len(project.slides))
    ]
    workflow.previews_rendered = True
    workflow.export_confirmed = False
    metadata = {
        "workflow_id": workflow_id,
        "project_path": str(workflow.project_manifest),
        "preview_paths": [str(preview) for preview in previews],
        "next_step": "In normal chat, show the previews and ask whether the user wants edits. Wait for their reply; do not export until they explicitly approve it.",
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(metadata))]
        + [Image(path=preview).to_image_content() for preview in previews]
    )


@mcp.tool()
def confirm_carousel_export(workflow_id: str, user_approval: str) -> dict[str, Any]:
    """Record a user's explicit export approval after they reviewed previews and declined further edits."""
    workflow = _workflow(workflow_id)
    if workflow.project_manifest is None:
        raise ValueError("Create a project before requesting export approval.")
    if not workflow.previews_rendered:
        raise ValueError("Render and show every slide preview before asking for export approval.")
    if not user_approval.strip():
        raise ValueError("Include the user's explicit export approval from the chat.")
    workflow.export_confirmed = True
    return {"workflow_id": workflow_id, "next_step": "Call export_carousel with this workflow_id to write the approved files."}


@mcp.tool()
def update_carousel(project_path: str, operation: str, slide_index: int | None = None, values: dict[str, Any] | None = None) -> CallToolResult:
    """Apply a validated project edit and return freshly rendered previews of every slide.

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
    workflow = _workflow_for_project(str(saved_path))
    if workflow:
        workflow.previews_rendered = True
        workflow.export_confirmed = False
    previews = [
        render_preview(
            project,
            project_artifact_path(saved_path, "previews", f"slide-{index + 1:02d}.png"),
            index,
        )
        for index in range(len(project.slides))
    ]
    metadata = {
        "project_path": str(saved_path),
        "slide_count": len(project.slides),
        "preview_paths": [str(preview) for preview in previews],
        "caption_recommendations": _caption_recommendations(project),
        "music_recommendations": _music_recommendations(project),
        "notice": "Fresh previews are included for review after this edit. Ask the user whether they want another edit or approve export; do not export directly.",
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(metadata))]
        + [Image(path=preview).to_image_content() for preview in previews]
    )


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
def export_carousel(workflow_id: str, project_path: str, output_directory: str | None = None, image_format: str = "png") -> dict[str, Any]:
    """Export only after the user reviewed previews and explicitly approved export in chat."""
    workflow = _workflow(workflow_id)
    if workflow.project_manifest != manifest_path(project_path):
        raise ValueError("This workflow does not own the requested project.")
    if not workflow.previews_rendered:
        raise ValueError("Render and show previews before export.")
    if not workflow.export_confirmed:
        raise ValueError("Ask the user whether they want edits and record explicit export approval before exporting.")
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
