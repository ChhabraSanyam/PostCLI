from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from .models import Asset, AssetAdjustment, PostProject, ShapeLayer, Slide
from .templates import get_template

def _cover_asset(asset: Asset, adjustment: AssetAdjustment, size: tuple[int, int]) -> Image.Image:
    with Image.open(asset.path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    image = ImageEnhance.Brightness(image).enhance(adjustment.brightness)
    image = ImageEnhance.Contrast(image).enhance(adjustment.contrast)
    target_width, target_height = size
    scale = max(target_width / image.width, target_height / image.height) * adjustment.zoom
    resized = image.resize((max(target_width, round(image.width * scale)), max(target_height, round(image.height * scale))), Image.Resampling.LANCZOS)
    left = round((resized.width - target_width) * adjustment.focus_x)
    top = round((resized.height - target_height) * adjustment.focus_y)
    left = max(0, min(left, resized.width - target_width))
    top = max(0, min(top, resized.height - target_height))
    return resized.crop((left, top, left + target_width, top + target_height))


def render_slide(project: PostProject, slide_index: int) -> Image.Image:
    slide = project.slides[slide_index]
    canvas = Image.new("RGB", (project.canvas.width, project.canvas.height), project.canvas.background)
    template = get_template(slide.template_id)
    assets = {asset.id: asset for asset in project.assets}
    for index, adjustment in enumerate(slide.assets):
        if index >= template.slot_count:
            break
        source = assets[adjustment.asset_id]
        slot = template.slots[index]
        box = (
            round(slot.x * project.canvas.width),
            round(slot.y * project.canvas.height),
            max(1, round(slot.width * project.canvas.width)),
            max(1, round(slot.height * project.canvas.height)),
        )
        image = _cover_asset(source, adjustment, (box[2], box[3]))
        canvas.paste(image, box[:2])
        if slide.template_id == "polaroid-stack":
            frame = ImageDraw.Draw(canvas)
            frame.rectangle((box[0] - 6, box[1] - 6, box[0] + box[2] + 6, box[1] + box[3] + 20), outline="#f8f5ef", width=12)
    draw = ImageDraw.Draw(canvas)
    for layer in slide.layers:
        if isinstance(layer, ShapeLayer):
            draw.rectangle(
                (
                    round(layer.x * project.canvas.width),
                    round(layer.y * project.canvas.height),
                    round((layer.x + layer.width) * project.canvas.width),
                    round((layer.y + layer.height) * project.canvas.height),
                ),
                fill=layer.color,
            )
    return canvas


def render_preview(project: PostProject, destination: str | Path, slide_index: int = 0) -> Path:
    path = Path(destination).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    render_slide(project, slide_index).save(path, "PNG")
    return path


def export_carousel(project: PostProject, destination: str | Path, image_format: str = "png") -> list[Path]:
    directory = Path(destination).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    extension = "jpg" if image_format.lower() in {"jpg", "jpeg"} else "png"
    written: list[Path] = []
    for index in range(len(project.slides)):
        output = directory / f"{index + 1:02d}-{project.name.lower().replace(' ', '-')}.{extension}"
        image = render_slide(project, index)
        image.save(output, "JPEG" if extension == "jpg" else "PNG", quality=95)
        written.append(output)
    return written
