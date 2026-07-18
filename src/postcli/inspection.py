from __future__ import annotations

from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from .models import Asset, stable_asset_id

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def expand_image_paths(paths: list[str | Path]) -> list[Path]:
    """Resolve image files from paths/directories without changing their contents."""
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if path.is_dir():
            files.extend(sorted(candidate for candidate in path.iterdir() if candidate.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES))
        elif path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
            files.append(path)
        else:
            raise ValueError(f"Not a supported image file or directory: {raw_path}")
    unique = {file.resolve(): file for file in files}
    if not unique:
        raise ValueError("No supported images were found.")
    return sorted(unique.values(), key=lambda item: item.name.lower())


def inspect_photo_set(paths: list[str | Path]) -> list[Asset]:
    assets: list[Asset] = []
    for path in expand_image_paths(paths):
        try:
            with Image.open(path) as source:
                width, height = ImageOps.exif_transpose(source).size
                image_format = source.format or path.suffix.lstrip(".").upper()
        except (OSError, ValueError) as error:
            raise ValueError(f"Could not read image: {path}") from error
        orientation = "square" if width == height else "landscape" if width > height else "portrait"
        assets.append(
            Asset(
                id=stable_asset_id(path),
                path=str(path),
                filename=path.name,
                width=width,
                height=height,
                orientation=orientation,
                image_format=image_format.lower(),
            )
        )
    return assets


def create_contact_sheet(assets: list[Asset], output_path: str | Path, cell_size: tuple[int, int] = (280, 240)) -> Path:
    """Create a labelled, downscaled inspection artifact; source files are read only."""
    if not assets:
        raise ValueError("At least one asset is required to create a contact sheet.")
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = min(3, len(assets))
    rows = ceil(len(assets) / columns)
    cell_width, cell_height = cell_size
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "#111111")
    draw = ImageDraw.Draw(sheet)
    for index, asset in enumerate(assets, start=1):
        col, row = (index - 1) % columns, (index - 1) // columns
        left, top = col * cell_width, row * cell_height
        with Image.open(asset.path) as source:
            thumbnail = ImageOps.exif_transpose(source).convert("RGB")
            thumbnail.thumbnail((cell_width - 16, cell_height - 52), Image.Resampling.LANCZOS)
        image_left = left + (cell_width - thumbnail.width) // 2
        sheet.paste(thumbnail, (image_left, top + 8))
        label = f"{index}. {asset.filename}  {asset.width}×{asset.height}"
        draw.rectangle((left, top + cell_height - 38, left + cell_width, top + cell_height), fill="#202020")
        draw.text((left + 8, top + cell_height - 29), label[:42], fill="#ffffff")
    sheet.save(output, "PNG")
    return output
