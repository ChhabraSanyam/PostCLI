from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanvasPreset:
    id: str
    name: str
    width: int
    height: int
    description: str


CANVAS_PRESETS: tuple[CanvasPreset, ...] = (
    CanvasPreset("instagram-portrait", "Instagram portrait", 1080, 1350, "4:5 feed portrait"),
    CanvasPreset("instagram-square", "Instagram square", 1080, 1080, "1:1 feed post"),
    CanvasPreset("story-vertical", "Stories / Reels", 1080, 1920, "9:16 full-screen vertical"),
    CanvasPreset("social-landscape", "LinkedIn / X landscape", 1200, 628, "1.91:1 landscape post"),
    CanvasPreset("widescreen-video", "YouTube / social video", 1920, 1080, "16:9 widescreen"),
)


def get_canvas_preset(preset_id: str) -> CanvasPreset:
    for preset in CANVAS_PRESETS:
        if preset.id == preset_id:
            return preset
    available = ", ".join(preset.id for preset in CANVAS_PRESETS)
    raise ValueError(f"Unknown canvas preset '{preset_id}'. Choose one of: {available}.")


def preset_for_size(width: int, height: int) -> CanvasPreset | None:
    return next((preset for preset in CANVAS_PRESETS if (preset.width, preset.height) == (width, height)), None)


def canvas_catalog() -> list[dict[str, object]]:
    return [
        {
            "id": preset.id,
            "name": preset.name,
            "width": preset.width,
            "height": preset.height,
            "description": preset.description,
        }
        for preset in CANVAS_PRESETS
    ]
