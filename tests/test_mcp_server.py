from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
import pytest

from postcli import mcp_server


def test_mcp_tools_are_registered():
    # FastMCP keeps the decorated functions callable and exposes them on the server.
    tool_names = set(mcp_server.mcp._tool_manager._tools)
    assert {
        "inspect_photo_set",
        "list_templates",
        "list_canvas_presets",
        "submit_carousel_options",
        "select_carousel_option",
        "confirm_carousel_creation",
        "create_carousel",
        "render_carousel_previews",
        "confirm_carousel_export",
        "update_carousel",
        "render_carousel_preview",
        "export_carousel",
    }.issubset(tool_names)


def test_mcp_inspection_returns_metadata_and_image(tmp_path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (300, 500), "purple").save(photo)
    result = mcp_server.inspect_photo_set([str(photo)], str(tmp_path / "sheet.png"))

    assert len(result.content) == 2
    assert "portrait" in result.content[0].text
    assert (tmp_path / "sheet.png").exists()


def test_mcp_create_preview_and_export_flow(tmp_path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (600, 900), "orange").save(first)
    Image.new("RGB", (900, 600), "navy").save(second)
    inspection = mcp_server.inspect_photo_set([str(first), str(second)], str(tmp_path / "sheet.png"))
    metadata = json.loads(inspection.content[0].text)
    workflow_id = metadata["workflow_id"]
    asset_ids = [asset["id"] for asset in metadata["assets"]]
    options = [
        {
            "name": f"MCP demo option {number}",
            "slides": [{"template_id": "before-after", "asset_ids": asset_ids, "headline": "Two views"}],
            "music_recommendations": [
                {"title": "Golden Hour", "artist": "JVKE", "rationale": "Warm, upbeat energy for the paired photos."}
            ],
        }
        for number in range(1, 4)
    ]
    project_path = tmp_path / "demo.postcli.json"

    mcp_server.submit_carousel_options(workflow_id, options)
    with pytest.raises(ValueError, match="choose one"):
        mcp_server.create_carousel(workflow_id, str(project_path), 320, 400)
    selected = mcp_server.select_carousel_option(workflow_id, 2, "I prefer option 2")
    assert selected["selected_option"] == 2
    with pytest.raises(ValueError, match="final approval"):
        mcp_server.create_carousel(workflow_id, str(project_path), 320, 400)
    mcp_server.confirm_carousel_creation(workflow_id, "Yes, please create it")
    created = mcp_server.create_carousel(workflow_id, str(project_path), 320, 400)
    with pytest.raises(ValueError, match="Render and show previews"):
        mcp_server.export_carousel(workflow_id, created["project_path"])
    reviewed = mcp_server.render_carousel_previews(workflow_id)
    assert len(reviewed.content) == 2
    updated = mcp_server.update_carousel(
        created["project_path"],
        "adjust_asset",
        0,
        {"asset_id": asset_ids[0], "brightness": 1.2},
    )
    rendered = mcp_server.render_carousel_preview(created["project_path"])
    with pytest.raises(ValueError, match="explicit export approval"):
        mcp_server.export_carousel(workflow_id, created["project_path"])
    mcp_server.confirm_carousel_export(workflow_id, "The previews look good, please export.")
    exported = mcp_server.export_carousel(workflow_id, created["project_path"])

    update_metadata = json.loads(updated.content[0].text)
    assert Path(created["project_path"]).exists()
    assert Path(created["project_directory"]) == Path(created["project_path"]).parent
    assert created["caption_recommendations"] == [{"slide_index": 0, "caption": "Two views"}]
    assert created["music_recommendations"][0]["title"] == "Golden Hour"
    assert update_metadata["slide_count"] == 1
    assert update_metadata["caption_recommendations"] == [{"slide_index": 0, "caption": "Two views"}]
    assert update_metadata["music_recommendations"][0]["artist"] == "JVKE"
    assert len(updated.content) == 2
    assert Path(update_metadata["preview_paths"][0]) == Path(created["project_path"]).parent / "previews" / "slide-01.png"
    assert rendered.path == Path(created["project_path"]).parent / "previews" / "slide-01.png"
    assert [Path(item).name for item in exported["files"]] == ["01-mcp-demo-option-2.png"]
    assert Path(exported["files"][0]).parent == Path(created["project_path"]).parent / "exports"
