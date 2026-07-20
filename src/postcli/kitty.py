from __future__ import annotations

import base64
import os
from collections.abc import Mapping


_ESC = "\x1b"
_ST = "\x1b\\"
_CHUNK_SIZE = 4096


def supports_graphics(environment: Mapping[str, str] | None = None) -> bool:
    """Return whether the environment advertises Kitty graphics support."""
    environment = os.environ if environment is None else environment
    requested_protocol = environment.get("POSTCLI_IMAGE_PROTOCOL", "").lower()
    terminal = environment.get("TERM", "").lower()
    return requested_protocol == "kitty" or "KITTY_WINDOW_ID" in environment or "kitty" in terminal or "ghostty" in terminal


def delete_image(image_id: int) -> str:
    """Delete an image and all of its placements without waiting for a reply."""
    return f"{_ESC}_Ga=d,d=I,i={image_id},q=2{_ST}"


def place_png(png: bytes, image_id: int, columns: int, rows: int) -> str:
    """Transmit a PNG and place it at the current cursor using Kitty graphics."""
    encoded = base64.standard_b64encode(png).decode("ascii")
    chunks = [encoded[index : index + _CHUNK_SIZE] for index in range(0, len(encoded), _CHUNK_SIZE)] or [""]
    commands: list[str] = []
    for index, chunk in enumerate(chunks):
        more = 1 if index < len(chunks) - 1 else 0
        metadata = f"a=T,f=100,i={image_id},c={columns},r={rows},C=1,z=1,q=2," if index == 0 else ""
        commands.append(f"{_ESC}_G{metadata}m={more};{chunk}{_ST}")
    return "".join(commands)


def cursor_to(column: int, row: int) -> str:
    """Move the terminal cursor to a one-based cell coordinate."""
    return f"{_ESC}[{row};{column}H"


def fit_placement(
    available_columns: int,
    available_rows: int,
    image_width: int,
    image_height: int,
    cell_aspect: float,
) -> tuple[int, int, int, int]:
    """Fit an image into a terminal rectangle without distorting its aspect ratio.

    Returns the placement columns, rows, and zero-based offsets inside the
    available rectangle. ``cell_aspect`` is the physical width / height of one
    terminal cell.
    """
    image_cell_aspect = (image_width / image_height) / cell_aspect
    available_aspect = available_columns / available_rows
    if available_aspect > image_cell_aspect:
        rows = available_rows
        columns = max(1, round(rows * image_cell_aspect))
    else:
        columns = available_columns
        rows = max(1, round(columns / image_cell_aspect))
    return columns, rows, (available_columns - columns) // 2, (available_rows - rows) // 2
