from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class TemplateSpec:
    id: str
    name: str
    description: str
    slots: tuple[Slot, ...]

    @property
    def slot_count(self) -> int:
        return len(self.slots)


TEMPLATES: dict[str, TemplateSpec] = {
    "clean-grid": TemplateSpec("clean-grid", "Clean grid", "Balanced two-photo grid", (Slot(0.04, 0.04, 0.92, 0.44), Slot(0.04, 0.52, 0.92, 0.44))),
    "triptych": TemplateSpec("triptych", "Triptych", "Three equal moments in a clean row", (Slot(0.04, 0.06, 0.28, 0.88), Slot(0.36, 0.06, 0.28, 0.88), Slot(0.68, 0.06, 0.28, 0.88))),
    "asymmetric-grid": TemplateSpec("asymmetric-grid", "Asymmetric grid", "Hero image with two supporting moments", (Slot(0.04, 0.04, 0.58, 0.92), Slot(0.66, 0.04, 0.30, 0.44), Slot(0.66, 0.52, 0.30, 0.44))),
    "polaroid-stack": TemplateSpec("polaroid-stack", "Polaroid stack", "Layered, informal three-image composition", (Slot(0.10, 0.10, 0.56, 0.54), Slot(0.37, 0.28, 0.54, 0.54), Slot(0.12, 0.61, 0.48, 0.30))),
    "scrapbook": TemplateSpec("scrapbook", "Scrapbook", "Four-photo memory board", (Slot(0.05, 0.06, 0.42, 0.38), Slot(0.53, 0.10, 0.40, 0.30), Slot(0.10, 0.52, 0.34, 0.38), Slot(0.52, 0.48, 0.40, 0.42))),
    "film-strip": TemplateSpec("film-strip", "Film strip", "Three frames with a cinematic rhythm", (Slot(0.07, 0.13, 0.86, 0.22), Slot(0.07, 0.39, 0.86, 0.22), Slot(0.07, 0.65, 0.86, 0.22))),
    "before-after": TemplateSpec("before-after", "Before / after", "Side-by-side visual comparison", (Slot(0.04, 0.12, 0.44, 0.76), Slot(0.52, 0.12, 0.44, 0.76))),
    "mosaic": TemplateSpec("mosaic", "Mosaic", "Five-image celebration collage", (Slot(0.04, 0.04, 0.56, 0.50), Slot(0.64, 0.04, 0.32, 0.26), Slot(0.64, 0.34, 0.32, 0.20), Slot(0.04, 0.58, 0.42, 0.38), Slot(0.50, 0.58, 0.46, 0.38))),
}


def get_template(template_id: str) -> TemplateSpec:
    try:
        return TEMPLATES[template_id]
    except KeyError as error:
        raise ValueError(f"Unknown template '{template_id}'.") from error


def template_catalog() -> list[dict[str, object]]:
    return [
        {"id": spec.id, "name": spec.name, "description": spec.description, "slot_count": spec.slot_count}
        for spec in TEMPLATES.values()
    ]
