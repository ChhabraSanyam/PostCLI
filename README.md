# PostCLI

PostCLI is a local-first terminal app for turning a folder of photos into editable collage slides and social carousels. It never modifies source images. An MCP server lets Codex or Claude Code inspect a labelled thumbnail sheet, recommend an arrangement, create the project, and apply structured edits.

## Install and run

```bash
uv sync --group dev --no-editable
uv run --no-sync postcli scan ~/Pictures/trip
uv run --no-sync postcli templates
uv run --no-sync postcli new projects/goa-weekend ~/Pictures/trip --template scrapbook --name "Goa weekend" --canvas instagram-portrait
POSTCLI_IMAGE_PROTOCOL=kitty uv run --no-sync postcli edit projects/goa-weekend
uv run --no-sync postcli export projects/goa-weekend --format png

# Development (rebuild package)
uv sync --group dev --no-editable --reinstall-package postcli
```

`postcli new` creates a new, empty project folder. Its `project.postcli.json` manifest, rendered previews, and exports remain inside that folder, keeping the repository root clean. For agent-directed carousels, start the MCP server with `uv run --no-sync postcli mcp`.

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
| `submit_carousel_options` | Validates and registers exactly three user-facing carousel options. |
| `select_carousel_option` | Records the option the user selected in chat. |
| `confirm_carousel_creation` | Records the user's final approval before creating files. |
| `create_carousel` | Creates the selected, explicitly approved project folder. |
| `render_carousel_previews` | Renders every slide for review before export. |
| `confirm_carousel_export` | Records the user's explicit export approval after preview review. |
| `update_carousel` | Applies a validated edit and returns fresh previews of every slide. |
| `render_carousel_preview` | Renders one slide to a local PNG and returns it to the host. |
| `export_carousel` | Exports every slide as PNG or JPEG. |

`inspect_photo_set` returns a labelled contact-sheet image and image metadata. If a host cannot display tool images, it still returns the local sheet path and dimensions/orientation metadata.

## Agent workflow

1. Call `inspect_photo_set(paths)`, `list_templates()`, and `list_canvas_presets()`.
2. Build and call `submit_carousel_options` with exactly three `CarouselPlan` options using the returned asset IDs and a chosen canvas size.
3. In a normal chat response—not a tool call or hidden working note—show all three options, three post-caption options, and three vibe-matched music recommendations (`title`, `artist`, and `rationale`). Ask which template option the user prefers, then wait.
4. After the user answers, call `select_carousel_option`. In a new chat response, summarize the chosen layout, caption, and music, ask whether to proceed, and wait for a clear yes.
5. Only after that approval, call `confirm_carousel_creation`, then `create_carousel` with a new project-folder name and canvas dimensions. The MCP server rejects direct creation before these gates.
6. Call `render_carousel_previews` to show every slide. In normal chat, ask whether the user wants any edits and wait for their reply. `update_carousel` returns fresh previews after every edit, which restarts this review step.
7. Only when the user explicitly says to export, call `confirm_carousel_export`, then `export_carousel` with the workflow ID. The MCP server rejects direct export. Use `render_carousel_preview` only for an additional single-slide render. Previews and exports write to the project's `previews/` and `exports/` folders; supplied destinations must also be inside that project folder.

All renders, previews, projects, and exports are local. PostCLI has no cloud storage, publishing API, or music API.

---

This Project was built using Codex and GPT 5.6

GPT 5.6 helped brainstorming features, tackle technical hurdles, defining an agent first user flow and refining how an agent should make creative recommendations, while keeping the user in control, and fine tune the app's architecture.
Codex helped turn that idea into a working project in a short amount of time. It supported the development of the python command line application, photo inspection and contact sheet generation, editable collage projects, image rendering, the terminal editor, export workflow and the MCP server that allows agents to use PostCLI