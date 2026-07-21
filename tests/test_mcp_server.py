from __future__ import annotations

from pathlib import Path

from PIL import Image

from postcli import mcp_server


def test_mcp_tools_are_registered():
    # FastMCP keeps the decorated functions callable and exposes them on the server.
    tool_names = set(mcp_server.mcp._tool_manager._tools)
    assert {"inspect_photo_set", "list_templates", "list_canvas_presets", "create_carousel", "update_carousel", "render_carousel_preview", "export_carousel"}.issubset(tool_names)


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
    assets = mcp_server.scan_photo_set([first, second])
    plan = {
        "name": "MCP demo",
        "slides": [{"template_id": "before-after", "asset_ids": [asset.id for asset in assets], "headline": "Two views"}],
    }
    project_path = tmp_path / "demo.postcli.json"

    created = mcp_server.create_carousel(plan, [str(first), str(second)], str(project_path), 320, 400)
    rendered = mcp_server.render_carousel_preview(created["project_path"])
    exported = mcp_server.export_carousel(created["project_path"])

    assert Path(created["project_path"]).exists()
    assert Path(created["project_directory"]) == Path(created["project_path"]).parent
    assert rendered.path == Path(created["project_path"]).parent / "previews" / "slide-01.png"
    assert [Path(item).name for item in exported["files"]] == ["01-mcp-demo.png"]
    assert Path(exported["files"][0]).parent == Path(created["project_path"]).parent / "exports"
