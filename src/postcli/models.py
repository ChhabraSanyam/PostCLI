from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class Asset(BaseModel):
    id: str
    path: str
    filename: str
    width: int
    height: int
    orientation: Literal["portrait", "landscape", "square"]
    image_format: str


class AssetAdjustment(BaseModel):
    asset_id: str
    focus_x: float = Field(default=0.5, ge=0, le=1)
    focus_y: float = Field(default=0.5, ge=0, le=1)
    zoom: float = Field(default=1.0, ge=1, le=3)
    brightness: float = Field(default=1.0, ge=0.1, le=3)
    contrast: float = Field(default=1.0, ge=0.1, le=3)


class TextLayer(BaseModel):
    kind: Literal["text"] = "text"
    text: str
    x: float = Field(default=0.06, ge=0, le=1)
    y: float = Field(default=0.08, ge=0, le=1)
    color: str = "#ffffff"
    size: int = Field(default=48, ge=10, le=240)


class ShapeLayer(BaseModel):
    kind: Literal["rectangle"] = "rectangle"
    x: float = Field(default=0.04, ge=0, le=1)
    y: float = Field(default=0.04, ge=0, le=1)
    width: float = Field(default=0.2, gt=0, le=1)
    height: float = Field(default=0.04, gt=0, le=1)
    color: str = "#ffffff"


Layer = TextLayer | ShapeLayer


class Slide(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    template_id: str
    assets: list[AssetAdjustment] = Field(default_factory=list)
    palette: list[str] = Field(default_factory=lambda: ["#151515", "#f8f5ef"])
    layers: list[Layer] = Field(default_factory=list)
    caption: str | None = None

    @model_validator(mode="after")
    def migrate_legacy_text_layers(self) -> "Slide":
        """Keep captions as metadata and remove legacy on-image headline layers."""
        legacy_headline = next((layer.text for layer in self.layers if isinstance(layer, TextLayer)), None)
        if self.caption is None:
            self.caption = legacy_headline
        self.layers = [layer for layer in self.layers if not isinstance(layer, TextLayer)]
        return self


class Canvas(BaseModel):
    width: int = Field(default=1080, ge=64, le=6000)
    height: int = Field(default=1350, ge=64, le=6000)
    background: str = "#151515"


class MusicRecommendation(BaseModel):
    title: str
    artist: str
    rationale: str


class PostProject(BaseModel):
    version: int = 1
    name: str
    canvas: Canvas = Field(default_factory=Canvas)
    assets: list[Asset] = Field(default_factory=list)
    slides: list[Slide] = Field(default_factory=list, min_length=1, max_length=10)
    music_recommendations: list[MusicRecommendation] = Field(default_factory=list)

    @field_validator("slides")
    @classmethod
    def carousel_size(cls, value: list[Slide]) -> list[Slide]:
        if len(value) > 10:
            raise ValueError("A carousel can contain at most 10 slides")
        return value


class CarouselPlanSlide(BaseModel):
    template_id: str
    asset_ids: list[str] = Field(min_length=1)
    palette: list[str] = Field(default_factory=lambda: ["#151515", "#f8f5ef"])
    caption: str | None = None
    headline: str | None = None
    rationale: str | None = None


class CarouselPlan(BaseModel):
    name: str
    slides: list[CarouselPlanSlide] = Field(min_length=1, max_length=10)
    rationale: str | None = None
    music_recommendations: list[MusicRecommendation] = Field(default_factory=list)

    @field_validator("slides")
    @classmethod
    def plan_size(cls, value: list[CarouselPlanSlide]) -> list[CarouselPlanSlide]:
        if len(value) > 10:
            raise ValueError("A carousel plan can contain at most 10 slides")
        return value


def stable_asset_id(path: Path) -> str:
    """Keep IDs stable across rescans without modifying the user's file."""
    import hashlib

    return hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12]
