from __future__ import annotations

import json
from pathlib import Path

import typer

from .inspection import create_contact_sheet, inspect_photo_set
from .mcp_server import run as run_mcp
from .models import CarouselPlan, CarouselPlanSlide
from .templates import get_template
from .project import create_project, load_project, save_project
from .render import export_carousel, render_preview
from .templates import template_catalog
from .tui import PostEditor

app = typer.Typer(help="Local-first, MCP-guided photo carousel composer.", no_args_is_help=True)


@app.command("templates")
def templates() -> None:
    """List built-in adaptive collage templates."""
    typer.echo(json.dumps(template_catalog(), indent=2))


@app.command("scan")
def scan(
    paths: list[Path] = typer.Argument(..., help="Image files or directories to inspect."),
    contact_sheet: Path = typer.Option(Path("contact-sheet.png"), "--contact-sheet", "-o"),
) -> None:
    """Inspect local images and write a labelled contact sheet."""
    assets = inspect_photo_set(paths)
    output = create_contact_sheet(assets, contact_sheet)
    typer.echo(json.dumps({"assets": [asset.model_dump() for asset in assets], "contact_sheet": str(output)}, indent=2))


@app.command("new")
def new(
    project: Path = typer.Argument(..., help="Destination project .postcli.json path."),
    images: list[Path] = typer.Argument(..., help="Photos for the first slide."),
    template_id: str = typer.Option("clean-grid", "--template"),
    name: str = typer.Option("My carousel", "--name"),
) -> None:
    """Create an editable project without an agent, using one collage slide."""
    assets = inspect_photo_set(images)
    slot_count = get_template(template_id).slot_count
    plan = CarouselPlan(
        name=name,
        slides=[
            CarouselPlanSlide(template_id=template_id, asset_ids=[asset.id for asset in assets[index : index + slot_count]])
            for index in range(0, len(assets), slot_count)
        ],
    )
    created = create_project(plan, assets)
    saved = save_project(created, project)
    typer.echo(f"Created {saved}")


@app.command("open")
def open_project(project: Path = typer.Argument(...)) -> None:
    """Print the local project's summary."""
    loaded = load_project(project)
    typer.echo(f"{loaded.name}: {len(loaded.slides)} slide(s), {len(loaded.assets)} asset(s), {loaded.canvas.width}×{loaded.canvas.height}")


@app.command("edit")
def edit(project: Path = typer.Argument(...)) -> None:
    """Open the keyboard-first terminal editor."""
    PostEditor(project).run()


@app.command("preview")
def preview(
    project: Path = typer.Argument(...),
    output: Path = typer.Option(Path("preview.png"), "--output", "-o"),
    slide: int = typer.Option(1, "--slide", min=1),
) -> None:
    """Render one slide to PNG."""
    loaded = load_project(project)
    if slide > len(loaded.slides):
        raise typer.BadParameter("Slide is out of range.")
    typer.echo(render_preview(loaded, output, slide - 1))


@app.command("export")
def export(
    project: Path = typer.Argument(...),
    output_directory: Path = typer.Argument(...),
    image_format: str = typer.Option("png", "--format"),
) -> None:
    """Export every slide as a numbered PNG/JPEG file."""
    outputs = export_carousel(load_project(project), output_directory, image_format)
    typer.echo("\n".join(str(item) for item in outputs))


@app.command("mcp")
def mcp() -> None:
    """Start the stdio MCP server for Codex or Claude Code."""
    run_mcp()


if __name__ == "__main__":
    app()
