# PostCLI

PostCLI is a local-first terminal app for turning a folder of photos into editable collage slides and social carousels. It never modifies source images. An MCP server lets Codex or Claude Code inspect a labelled thumbnail sheet, recommend an arrangement, create the project, and apply structured edits.

## Install and run

```bash
uv sync --group dev --no-editable
uv run --no-sync postcli scan ~/Pictures/trip --contact-sheet trip-sheet.png
uv run --no-sync postcli templates
uv run --no-sync postcli new trip.postcli.json ~/Pictures/trip --template scrapbook --name "Goa weekend"
uv run --no-sync postcli edit trip.postcli.json
uv run --no-sync postcli export trip.postcli.json exports --format png
```

`postcli new` makes a standalone project. For agent-directed carousels, start the MCP server with `uv run --no-sync postcli mcp`.

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

Then ask the agent to inspect a folder, call `list_templates`, propose three plans, and call `create_carousel` only after you choose one. `inspect_photo_set` returns a labelled contact-sheet image and image metadata; if a host cannot display tool images, it still returns the local sheet path and dimensions/orientation metadata.

## Agent workflow

1. `inspect_photo_set(paths)` returns stable asset IDs, dimensions, and a contact sheet.
2. `list_templates()` exposes slot counts and template intent.
3. The agent proposes three `CarouselPlan` objects using the returned asset IDs.
4. The selected plan is passed to `create_carousel` with the original local paths and destination project file.
5. Use `update_carousel`, `render_carousel_preview`, and `export_carousel` to iterate.

All renders, previews, projects, and exports are local. PostCLI has no cloud storage, publishing API, or music API.
