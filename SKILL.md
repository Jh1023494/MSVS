---
name: visualize-markdown-structure
description: Turn Markdown-structured discussion into visible, interactive hierarchy maps. Use when Codex and the user discuss or create Markdown with headings such as # topic, ## subtopic, and ### detail, whether the Markdown comes from conversation, pasted text, attachments, or .md files. Produces an accordion-style visual tree where headings become parent/child nodes and clicking a node reveals the direct Markdown content under that heading, with pan, zoom, wrapped text cards, plus optional outline and Mermaid artifacts.
---

# Visualize Markdown Structure

## Core Workflow

1. Treat the target as Markdown-structured content, not necessarily as a file. If the user has been discussing a Markdown outline in chat, save that current Markdown content into a temporary workspace `.md` input and visualize it.
2. Use Markdown headings as the structure: `#` is the root topic, `##` is a middle topic, `###` and deeper headings are child topics. Preserve heading wording and ordering.
3. Store the direct Markdown body under each heading. When a node is opened, show the content that appears below that heading before the next heading.
4. Generate an interactive HTML visualization by default, and also emit an editable Excalidraw board for export/edit workflows. The HTML visualization must support:
   - Dragging/panning the canvas.
   - Wheel or button zoom in/out.
   - Clicking nodes to open or close that heading's Markdown body.
   - Individual node open/close behavior, not only global expand/collapse.
   - A left-to-right tree layout by default for reading long Markdown structures.
   - Curved SVG connector lines between parent and child nodes that recalculate after node movement, resize, zoom, or pan.
   - Connector stroke widths that sit on discrete min-to-max depth breakpoints, with upper levels thicker and deeper levels thinner.
   - Heading text sizes that scale dramatically by hierarchy depth so higher-level topics read as more prominent.
   - A toolbar auto-layout toggle that runs a live tree layout: sibling nodes repel vertically, children remain grouped to the right of parents, and the whole map keeps a left-to-right tree shape. Turning it off preserves manual node positioning.
   - Per-node movement by dragging the node header without replacing canvas panning.
   - Per-node resizing by dragging the node edge/handle without replacing canvas panning; collapsed node height must remain compact, while resized body height applies only when the Markdown body is open.
   - Multi-selection: Ctrl-click toggles nodes, Shift-click selects sibling ranges, Alt-drag box-selects nodes, right-click selects a subtree, Esc clears selection, and dragging one selected node moves the selected group together.
   - A viewport pan toggle so full-canvas dragging can be enabled or disabled from the toolbar.
   - A theme/tone control for changing the full layout palette. Default to a readable dark slate theme instead of a mostly white layout.
   - A visible Help/Commands panel listing interaction commands.
   - Text selection inside a node without accidentally selecting unrelated nodes or triggering canvas panning.
   - Wrapped text inside node cards so labels do not spill outside the map.
   - A Fit control and first-load fit-to-screen behavior so long heading trees are visible before manual navigation.
   - Separate interactions for node body expansion and child-branch folding: clicking the node opens direct Markdown content, while a small per-node +/- control hides or shows descendants. Hidden descendant branches must be excluded from connector drawing, auto-layout, box selection, and visible status counts.
   - Structured Markdown body rendering for direct heading content: paragraphs, lists, and fenced code blocks should be visually distinct rather than always rendered as one raw text block.
   - Depth-specific card palettes and node sizing so H1/H2/H3/H4 structure reads as root, branch, topic, and detail rather than a flat list.
   - A compact status readout with node count, maximum depth, selected count, open body count, and folded branch count.
   - Export controls: download the current interactive HTML and export the full visible map as a PNG image from inside the generated page. For higher-quality manual editing/export, use the generated `.excalidraw` board.
5. Also generate an outline and an editable `.excalidraw` board unless the user asks for only one output format.
6. Return a clickable local file link to the interactive HTML in the final answer so the user can open and inspect it naturally from the conversation.
7. Use static Mermaid only as a secondary artifact or quick inline preview, not as the main deliverable when the user wants to see or explore the map.

## Script

Use `scripts/md_structure.py` for deterministic Markdown parsing and artifact generation:

```powershell
python C:\Users\jhi\.codex\skills\visualize-markdown-structure\scripts\md_structure.py <input.md> [more.md] --out-dir <folder>
```

Supported formats:

- `interactive`: Default. Standalone HTML map with left-to-right pan, first-load Fit, HTML/PNG export controls, a toolbar pan toggle, zoom, Slate/Graph/Paper tone switching, multi-selectable and draggable connected heading nodes, auto-updating curved SVG connectors with discrete top-heavy depth-scaled thickness, dramatically depth-scaled heading text, depth-specific node palettes, a live auto/manual tree-layout toggle, per-node resize handles that keep collapsed cards compact, click-to-open structured Markdown body content, separate +/- descendant folding that removes hidden branches from visible calculations, wrapped/selectable node text, a compact structure status readout, and a visible commands panel. Use a dark slate base palette (`#18212f`, `#253142`, `#38bdf8`) for better readability unless the user asks for a different tone.
- `outline`: Markdown outline with heading levels, list summaries, links, tables, and code block counts.
- `excalidraw`: Editable Excalidraw scene file with left-to-right document-structure nodes, curved arrows, depth-specific colors, title/meta text, and short direct-content previews. Use this as the stable edit/share/export companion to the interactive HTML.
- `mindmap`: Mermaid mindmap of the heading hierarchy.
- `flowchart`: Mermaid flowchart of heading parent/child structure plus reading order.
- `html`: Alias for `interactive`.

Prefer the script whenever the user wants to see the visualization. For pasted Markdown snippets or Markdown created during conversation, save the snippet to a temporary `.md` file in the workspace, run the script, and return the interactive HTML link.

## Output Guidance

Lead with the interactive HTML path. Include the Excalidraw and outline paths if generated. If the intended test file was missing, say exactly which file was searched for instead of silently using another file.

Do not over-normalize the document. Keep original heading names, ordering, and intent visible, even when proposing a cleaner structure.
