from __future__ import annotations

import asyncio

from PIL import Image

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
            await pilot.press("]", "d", "r", "x", "q")
            await pilot.pause()

    asyncio.run(drive_editor())

    saved = load_project(source)
    assert len(saved.slides) == 1
    assert saved.slides[0].template_id == "triptych"
    assert (tmp_path / "previews" / "slide-02.png").exists()
