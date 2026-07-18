from __future__ import annotations

from pathlib import Path

from .models import AssetAdjustment, CarouselPlan, PostProject, Slide, TextLayer
from .templates import get_template


def project_path(path: str | Path) -> Path:
    destination = Path(path).expanduser().resolve()
    return destination if destination.suffix == ".json" else destination.with_suffix(".postcli.json")


def create_project(plan: CarouselPlan, assets, canvas=None) -> PostProject:
    from .models import Canvas

    asset_map = {asset.id: asset for asset in assets}
    slides: list[Slide] = []
    for plan_slide in plan.slides:
        template = get_template(plan_slide.template_id)
        if len(plan_slide.asset_ids) > template.slot_count:
            raise ValueError(f"'{template.id}' accepts at most {template.slot_count} images, received {len(plan_slide.asset_ids)}.")
        unknown = set(plan_slide.asset_ids) - set(asset_map)
        if unknown:
            raise ValueError(f"Plan references unknown asset IDs: {', '.join(sorted(unknown))}")
        layers = [TextLayer(text=plan_slide.headline)] if plan_slide.headline else []
        slides.append(
            Slide(
                template_id=template.id,
                assets=[AssetAdjustment(asset_id=asset_id) for asset_id in plan_slide.asset_ids],
                palette=plan_slide.palette,
                layers=layers,
            )
        )
    return PostProject(name=plan.name, canvas=canvas or Canvas(), assets=list(assets), slides=slides, music_recommendations=plan.music_recommendations)


def save_project(project: PostProject, destination: str | Path) -> Path:
    path = project_path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_project(source: str | Path) -> PostProject:
    path = project_path(source)
    return PostProject.model_validate_json(path.read_text(encoding="utf-8"))


def update_project(project: PostProject, operation: str, slide_index: int | None = None, values: dict | None = None) -> PostProject:
    """Apply a small validated edit operation to a project in memory."""
    values = values or {}
    if operation == "reorder_slide":
        source, target = int(values["from_index"]), int(values["to_index"])
        if not (0 <= source < len(project.slides) and 0 <= target < len(project.slides)):
            raise ValueError("Slide indices are out of range.")
        project.slides.insert(target, project.slides.pop(source))
        return project
    if slide_index is None or not 0 <= slide_index < len(project.slides):
        raise ValueError("A valid slide_index is required for this operation.")
    slide = project.slides[slide_index]
    if operation == "swap_template":
        template = get_template(str(values["template_id"]))
        if len(slide.assets) > template.slot_count:
            raise ValueError("The selected template has too few slots for this slide's assets.")
        slide.template_id = template.id
    elif operation == "set_assets":
        template = get_template(slide.template_id)
        asset_ids = list(values["asset_ids"])
        known = {asset.id for asset in project.assets}
        if not asset_ids:
            raise ValueError("A slide needs at least one asset.")
        if len(asset_ids) > template.slot_count:
            raise ValueError("The selected template has too few slots for these assets.")
        if not set(asset_ids).issubset(known):
            raise ValueError("Assets must be known project assets.")
        slide.assets = [AssetAdjustment(asset_id=asset_id) for asset_id in asset_ids]
    elif operation == "set_palette":
        palette = list(values["palette"])
        if not palette:
            raise ValueError("A palette requires at least one colour.")
        slide.palette = palette
    elif operation == "set_headline":
        text = str(values["text"])
        existing = next((layer for layer in slide.layers if isinstance(layer, TextLayer)), None)
        if existing:
            existing.text = text
        else:
            slide.layers.append(TextLayer(text=text))
    elif operation == "adjust_asset":
        adjustment = next((item for item in slide.assets if item.asset_id == values["asset_id"]), None)
        if not adjustment:
            raise ValueError("The asset is not assigned to this slide.")
        for field in ("focus_x", "focus_y", "zoom", "brightness", "contrast"):
            if field in values:
                setattr(adjustment, field, values[field])
        # Revalidate numeric bounds after mutation.
        replacement = AssetAdjustment.model_validate(adjustment.model_dump())
        slide.assets[slide.assets.index(adjustment)] = replacement
    elif operation == "duplicate_slide":
        if len(project.slides) == 10:
            raise ValueError("A carousel can contain at most 10 slides.")
        project.slides.insert(slide_index + 1, slide.model_copy(deep=True))
    elif operation == "delete_slide":
        if len(project.slides) == 1:
            raise ValueError("A carousel requires at least one slide.")
        project.slides.pop(slide_index)
    else:
        raise ValueError(f"Unknown edit operation: {operation}")
    return project
