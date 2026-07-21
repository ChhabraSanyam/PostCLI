from __future__ import annotations

import secrets
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Resize
from textual.markup import escape
from textual.widgets import Footer, Header, Static

from .canvas import CANVAS_PRESETS, preset_for_size
from .kitty import cursor_to, delete_image, fit_placement, place_png, supports_graphics
from .project import load_project, project_path, save_project, update_project
from .render import render_slide
from .templates import TEMPLATES


class PostEditor(App[None]):
    """Small keyboard-first local editor for reviewing and changing a carousel."""

    TITLE = "PostCLI Editor"
    CSS = """
    #body {
        height: 1fr;
    }

    #summary {
        padding: 1 2;
    }

    #preview {
        height: 1fr;
        padding: 0;
    }
    """
    BINDINGS = [
        Binding("n", "next_slide", "Next/Previous", key_display="n/p"),
        Binding("p", "previous_slide", show=False),
        Binding("[", "previous_template", show=False),
        Binding("]", "next_template", "Template +/-", key_display="]/["),
        Binding("a", "next_asset", "Next photo"),
        Binding("comma", "move_asset_left", "Move photo left/right", key_display=",/."),
        Binding("full_stop", "move_asset_right", show=False),
        Binding("d", "duplicate", "Duplicate"),
        Binding("x", "delete", "Delete"),
        Binding("g", "next_canvas", "Canvas"),
        Binding("h", "focus_left", show=False),
        Binding("l", "focus_right", show=False),
        Binding("k", "focus_up", show=False),
        Binding("j", "focus_down", show=False),
        Binding("w", "zoom_in", show=False),
        Binding("s", "zoom_out", show=False),
        Binding("b", "brightness_up", show=False),
        Binding("B", "brightness_down", show=False),
        Binding("c", "contrast_up", show=False),
        Binding("C", "contrast_down", show=False),
        Binding("r", "reset_asset", "Reset photo"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, source: str | Path) -> None:
        super().__init__()
        self.source = project_path(source)
        self.project = load_project(self.source)
        self.slide_index = 0
        self.asset_index = 0
        self._kitty_image_id = secrets.randbelow(2**31 - 1) + 1
        self._cell_aspect = 0.5

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="body"):
            yield Static(id="summary")
            yield Static(id="preview")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_summary()

    def _asset_name(self, asset_id: str, max_length: int = 18) -> str:
        """Return a compact, recognizable filename for the terminal summary."""
        filename = next((asset.filename for asset in self.project.assets if asset.id == asset_id), asset_id)
        stem = Path(filename).stem
        return stem if len(stem) <= max_length else f"{stem[:max_length - 1]}…"

    def _refresh_summary(self, message: str = "") -> None:
        slide = self.project.slides[self.slide_index]
        selected = self._selected_asset()
        preset = preset_for_size(self.project.canvas.width, self.project.canvas.height)
        canvas_name = preset.name if preset else "Custom canvas"
        assigned = ", ".join(
            f"{'●' if index == self.asset_index else '○'} {index + 1}. "
            f"{escape(self._asset_name(item.asset_id))}"
            for index, item in enumerate(slide.assets)
        )
        self.query_one("#summary", Static).update(
            f"[b]{self.project.name}[/b]  •  Slide {self.slide_index + 1}/{len(self.project.slides)}\n\n"
            f"Canvas: [cyan]{canvas_name}[/cyan] · {self.project.canvas.width}×{self.project.canvas.height} · press g to change\n"
            f"Template: [cyan]{slide.template_id}[/cyan]\nPhotos: {assigned}\n"
            f"Selected {self.asset_index + 1}/{len(slide.assets)} — crop {selected.focus_x:.2f}, {selected.focus_y:.2f} · "
            f"zoom {selected.zoom:.1f} · brightness {selected.brightness:.1f} · contrast {selected.contrast:.1f}\n\n"
            "[dim]Edit selected: h/l crop x · k/j crop y · w/s zoom · b/B brightness · c/C contrast[/dim]"
            + (f"\n\n[green]{message}[/green]" if message else "")
        )
        self._refresh_preview()

    def _selected_asset(self):
        assets = self.project.slides[self.slide_index].assets
        self.asset_index = min(self.asset_index, len(assets) - 1)
        return assets[self.asset_index]

    def _preview_path(self) -> Path:
        return self.source.parent / "previews" / f"slide-{self.slide_index + 1:02d}.png"

    def _refresh_preview(self) -> Path:
        """Render the active slide and send it to a Kitty-compatible terminal."""
        image = render_slide(self.project, self.slide_index)
        preview_path = self._preview_path()
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(preview_path, "PNG")
        preview = self.query_one("#preview", Static)
        if supports_graphics():
            preview.update("")
            self.call_after_refresh(self._place_kitty_preview, preview_path)
        else:
            preview.update(
                "[b]Inline preview unavailable[/b]\n\n"
                "Use a Kitty-compatible terminal, or set [cyan]POSTCLI_IMAGE_PROTOCOL=kitty[/cyan], "
                "to display the rendered PNG here.\n\n"
                "The full-resolution preview is saved to:\n[dim]"
                + str(preview_path)
                + "[/dim]"
            )
        return preview_path

    def _place_kitty_preview(self, preview_path: Path) -> None:
        """Place the PNG at the preview widget's screen coordinates."""
        if self._driver is None or not supports_graphics():
            return
        region = self.query_one("#preview", Static).region
        if region.width < 1 or region.height < 1:
            return
        columns, rows, offset_x, offset_y = fit_placement(
            region.width,
            region.height,
            self.project.canvas.width,
            self.project.canvas.height,
            self._cell_aspect,
        )
        self._driver.write(delete_image(self._kitty_image_id))
        self._driver.write(cursor_to(region.x + offset_x + 1, region.y + offset_y + 1))
        self._driver.write(place_png(preview_path.read_bytes(), self._kitty_image_id, columns, rows))

    def on_resize(self, event: Resize) -> None:
        if event.pixel_size is not None and event.size.width and event.size.height:
            cell_width = event.pixel_size.width / event.size.width
            cell_height = event.pixel_size.height / event.size.height
            self._cell_aspect = cell_width / cell_height
        if self.is_mounted:
            self._refresh_preview()

    def on_unmount(self) -> None:
        if self._driver is not None and supports_graphics():
            self._driver.write(delete_image(self._kitty_image_id))

    def _save(self, message: str) -> None:
        save_project(self.project, self.source)
        self._refresh_summary(message)

    def action_next_slide(self) -> None:
        self.slide_index = (self.slide_index + 1) % len(self.project.slides)
        self.asset_index = 0
        self._refresh_summary()

    def action_previous_slide(self) -> None:
        self.slide_index = (self.slide_index - 1) % len(self.project.slides)
        self.asset_index = 0
        self._refresh_summary()

    def action_next_asset(self) -> None:
        self.asset_index = (self.asset_index + 1) % len(self.project.slides[self.slide_index].assets)
        self._refresh_summary()

    def action_next_canvas(self) -> None:
        current = preset_for_size(self.project.canvas.width, self.project.canvas.height)
        current_index = CANVAS_PRESETS.index(current) if current else -1
        preset = CANVAS_PRESETS[(current_index + 1) % len(CANVAS_PRESETS)]
        update_project(self.project, "set_canvas", values={"width": preset.width, "height": preset.height})
        self._save(f"Canvas changed to {preset.name} ({preset.width}×{preset.height}).")

    def _move_asset(self, direction: int) -> None:
        target = self.asset_index + direction
        if 0 <= target < len(self.project.slides[self.slide_index].assets):
            update_project(
                self.project,
                "reorder_assets",
                self.slide_index,
                {"from_index": self.asset_index, "to_index": target},
            )
            self.asset_index = target
            self._save(f"Moved selected photo to slot {target + 1}.")
            return

        old_asset_count = len(self.project.slides[self.slide_index].assets)
        try:
            update_project(
                self.project,
                "move_asset",
                self.slide_index,
                {"asset_index": self.asset_index, "direction": direction},
            )
        except ValueError as error:
            self._refresh_summary(str(error))
            return
        if direction == 1:
            self.slide_index += 0 if old_asset_count == 1 else 1
            self.asset_index = 0
        else:
            self.slide_index -= 1
            self.asset_index = len(self.project.slides[self.slide_index].assets) - 1
        self._save("Moved selected photo to the adjacent slide.")

    def action_move_asset_left(self) -> None:
        self._move_asset(-1)

    def action_move_asset_right(self) -> None:
        self._move_asset(1)

    def _adjust_selected(self, field: str, amount: float, label: str) -> None:
        selected = self._selected_asset()
        lower, upper = (0.0, 1.0) if field.startswith("focus_") else ((1.0, 3.0) if field == "zoom" else (0.1, 3.0))
        value = round(min(upper, max(lower, getattr(selected, field) + amount)), 2)
        update_project(self.project, "adjust_asset", self.slide_index, {"asset_id": selected.asset_id, field: value})
        self._save(f"{label}: {value:.2f}")

    def action_focus_left(self) -> None:
        self._adjust_selected("focus_x", -0.05, "Crop horizontal")

    def action_focus_right(self) -> None:
        self._adjust_selected("focus_x", 0.05, "Crop horizontal")

    def action_focus_up(self) -> None:
        self._adjust_selected("focus_y", -0.05, "Crop vertical")

    def action_focus_down(self) -> None:
        self._adjust_selected("focus_y", 0.05, "Crop vertical")

    def action_zoom_in(self) -> None:
        self._adjust_selected("zoom", 0.1, "Zoom")

    def action_zoom_out(self) -> None:
        self._adjust_selected("zoom", -0.1, "Zoom")

    def action_brightness_up(self) -> None:
        self._adjust_selected("brightness", 0.1, "Brightness")

    def action_brightness_down(self) -> None:
        self._adjust_selected("brightness", -0.1, "Brightness")

    def action_contrast_up(self) -> None:
        self._adjust_selected("contrast", 0.1, "Contrast")

    def action_contrast_down(self) -> None:
        self._adjust_selected("contrast", -0.1, "Contrast")

    def action_reset_asset(self) -> None:
        selected = self._selected_asset()
        update_project(
            self.project,
            "adjust_asset",
            self.slide_index,
            {
                "asset_id": selected.asset_id,
                "focus_x": 0.5,
                "focus_y": 0.5,
                "zoom": 1.0,
                "brightness": 1.0,
                "contrast": 1.0,
            },
        )
        self._save("Selected photo reset.")

    def _switch_template(self, direction: int) -> None:
        template_ids = list(TEMPLATES)
        current = self.project.slides[self.slide_index].template_id
        start = template_ids.index(current)
        candidate = template_ids[(start + direction) % len(template_ids)]
        try:
            update_project(self.project, "swap_template", self.slide_index, {"template_id": candidate})
        except ValueError as error:
            self._refresh_summary(str(error))
            return
        self.asset_index = min(self.asset_index, len(self.project.slides[self.slide_index].assets) - 1)
        self._save(f"Template changed to {candidate}; extra photos carried forward.")

    def action_next_template(self) -> None:
        self._switch_template(1)

    def action_previous_template(self) -> None:
        self._switch_template(-1)

    def action_duplicate(self) -> None:
        update_project(self.project, "duplicate_slide", self.slide_index)
        self.slide_index += 1
        self._save("Slide duplicated.")

    def action_delete(self) -> None:
        try:
            update_project(self.project, "delete_slide", self.slide_index)
        except ValueError as error:
            self._refresh_summary(str(error))
            return
        self.slide_index = min(self.slide_index, len(self.project.slides) - 1)
        self.asset_index = 0
        self._save("Slide deleted.")
