from __future__ import annotations

from PIL import Image
import pytest

from postcli.inspection import inspect_photo_set
from postcli.models import CarouselPlan, CarouselPlanSlide
from postcli.project import create_project, create_project_folder, load_project, project_artifact_path, save_project, update_project
from postcli.render import export_carousel, render_preview


def make_image(path, size, color):
    Image.new("RGB", size, color).save(path)


def fixture_assets(tmp_path):
    paths = []
    for index, (size, color) in enumerate([((500, 800), "red"), ((800, 500), "blue"), ((600, 600), "green"), ((500, 800), "yellow")]):
        path = tmp_path / f"asset-{index}.png"
        make_image(path, size, color)
        paths.append(path)
    return inspect_photo_set(paths)


def test_create_save_edit_render_and_export_carousel(tmp_path):
    assets = fixture_assets(tmp_path)
    plan = CarouselPlan(
        name="Summer test",
        slides=[
            CarouselPlanSlide(template_id="asymmetric-grid", asset_ids=[asset.id for asset in assets[:3]], headline="Weekend"),
            CarouselPlanSlide(template_id="before-after", asset_ids=[asset.id for asset in assets[2:]], palette=["#222222", "#eeeeee"]),
        ],
    )
    project = create_project(plan, assets)
    assert project.slides[0].caption == "Weekend"
    assert project.slides[0].layers == []
    project.canvas.width = 400
    project.canvas.height = 500
    source = save_project(project, tmp_path / "summer")
    update_project(project, "adjust_asset", 0, {"asset_id": assets[0].id, "focus_x": 0.2, "brightness": 1.2})
    update_project(project, "reorder_assets", 0, {"from_index": 0, "to_index": 2})
    update_project(project, "reorder_slide", values={"from_index": 1, "to_index": 0})
    save_project(project, source)

    preview = render_preview(load_project(source), tmp_path / "preview.png")
    outputs = export_carousel(load_project(source), tmp_path / "exports")

    assert Image.open(preview).size == (400, 500)
    assert [path.name for path in outputs] == ["01-summer-test.png", "02-summer-test.png"]
    assert all(path.exists() for path in outputs)
    assert load_project(source).slides[1].assets[-1].asset_id == assets[0].id
    assert load_project(source).slides[1].assets[-1].brightness == 1.2


def test_project_rejects_unknown_assets_and_invalid_template_capacity(tmp_path):
    assets = fixture_assets(tmp_path)
    unknown = CarouselPlan(name="Bad", slides=[CarouselPlanSlide(template_id="clean-grid", asset_ids=["not-here"])])
    with pytest.raises(ValueError, match="unknown asset"):
        create_project(unknown, assets)
    too_many = CarouselPlan(name="Bad", slides=[CarouselPlanSlide(template_id="clean-grid", asset_ids=[asset.id for asset in assets[:3]])])
    with pytest.raises(ValueError, match="at most"):
        create_project(too_many, assets)


def test_slide_edit_boundaries(tmp_path):
    assets = fixture_assets(tmp_path)
    project = create_project(CarouselPlan(name="One", slides=[CarouselPlanSlide(template_id="clean-grid", asset_ids=[assets[0].id])]), assets)
    with pytest.raises(ValueError, match="at least one"):
        update_project(project, "delete_slide", 0)
    with pytest.raises(ValueError, match="few slots"):
        update_project(project, "set_assets", 0, {"asset_ids": [asset.id for asset in assets[:3]]})


def test_template_overflow_and_photo_moves_flow_between_slides(tmp_path):
    assets = fixture_assets(tmp_path)
    project = create_project(
        CarouselPlan(
            name="Flow",
            slides=[
                CarouselPlanSlide(template_id="asymmetric-grid", asset_ids=[asset.id for asset in assets[:3]]),
                CarouselPlanSlide(template_id="before-after", asset_ids=[assets[3].id]),
            ],
        ),
        assets,
    )

    update_project(project, "swap_template", 0, {"template_id": "clean-grid"})
    assert [[item.asset_id for item in slide.assets] for slide in project.slides] == [
        [assets[0].id, assets[1].id],
        [assets[2].id, assets[3].id],
    ]

    update_project(project, "move_asset", 0, {"asset_index": 1, "direction": 1})
    assert [[item.asset_id for item in slide.assets] for slide in project.slides] == [
        [assets[0].id],
        [assets[1].id, assets[2].id],
        [assets[3].id],
    ]


def test_new_project_owns_its_manifest_and_generated_artifacts(tmp_path):
    assets = fixture_assets(tmp_path)
    project = create_project(
        CarouselPlan(name="Contained", slides=[CarouselPlanSlide(template_id="clean-grid", asset_ids=[assets[0].id])]),
        assets,
    )
    manifest = create_project_folder(project, tmp_path / "contained")

    assert manifest == tmp_path / "contained" / "project.postcli.json"
    assert manifest.exists()
    preview = render_preview(load_project(manifest), project_artifact_path(manifest, "previews", "slide-01.png"))
    exports = export_carousel(load_project(manifest), project_artifact_path(manifest, "exports", ""))

    assert preview.parent == tmp_path / "contained" / "previews"
    assert exports[0].parent == tmp_path / "contained" / "exports"
    with pytest.raises(FileExistsError, match="already exists"):
        create_project_folder(project, tmp_path / "contained")
