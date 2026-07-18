from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static

from .project import load_project, save_project, update_project
from .render import render_preview
from .templates import TEMPLATES


class PostEditor(App[None]):
    """Small keyboard-first local editor for reviewing and changing a carousel."""

    TITLE = "PostCLI Editor"
    BINDINGS = [
        Binding("n", "next_slide", "Next"),
        Binding("p", "previous_slide", "Previous"),
        Binding("[", "previous_template", "Template −"),
        Binding("]", "next_template", "Template +"),
        Binding("d", "duplicate", "Duplicate"),
        Binding("x", "delete", "Delete"),
        Binding("r", "render", "Render preview"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, source: str | Path) -> None:
        super().__init__()
        self.source = Path(source).expanduser().resolve()
        self.project = load_project(self.source)
        self.slide_index = 0

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="summary")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_summary()

    def _refresh_summary(self, message: str = "") -> None:
        slide = self.project.slides[self.slide_index]
        assigned = ", ".join(item.asset_id for item in slide.assets) or "No assets"
        self.query_one("#summary", Static).update(
            f"[b]{self.project.name}[/b]  •  Slide {self.slide_index + 1}/{len(self.project.slides)}\n\n"
            f"Template: [cyan]{slide.template_id}[/cyan]\nAssigned assets: {assigned}\nPalette: {', '.join(slide.palette)}\n\n"
            "[dim]n/p navigate · [/] swap template · d duplicate · x delete · r render preview · q quit[/dim]"
            + (f"\n\n[green]{message}[/green]" if message else "")
        )

    def _save(self, message: str) -> None:
        save_project(self.project, self.source)
        self._refresh_summary(message)

    def action_next_slide(self) -> None:
        self.slide_index = (self.slide_index + 1) % len(self.project.slides)
        self._refresh_summary()

    def action_previous_slide(self) -> None:
        self.slide_index = (self.slide_index - 1) % len(self.project.slides)
        self._refresh_summary()

    def _switch_template(self, direction: int) -> None:
        template_ids = list(TEMPLATES)
        current = self.project.slides[self.slide_index].template_id
        start = template_ids.index(current)
        for offset in range(1, len(template_ids) + 1):
            candidate = template_ids[(start + direction * offset) % len(template_ids)]
            if TEMPLATES[candidate].slot_count >= len(self.project.slides[self.slide_index].assets):
                update_project(self.project, "swap_template", self.slide_index, {"template_id": candidate})
                self._save(f"Template changed to {candidate}.")
                return

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
        self._save("Slide deleted.")

    def action_render(self) -> None:
        preview = self.source.parent / "previews" / f"slide-{self.slide_index + 1:02d}.png"
        render_preview(self.project, preview, self.slide_index)
        self._refresh_summary(f"Preview written to {preview}")
