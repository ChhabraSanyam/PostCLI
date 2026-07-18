from __future__ import annotations

import hashlib

from PIL import Image

from postcli.inspection import create_contact_sheet, inspect_photo_set


def make_image(path, size, color):
    Image.new("RGB", size, color).save(path)


def test_inspection_and_contact_sheet_leave_sources_untouched(tmp_path):
    portrait = tmp_path / "portrait.jpg"
    landscape = tmp_path / "landscape.png"
    make_image(portrait, (400, 700), "red")
    make_image(landscape, (800, 400), "blue")
    before = hashlib.sha256(portrait.read_bytes()).hexdigest()

    assets = inspect_photo_set([portrait, landscape])
    output = create_contact_sheet(assets, tmp_path / "sheet.png")

    assert [asset.orientation for asset in assets] == ["landscape", "portrait"]
    assert output.exists()
    assert Image.open(output).size[0] > 0
    assert hashlib.sha256(portrait.read_bytes()).hexdigest() == before


def test_inspection_expands_a_directory(tmp_path):
    make_image(tmp_path / "one.png", (100, 100), "green")
    (tmp_path / "not-image.txt").write_text("not an image")

    assets = inspect_photo_set([tmp_path])

    assert len(assets) == 1
    assert assets[0].filename == "one.png"
