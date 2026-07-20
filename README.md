# PostCLI

PostCLI is a local-first terminal app for turning a folder of photos into editable collage slides and social carousels. It never modifies source images. An MCP server lets Codex or Claude Code inspect a labelled thumbnail sheet, recommend an arrangement, create the project, and apply structured edits.

## Install and run

```bash
uv sync --group dev --no-editable
uv run --no-sync postcli scan ~/Pictures/trip --contact-sheet trip-sheet.png
uv run --no-sync postcli templates
uv run --no-sync postcli new trip.postcli.json ~/Pictures/trip --template scrapbook --name "Goa weekend" --canvas instagram-portrait
POSTCLI_IMAGE_PROTOCOL=kitty uv run --no-sync postcli edit trip.postcli.json
uv run --no-sync postcli export trip.postcli.json exports --format png

// Development (Rebuild package)
uv sync --group dev --no-editable --reinstall-package postcli
```

`postcli new` makes a standalone project. For agent-directed carousels, start the MCP server with `uv run --no-sync postcli mcp`.

Kitty and compatible terminals display the preview inline through the Kitty graphics protocol, in the Edit TUI. In a compatible terminal that does not advertise support, set `POSTCLI_IMAGE_PROTOCOL=kitty` once in your shell profile. Other terminals still receive a full-resolution PNG in the project’s `previews/` directory.

## MCP setup

Start from the repository directory so `uv` can locate the project.

### Codex

Add this to `.codex/config.toml` or the relevant Codex MCP configuration:

```toml
[mcp_servers.postcli]
command = "/absolute/path/to/PostCLI/.venv/bin/postcli"
args = ["mcp"]
```

### Claude Code

```bash
claude mcp add postcli -- /absolute/path/to/PostCLI/.venv/bin/postcli mcp
```

The server provides the following local-only tools:

| Tool | Purpose |
| --- | --- |
| `inspect_photo_set` | Returns stable asset IDs, metadata, and a labelled contact sheet. |
| `list_templates` | Lists collage templates and their slot counts. |
| `list_canvas_presets` | Lists platform-oriented canvas sizes. |
| `create_carousel` | Persists an editable project from an agent-authored plan and original local paths. |
| `update_carousel` | Applies a validated edit to a project. |
| `render_carousel_preview` | Renders one slide to a local PNG and returns it to the host. |
| `export_carousel` | Exports every slide as PNG or JPEG. |

`inspect_photo_set` returns a labelled contact-sheet image and image metadata. If a host cannot display tool images, it still returns the local sheet path and dimensions/orientation metadata.

## Agent workflow

1. Call `inspect_photo_set(paths)`, `list_templates()`, and `list_canvas_presets()`.
2. Propose three `CarouselPlan` options using the returned asset IDs and a chosen canvas size. Each plan can include a per-slide `caption` recommendation.
3. Choose one plan before calling `create_carousel`. Pass the original paths plus the canvas dimensions as `canvas_width` and `canvas_height`.
4. Use `update_carousel` to set the canvas, reorder slides or photos, swap templates, set a caption, adjust crop/tone values, duplicate slides, or delete slides.
5. Use `render_carousel_preview` and `export_carousel` to review and export the final files.

Slide captions are agent-recommended metadata. They are stored on each slide in the project file and are never rendered over source photos. Legacy headline layers are migrated to caption metadata when a project loads.

All renders, previews, projects, and exports are local. PostCLI has no cloud storage, publishing API, or music API.
