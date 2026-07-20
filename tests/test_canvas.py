import pytest

from postcli.canvas import canvas_catalog, get_canvas_preset, preset_for_size
from postcli.models import CarouselPlan, CarouselPlanSlide
from postcli.project import create_project, update_project


def test_canvas_presets_are_findable_and_catalogued():
    preset = get_canvas_preset("story-vertical")

    assert (preset.width, preset.height) == (1080, 1920)
    assert preset_for_size(1080, 1920) == preset
    assert any(item["id"] == "instagram-square" for item in canvas_catalog())
    with pytest.raises(ValueError, match="Unknown canvas"):
        get_canvas_preset("not-a-preset")


def test_project_canvas_can_be_updated_without_a_slide_index(tmp_path):
    photo = tmp_path / "photo.png"
    photo.write_bytes(b"not an image")
    # Build a minimal valid project without relying on a specific source image.
    from postcli.models import Asset

    asset = Asset(id="asset", path=str(photo), filename=photo.name, width=100, height=100, orientation="square", image_format="png")
    project = create_project(
        CarouselPlan(name="Canvas", slides=[CarouselPlanSlide(template_id="clean-grid", asset_ids=[asset.id])]),
        [asset],
    )

    update_project(project, "set_canvas", values={"width": 1080, "height": 1920})

    assert (project.canvas.width, project.canvas.height) == (1080, 1920)
