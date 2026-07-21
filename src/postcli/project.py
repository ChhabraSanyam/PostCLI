from __future__ import annotations

from pathlib import Path

from .models import AssetAdjustment, Canvas, CarouselPlan, PostProject, Slide
from .templates import get_template

PROJECT_MANIFEST = "project.postcli.json"


def project_path(path: str | Path) -> Path:
    destination = Path(path).expanduser().resolve()
    if destination.suffix == ".json":
        return destination
    return destination / PROJECT_MANIFEST


def create_project_folder(project: PostProject, destination: str | Path) -> Path:
    """Create one clean, self-contained folder for a newly created project."""
    requested = Path(destination).expanduser().resolve()
    # Accept the old ``name.postcli.json`` shape as a request for a ``name/``
    # workspace, rather than leaving a manifest in the caller's directory.
    if requested.suffix == ".json":
        stem = requested.name.removesuffix(".postcli.json").removesuffix(".json")
        requested = requested.parent / stem
    if requested.exists():
        raise FileExistsError(f"Project folder already exists: {requested}")
    requested.mkdir(parents=True)
    return save_project(project, requested / PROJECT_MANIFEST)


def project_root(source: str | Path) -> Path:
    """Return the folder owning the persisted manifest and its generated files."""
    return project_path(source).parent


def project_artifact_path(source: str | Path, category: str, filename: str) -> Path:
    """Build a generated-artifact path inside a project's dedicated folder."""
    if category not in {"previews", "exports"}:
        raise ValueError(f"Unsupported project artifact category: {category}")
    root = project_root(source)
    return root / category / filename


def require_project_artifact_path(source: str | Path, candidate: str | Path) -> Path:
    """Reject generated files outside the dedicated project directory."""
    root = project_root(source).resolve()
    requested = Path(candidate).expanduser()
    path = requested.resolve() if requested.is_absolute() else (root / requested).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"Generated files must stay inside the project folder: {root}") from error
    return path


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
        slides.append(
            Slide(
                template_id=template.id,
                assets=[AssetAdjustment(asset_id=asset_id) for asset_id in plan_slide.asset_ids],
                palette=plan_slide.palette,
                caption=plan_slide.caption or plan_slide.headline,
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


def _push_overflow_forward(project: PostProject, slide_index: int, new_slide_template: str) -> None:
    """Keep each slide within its template capacity, carrying overflow forward."""
    index = slide_index
    while True:
        slide = project.slides[index]
        capacity = get_template(slide.template_id).slot_count
        if len(slide.assets) <= capacity:
            return
        overflow = slide.assets[capacity:]
        slide.assets = slide.assets[:capacity]
        index += 1
        if index == len(project.slides):
            if len(project.slides) == 10:
                raise ValueError("No room to carry photos forward; a carousel can contain at most 10 slides.")
            project.slides.append(
                Slide(
                    template_id=new_slide_template,
                    assets=[],
                    palette=slide.palette.copy(),
                )
            )
        project.slides[index].assets = overflow + project.slides[index].assets


def _switch_template_with_overflow(project: PostProject, slide_index: int, template_id: str) -> None:
    slide = project.slides[slide_index]
    slide.template_id = template_id
    _push_overflow_forward(project, slide_index, template_id)


def _move_asset_between_slides(project: PostProject, slide_index: int, asset_index: int, direction: int) -> None:
    """Move one photo across a slide boundary and preserve every photo in order."""
    if direction not in {-1, 1}:
        raise ValueError("Photo movement direction must be -1 or 1.")
    source = project.slides[slide_index]
    if not 0 <= asset_index < len(source.assets):
        raise ValueError("Photo index is out of range.")
    if direction == -1:
        if slide_index == 0:
            raise ValueError("Photo is already at the start of the carousel.")
        destination = project.slides[slide_index - 1]
        moved = source.assets.pop(asset_index)
        displaced = None
        if len(destination.assets) == get_template(destination.template_id).slot_count:
            displaced = destination.assets.pop()
        destination.assets.append(moved)
        if displaced is not None:
            source.assets.insert(0, displaced)
        if not source.assets:
            project.slides.pop(slide_index)
        return

    destination_index = slide_index + 1
    if destination_index == len(project.slides):
        if len(project.slides) == 10:
            raise ValueError("Photo is already at the end of a full 10-slide carousel.")
        project.slides.append(
            Slide(template_id=source.template_id, assets=[], palette=source.palette.copy())
        )
    moved = source.assets.pop(asset_index)
    destination = project.slides[destination_index]
    destination.assets.insert(0, moved)
    _push_overflow_forward(project, destination_index, source.template_id)
    if not source.assets:
        project.slides.pop(slide_index)


def update_project(project: PostProject, operation: str, slide_index: int | None = None, values: dict | None = None) -> PostProject:
    """Apply a small validated edit operation to a project in memory."""
    values = values or {}
    if operation == "reorder_slide":
        source, target = int(values["from_index"]), int(values["to_index"])
        if not (0 <= source < len(project.slides) and 0 <= target < len(project.slides)):
            raise ValueError("Slide indices are out of range.")
        project.slides.insert(target, project.slides.pop(source))
        return project
    if operation == "set_canvas":
        project.canvas = Canvas(
            width=int(values["width"]),
            height=int(values["height"]),
            background=str(values.get("background", project.canvas.background)),
        )
        return project
    if slide_index is None or not 0 <= slide_index < len(project.slides):
        raise ValueError("A valid slide_index is required for this operation.")
    slide = project.slides[slide_index]
    if operation == "swap_template":
        template = get_template(str(values["template_id"]))
        working = project.model_copy(deep=True)
        _switch_template_with_overflow(working, slide_index, template.id)
        project.slides = working.slides
    elif operation == "move_asset":
        asset_index = int(values["asset_index"])
        direction = int(values["direction"])
        working = project.model_copy(deep=True)
        _move_asset_between_slides(working, slide_index, asset_index, direction)
        project.slides = working.slides
    elif operation == "reorder_assets":
        source, target = int(values["from_index"]), int(values["to_index"])
        if not (0 <= source < len(slide.assets) and 0 <= target < len(slide.assets)):
            raise ValueError("Photo indices are out of range.")
        slide.assets.insert(target, slide.assets.pop(source))
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
    elif operation in {"set_caption", "set_headline"}:
        text = str(values["text"])
        slide.caption = text
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
