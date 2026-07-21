from __future__ import annotations

import asyncio

from PIL import Image
from textual.widgets import Static

from postcli.inspection import inspect_photo_set
from postcli.models import CarouselPlan, CarouselPlanSlide
from postcli.project import create_project, load_project, save_project
from postcli.tui import PostEditor


def test_editor_starts_and_applies_keyboard_actions(tmp_path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (300, 500), "teal").save(photo)
    asset = inspect_photo_set([photo])[0]
    project = create_project(
        CarouselPlan(name="Editor test", slides=[CarouselPlanSlide(template_id="clean-grid", asset_ids=[asset.id])]),
        [asset],
    )
    source = save_project(project, tmp_path / "editor")

    async def drive_editor() -> None:
        app = PostEditor(source)
        async with app.run_test() as pilot:
            assert (source.parent / "previews" / "slide-01.png").exists()
            assert "Inline preview unavailable" in str(app.query_one("#preview", Static).render())
            summary = str(app.query_one("#summary", Static).render())
            assert "1. photo" in summary
            assert asset.id not in summary
            await pilot.press("]", "d", "r", "x", "q")
            await pilot.pause()

    asyncio.run(drive_editor())

    saved = load_project(source)
    assert len(saved.slides) == 1
    assert saved.slides[0].template_id == "triptych"
    assert (source.parent / "previews" / "slide-02.png").exists()


def test_editor_reorders_and_adjusts_selected_photo(tmp_path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (300, 500), "teal").save(first)
    Image.new("RGB", (300, 500), "orange").save(second)
    assets = inspect_photo_set([first, second])
    project = create_project(
        CarouselPlan(name="Photo edits", slides=[CarouselPlanSlide(template_id="clean-grid", asset_ids=[asset.id for asset in assets])]),
        assets,
    )
    source = save_project(project, tmp_path / "photo-edits")

    async def drive_editor() -> None:
        app = PostEditor(source)
        async with app.run_test() as pilot:
            await pilot.press("full_stop", "h", "j", "w", "b", "c", "B", "C", "q")
            await pilot.pause()

    asyncio.run(drive_editor())

    saved = load_project(source)
    selected = saved.slides[0].assets[1]
    assert [item.asset_id for item in saved.slides[0].assets] == [assets[1].id, assets[0].id]
    assert (selected.focus_x, selected.focus_y) == (0.45, 0.55)
    assert (selected.zoom, selected.brightness, selected.contrast) == (1.1, 1.0, 1.0)


def test_editor_cycles_canvas_presets(tmp_path):
    photo = tmp_path / "photo.png"
    Image.new("RGB", (300, 500), "teal").save(photo)
    asset = inspect_photo_set([photo])[0]
    project = create_project(
        CarouselPlan(name="Canvas edit", slides=[CarouselPlanSlide(template_id="clean-grid", asset_ids=[asset.id])]),
        [asset],
    )
    source = save_project(project, tmp_path / "canvas-edit")

    async def drive_editor() -> None:
        app = PostEditor(source)
        async with app.run_test() as pilot:
            await pilot.press("g", "q")
            await pilot.pause()

    asyncio.run(drive_editor())

    saved = load_project(source)
    assert (saved.canvas.width, saved.canvas.height) == (1080, 1080)


def test_editor_moves_photo_to_the_next_slide(tmp_path):
    paths = [tmp_path / f"photo-{index}.png" for index in range(3)]
    for path, color in zip(paths, ("teal", "orange", "purple")):
        Image.new("RGB", (300, 500), color).save(path)
    assets = inspect_photo_set(paths)
    project = create_project(
        CarouselPlan(
            name="Continuous",
            slides=[
                CarouselPlanSlide(template_id="clean-grid", asset_ids=[assets[0].id, assets[1].id]),
                CarouselPlanSlide(template_id="clean-grid", asset_ids=[assets[2].id]),
            ],
        ),
        assets,
    )
    source = save_project(project, tmp_path / "continuous")

    async def drive_editor() -> None:
        app = PostEditor(source)
        async with app.run_test() as pilot:
            await pilot.press("a", "full_stop", "q")
            await pilot.pause()

    asyncio.run(drive_editor())

    saved = load_project(source)
    assert [[item.asset_id for item in slide.assets] for slide in saved.slides] == [
        [assets[0].id],
        [assets[1].id, assets[2].id],
    ]


def test_editor_compacts_long_photo_names(tmp_path):
    photo = tmp_path / "a-very-long-descriptive-photograph-name-from-the-camera-roll.jpeg"
    Image.new("RGB", (300, 500), "teal").save(photo)
    asset = inspect_photo_set([photo])[0]
    project = create_project(
        CarouselPlan(name="Long names", slides=[CarouselPlanSlide(template_id="clean-grid", asset_ids=[asset.id])]),
        [asset],
    )
    source = save_project(project, tmp_path / "long-names")

    async def drive_editor() -> None:
        app = PostEditor(source)
        async with app.run_test() as pilot:
            label = app._asset_name(asset.id)
            assert label.startswith("a-very-long-")
            assert label.endswith("…")
            assert ".jpeg" not in label
            assert len(label) == 24
            await pilot.press("q")

    asyncio.run(drive_editor())
