#!/usr/bin/env python3
import argparse
import html
import json
import re
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.+?)\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
TABLE_RE = re.compile(r"^\s*\|.+\|\s*$")


def strip_inline(value):
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"\*([^*]+)\*", r"\1", value)
    value = re.sub(r"__([^_]+)__", r"\1", value)
    value = re.sub(r"_([^_]+)_", r"\1", value)
    return value.strip()


def parse_markdown(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    headings = []
    lists = []
    links = []
    tables = 0
    code_blocks = 0
    in_code = False
    frontmatter = False
    current_heading = None
    visible_lines = []

    for index, line in enumerate(lines, start=1):
        if index == 1 and line.strip() == "---":
            frontmatter = True
            continue
        if frontmatter:
            if line.strip() == "---":
                frontmatter = False
            continue

        visible_lines.append({"line": index, "text": line})

        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            in_code = not in_code
            if in_code:
                code_blocks += 1
            continue
        if in_code:
            continue

        heading = HEADING_RE.match(line)
        if heading:
            current_heading = len(headings)
            headings.append(
                {
                    "line": index,
                    "level": len(heading.group(1)),
                    "title": strip_inline(heading.group(2)),
                    "raw": line,
                    "content_lines": [],
                }
            )
            continue

        item = LIST_RE.match(line)
        if item:
            lists.append(
                {
                    "line": index,
                    "indent": len(item.group(1).replace("\t", "    ")),
                    "text": strip_inline(item.group(3)),
                    "heading_index": current_heading,
                }
            )

        if TABLE_RE.match(line):
            tables += 1

        for match in LINK_RE.finditer(line):
            links.append({"line": index, "text": match.group(1), "target": match.group(2)})

    heading_by_line = {item["line"]: index for index, item in enumerate(headings)}
    current_heading_for_content = None
    root_content_lines = []
    for item in visible_lines:
        if item["line"] in heading_by_line:
            current_heading_for_content = heading_by_line[item["line"]]
            continue
        if current_heading_for_content is None:
            root_content_lines.append(item["text"])
        else:
            headings[current_heading_for_content]["content_lines"].append(item["text"])

    return {
        "path": path,
        "headings": headings,
        "lists": lists,
        "links": links,
        "tables": tables,
        "code_blocks": code_blocks,
        "visible_lines": visible_lines,
        "root_content_lines": root_content_lines,
    }


def heading_prefix(level):
    return "  " * max(level - 1, 0)


def render_outline(data):
    lines = [f"# Structure Outline: {data['path'].name}", ""]
    lines.append("## Headings")
    if data["headings"]:
        for item in data["headings"]:
            lines.append(
                f"{heading_prefix(item['level'])}- H{item['level']} L{item['line']}: {item['title']}"
            )
    else:
        lines.append("- No Markdown headings found.")

    lines.extend(["", "## Lists"])
    if data["lists"]:
        for item in data["lists"][:80]:
            indent = "  " * (item["indent"] // 2)
            lines.append(f"{indent}- L{item['line']}: {item['text']}")
        if len(data["lists"]) > 80:
            lines.append(f"- ... {len(data['lists']) - 80} more list items omitted.")
    else:
        lines.append("- No list items found.")

    lines.extend(["", "## Links"])
    if data["links"]:
        for item in data["links"][:80]:
            lines.append(f"- L{item['line']}: {item['text']} -> {item['target']}")
        if len(data["links"]) > 80:
            lines.append(f"- ... {len(data['links']) - 80} more links omitted.")
    else:
        lines.append("- No links found.")

    lines.extend(
        [
            "",
            "## Counts",
            f"- Headings: {len(data['headings'])}",
            f"- List items: {len(data['lists'])}",
            f"- Links: {len(data['links'])}",
            f"- Table-like rows: {data['tables']}",
            f"- Code blocks: {data['code_blocks']}",
        ]
    )
    return "\n".join(lines) + "\n"


def escape_mermaid(value):
    return value.replace('"', "'").replace("\n", " ").strip()


def render_mermaid(data):
    lines = ["mindmap", f'  root("{escape_mermaid(data["path"].stem)}")']
    if data["headings"]:
        for item in data["headings"]:
            indent = "  " * (item["level"] + 1)
            label = f"H{item['level']} L{item['line']}: {escape_mermaid(item['title'])}"
            lines.append(f'{indent}("{label}")')
    else:
        for item in data["lists"][:30]:
            lines.append(f'    ("L{item["line"]}: {escape_mermaid(item["text"])}")')
    return "\n".join(lines) + "\n"


def render_flowchart(data):
    lines = ["flowchart TD"]
    title = escape_mermaid(data["path"].stem)
    lines.append(f'  root["{title}"]')

    previous_by_level = {0: "root"}
    previous_node = None
    if data["headings"]:
        for index, item in enumerate(data["headings"], start=1):
            node = f"h{index}"
            label = f"H{item['level']} L{item['line']}: {escape_mermaid(item['title'])}"
            lines.append(f'  {node}["{label}"]')

            parent_level = item["level"] - 1
            while parent_level > 0 and parent_level not in previous_by_level:
                parent_level -= 1
            parent = previous_by_level.get(parent_level, "root")
            lines.append(f"  {parent} --> {node}")

            if previous_node and previous_node != parent:
                lines.append(f"  {previous_node} -. next .-> {node}")

            previous_by_level[item["level"]] = node
            for level in list(previous_by_level):
                if level > item["level"]:
                    del previous_by_level[level]
            previous_node = node
    else:
        for index, item in enumerate(data["lists"][:30], start=1):
            node = f"l{index}"
            label = f"L{item['line']}: {escape_mermaid(item['text'])}"
            lines.append(f'  {node}["{label}"]')
            lines.append(f"  root --> {node}")
    return "\n".join(lines) + "\n"


def build_interactive_tree(data):
    root = {
        "label": data["path"].stem,
        "meta": data["path"].name,
        "children": [],
        "content_md": "\n".join(data.get("root_content_lines", [])).strip(),
        "content_html": markdown_fragment_to_html(
            "\n".join(data.get("root_content_lines", [])).strip()
        ),
        "depth": 0,
    }
    stack = [(0, root)]
    heading_nodes = []

    for heading in data["headings"]:
        node = {
            "label": heading["title"],
            "meta": f"H{heading['level']} - line {heading['line']}",
            "children": [],
            "content_md": "\n".join(heading.get("content_lines", [])).strip(),
            "content_html": markdown_fragment_to_html(
                "\n".join(heading.get("content_lines", [])).strip()
            ),
            "depth": heading["level"],
        }
        while stack and stack[-1][0] >= heading["level"]:
            stack.pop()
        parent = stack[-1][1] if stack else root
        parent["children"].append(node)
        stack.append((heading["level"], node))
        heading_nodes.append(node)

    if not heading_nodes:
        for item in data["lists"]:
            root["children"].append(
                {
                    "label": item["text"],
                    "meta": f"line {item['line']}",
                    "children": [],
                    "content_md": "",
                    "content_html": markdown_fragment_to_html(""),
                    "depth": 1,
                }
            )

    return root


def markdown_fragment_to_html(markdown_text):
    if not markdown_text.strip():
        return '<div class="empty">No direct Markdown content under this heading.</div>'

    blocks = []
    in_list = False
    in_code = False
    code_lines = []
    table_lines = []

    def close_list():
        nonlocal in_list
        if in_list:
            blocks.append("</ul>")
            in_list = False

    def close_table():
        nonlocal table_lines
        if not table_lines:
            return
        rows = []
        for table_line in table_lines:
            cells = [cell.strip() for cell in table_line.strip().strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            tag = "th" if not rows else "td"
            rows.append(
                "<tr>"
                + "".join(f"<{tag}>{html.escape(strip_inline(cell))}</{tag}>" for cell in cells)
                + "</tr>"
            )
        if rows:
            blocks.append('<div class="table-wrap"><table>' + "".join(rows) + "</table></div>")
        table_lines = []

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            if in_code:
                blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                close_list()
                close_table()
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            close_list()
            close_table()
            continue

        if TABLE_RE.match(line):
            close_list()
            table_lines.append(line)
            continue

        item = LIST_RE.match(line)
        if item:
            close_table()
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{html.escape(strip_inline(item.group(3)))}</li>")
            continue

        close_list()
        close_table()
        blocks.append(f"<p>{html.escape(stripped)}</p>")

    if in_code:
        blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    close_list()
    close_table()
    return "\n".join(blocks)




def excalidraw_id(prefix, index):
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    value = index + 1000
    encoded = ""
    while value:
        value, remainder = divmod(value, 36)
        encoded = alphabet[remainder] + encoded
    return f"{prefix}_{encoded or '0'}"


def excalidraw_seed(index):
    return 100000 + index * 7919 % 900000


def wrap_plain_text(value, max_chars, max_lines=None):
    value = re.sub(r"\s+", " ", strip_inline(value or "")).strip()
    if not value:
        return []
    chunks = value.split(" ") if " " in value else list(value)
    gap = " " if " " in value else ""
    lines = []
    current = ""
    for chunk in chunks:
        candidate = f"{current}{gap}{chunk}" if current else chunk
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = chunk
            if max_lines and len(lines) >= max_lines:
                break
        else:
            current = candidate
    if current and (not max_lines or len(lines) < max_lines):
        lines.append(current)
    return lines


def content_preview_lines(markdown_text, max_lines=5, max_chars=34):
    lines = []
    in_code = False
    for raw in (markdown_text or "").splitlines():
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            if len(lines) < max_lines:
                lines.append("[code block]")
            continue
        if not stripped:
            continue
        if TABLE_RE.match(stripped):
            text = "[table] " + stripped.replace("|", " ").strip()
        elif in_code:
            text = "` " + stripped
        else:
            item = LIST_RE.match(stripped)
            text = "- " + item.group(3) if item else stripped
        for line in wrap_plain_text(text, max_chars, max_lines - len(lines)):
            lines.append(line)
            if len(lines) >= max_lines:
                return lines
    return lines


def excalidraw_node_style(depth):
    if depth <= 0:
        return {
            "width": 360,
            "fill": "#32415a",
            "stroke": "#f59e0b",
            "font": 34,
            "stroke_width": 3,
        }
    if depth <= 2:
        return {
            "width": 330,
            "fill": "#243b53",
            "stroke": "#38bdf8",
            "font": 27,
            "stroke_width": 2,
        }
    if depth == 3:
        return {
            "width": 300,
            "fill": "#243447",
            "stroke": "#a78bfa",
            "font": 22,
            "stroke_width": 2,
        }
    return {
        "width": 270,
        "fill": "#202b3a",
        "stroke": "#94a3b8",
        "font": 18,
        "stroke_width": 2,
    }


def flatten_excalidraw_tree(root):
    flat = []

    def visit(node, parent_id=None):
        node_id = excalidraw_id("node", len(flat) + 1)
        flat.append({"id": node_id, "node": node, "parent": parent_id})
        for child in node.get("children", []):
            visit(child, node_id)

    visit(root)
    return flat


def assign_excalidraw_layout(root):
    positions = {}
    cursor_y = 0
    column_gap = 460
    leaf_gap = 170

    def visit(node, node_id, depth, flat_by_node):
        nonlocal cursor_y
        children = node.get("children", [])
        if not children:
            center_y = cursor_y
            cursor_y += leaf_gap
        else:
            start_y = cursor_y
            for child in children:
                visit(child, flat_by_node[id(child)], depth + 1, flat_by_node)
            end_y = cursor_y - leaf_gap
            center_y = (start_y + end_y) / 2
        positions[node_id] = {"x": depth * column_gap, "y": center_y}

    flat = flatten_excalidraw_tree(root)
    flat_by_node = {id(item["node"]): item["id"] for item in flat}
    visit(root, flat[0]["id"], 0, flat_by_node)
    min_y = min(item["y"] for item in positions.values()) if positions else 0
    for item in positions.values():
        item["y"] = item["y"] - min_y + 80
        item["x"] = item["x"] + 80
    return flat, positions


def excalidraw_base_element(element_id, element_type, x, y, width, height, index):
    return {
        "id": element_id,
        "type": element_type,
        "x": round(x, 2),
        "y": round(y, 2),
        "width": round(width, 2),
        "height": round(height, 2),
        "angle": 0,
        "strokeColor": "#94a3b8",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "seed": excalidraw_seed(index),
        "version": 1,
        "versionNonce": excalidraw_seed(index + 17),
        "isDeleted": False,
        "boundElements": None,
        "updated": 1,
        "link": None,
        "locked": False,
    }


def render_excalidraw(data):
    root = build_interactive_tree(data)
    flat, positions = assign_excalidraw_layout(root)
    dimensions = {}
    elements = []
    element_index = 1

    for item in flat:
        node = item["node"]
        node_id = item["id"]
        depth = int(node.get("depth", 0))
        style = excalidraw_node_style(depth)
        title_lines = wrap_plain_text(node.get("label", ""), 18 if depth <= 2 else 22, 4)
        content_lines = content_preview_lines(node.get("content_md", ""), max_lines=5, max_chars=36)
        meta = node.get("meta", "")
        text_lines = title_lines[:]
        if meta:
            text_lines.append(meta)
        if content_lines:
            text_lines.append("---")
            text_lines.extend(content_lines)
        line_height = 1.25
        font_size = style["font"]
        meta_extra = 0 if not meta else 4
        content_extra = 18 if content_lines else 0
        text_height = max(42, len(text_lines) * font_size * line_height * 0.72 + meta_extra + content_extra)
        width = style["width"]
        height = max(86, min(260, text_height + 34))
        pos = positions[node_id]
        x = pos["x"]
        y = pos["y"] - height / 2
        dimensions[node_id] = {"x": x, "y": y, "width": width, "height": height}

        group_id = excalidraw_id("group", element_index)
        rect = excalidraw_base_element(excalidraw_id("rect", element_index), "rectangle", x, y, width, height, element_index)
        rect.update(
            {
                "strokeColor": style["stroke"],
                "backgroundColor": style["fill"],
                "strokeWidth": style["stroke_width"],
                "groupIds": [group_id],
            }
        )
        elements.append(rect)
        element_index += 1

        text = "\n".join(text_lines)
        text_el = excalidraw_base_element(
            excalidraw_id("text", element_index),
            "text",
            x + 18,
            y + 16,
            width - 36,
            height - 28,
            element_index,
        )
        text_el.update(
            {
                "strokeColor": "#e5e7eb",
                "backgroundColor": "transparent",
                "fontSize": font_size,
                "fontFamily": 1,
                "text": text,
                "rawText": text,
                "textAlign": "left",
                "verticalAlign": "top",
                "containerId": None,
                "originalText": text,
                "lineHeight": 1.25,
                "baseline": max(20, int((height - 28) * 0.82)),
                "groupIds": [group_id],
            }
        )
        elements.append(text_el)
        element_index += 1

    for item in flat:
        parent_id = item["parent"]
        if not parent_id:
            continue
        child_id = item["id"]
        parent = dimensions[parent_id]
        child = dimensions[child_id]
        start_x = parent["x"] + parent["width"]
        start_y = parent["y"] + parent["height"] / 2
        end_x = child["x"]
        end_y = child["y"] + child["height"] / 2
        dx = max(80, end_x - start_x)
        dy = end_y - start_y
        arrow = excalidraw_base_element(
            excalidraw_id("arrow", element_index), "arrow", start_x, start_y, dx, dy, element_index
        )
        child_depth = int(item["node"].get("depth", 1))
        arrow.update(
            {
                "strokeColor": "#7dd3fc",
                "backgroundColor": "transparent",
                "strokeWidth": max(1, min(8, 9 - child_depth)),
                "roundness": {"type": 2},
                "points": [[0, 0], [dx * 0.5, 0], [dx * 0.5, dy], [dx, dy]],
                "lastCommittedPoint": None,
                "startBinding": None,
                "endBinding": None,
                "startArrowhead": None,
                "endArrowhead": "arrow",
            }
        )
        elements.append(arrow)
        element_index += 1

    return json.dumps(
        {
            "type": "excalidraw",
            "version": 2,
            "source": "visualize-markdown-structure",
            "elements": elements,
            "appState": {
                "gridSize": 20,
                "viewBackgroundColor": "#18212f",
                "currentItemStrokeColor": "#7dd3fc",
                "currentItemBackgroundColor": "transparent",
            },
            "files": {},
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
def render_html(data):
    tree_json = json.dumps(build_interactive_tree(data), ensure_ascii=False)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Interactive Markdown Map - {html.escape(data['path'].name)}</title>
<style>
:root {{
  --bg: #18212f;
  --bg-grid: rgba(148, 163, 184, 0.08);
  --surface: #253142;
  --surface-strong: #2f3d52;
  --toolbar: rgba(31, 41, 55, 0.94);
  --border: #475569;
  --text: #e5e7eb;
  --muted: #aab7c7;
  --content: #d4dde9;
  --accent: #38bdf8;
  --accent-strong: #f59e0b;
  --connector: #7dd3fc;
  --root-bg: #32415a;
  --root-accent: #f59e0b;
  --branch-bg: #243b53;
  --branch-accent: #38bdf8;
  --topic-bg: #243447;
  --topic-accent: #a78bfa;
  --detail-bg: #202b3a;
  --detail-accent: #94a3b8;
  --column-gap: 72px;
  --row-gap: 34px;
}}
body[data-theme="graph"] {{
  --bg: #111827;
  --bg-grid: rgba(45, 212, 191, 0.10);
  --surface: #182232;
  --surface-strong: #202d42;
  --toolbar: rgba(17, 24, 39, 0.96);
  --border: #334155;
  --text: #e2e8f0;
  --muted: #93a4b8;
  --content: #cbd5e1;
  --accent: #2dd4bf;
  --accent-strong: #f97316;
  --connector: #22d3ee;
  --root-bg: #3f2d1f;
  --root-accent: #f97316;
  --branch-bg: #123341;
  --branch-accent: #22d3ee;
  --topic-bg: #1f2f46;
  --topic-accent: #818cf8;
  --detail-bg: #182232;
  --detail-accent: #64748b;
}}
body[data-theme="paper"] {{
  --bg: #e8dfcf;
  --bg-grid: rgba(71, 85, 105, 0.10);
  --surface: #f7f1e5;
  --surface-strong: #efe4d0;
  --toolbar: rgba(250, 244, 232, 0.96);
  --border: #b7a98f;
  --text: #1f2937;
  --muted: #6b5f4e;
  --content: #374151;
  --accent: #2563eb;
  --accent-strong: #b45309;
  --connector: #64748b;
  --root-bg: #efe0bd;
  --root-accent: #b45309;
  --branch-bg: #e7edf7;
  --branch-accent: #2563eb;
  --topic-bg: #f2eadc;
  --topic-accent: #7c3aed;
  --detail-bg: #f7f1e5;
  --detail-accent: #64748b;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  overflow: hidden;
  background-color: var(--bg);
  background-image:
    linear-gradient(var(--bg-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--bg-grid) 1px, transparent 1px);
  background-size: 28px 28px;
  color: var(--text);
  font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif;
}}
.toolbar {{
  position: fixed;
  z-index: 10;
  top: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--toolbar);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);
}}
.toolbar strong {{ margin-right: auto; }}
.status {{
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}}
button {{
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text);
  padding: 6px 10px;
  cursor: pointer;
}}
button.active {{
  background: var(--accent);
  border-color: var(--accent);
  color: #0f172a;
}}
#viewport {{
  position: fixed;
  inset: 0;
  cursor: grab;
  touch-action: none;
  user-select: none;
}}
#viewport.dragging {{ cursor: grabbing; }}
#connections {{
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: 0;
}}
#canvas {{
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
  padding: 96px 80px 80px;
  z-index: 1;
}}
.tree, .tree ul {{
  display: flex;
  align-items: flex-start;
  gap: var(--column-gap);
  list-style: none;
  margin: 0;
  padding: 0;
}}
.tree {{
  flex-direction: row;
}}
.tree ul {{
  flex-direction: column;
  gap: var(--row-gap);
  padding-left: 64px;
  position: relative;
}}
.tree li {{
  display: flex;
  flex-direction: row;
  align-items: center;
  position: relative;
}}
.node {{
  width: 260px;
  min-width: 180px;
  max-width: 560px;
  min-height: 72px;
  border: 1px solid var(--border);
  border-left: 5px solid var(--accent);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.22);
  padding: 10px 12px;
  text-align: left;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: keep-all;
  position: relative;
  user-select: text;
}}
.tree li[data-depth="0"] > .node {{
  width: 340px;
  min-height: 96px;
  background: var(--root-bg);
  border-left-color: var(--root-accent);
  border-left-width: 8px;
}}
.tree li[data-depth="1"] > .node,
.tree li[data-depth="2"] > .node {{
  width: 310px;
  background: var(--branch-bg);
  border-left-color: var(--branch-accent);
  border-left-width: 7px;
}}
.tree li[data-depth="3"] > .node {{
  width: 280px;
  background: var(--topic-bg);
  border-left-color: var(--topic-accent);
  border-left-width: 6px;
}}
.tree li[data-depth="4"] > .node,
.tree li[data-depth="5"] > .node,
.tree li[data-depth="6"] > .node {{
  width: 250px;
  background: var(--detail-bg);
  border-left-color: var(--detail-accent);
}}
.tree li.selected > .node {{
  outline: 3px solid var(--accent-strong);
  box-shadow: 0 0 0 6px rgba(245, 158, 11, 0.18), 0 8px 20px rgba(0, 0, 0, 0.22);
}}
.node {{ cursor: default; }}
.node-header {{
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
  align-items: start;
  cursor: grab;
}}
.node-header.dragging {{ cursor: grabbing; }}
.child-toggle {{
  width: 24px;
  height: 24px;
  padding: 0;
  border-radius: 6px;
  line-height: 1;
  font-weight: 700;
  background: var(--surface-strong);
}}
.child-toggle.empty {{
  visibility: hidden;
}}
.heading-text {{
  min-width: 0;
}}
.label {{
  font-weight: 700;
  line-height: 1.35;
  font-size: var(--label-size, 16px);
}}
.meta {{
  margin-top: 4px;
  color: var(--muted);
  font-size: 12px;
}}
.content {{
  display: none;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  color: var(--content);
  font-size: 13px;
  max-height: 260px;
  overflow: auto;
  user-select: text;
}}
.content-open > .node .content {{
  display: block;
}}
.content pre {{
  margin: 6px 0;
  padding: 8px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.22);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: keep-all;
  font-family: "Cascadia Mono", Consolas, monospace;
  line-height: 1.45;
}}
.content p {{
  margin: 6px 0;
  line-height: 1.5;
}}
.content ul {{
  margin: 6px 0 6px 18px;
  padding: 0;
}}
.content li {{
  display: list-item;
  margin: 4px 0;
  line-height: 1.45;
}}
.table-wrap {{
  max-width: 100%;
  overflow: auto;
  margin: 8px 0;
}}
.content table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}}
.content th,
.content td {{
  border: 1px solid var(--border);
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}}
.content th {{
  background: var(--surface-strong);
  color: var(--text);
}}
.empty {{
  color: var(--muted);
  font-style: italic;
}}
.tree li > .node .label::before {{ content: "◇ "; color: var(--accent); }}
.tree li.content-open > .node .label::before {{ content: "◆ "; color: var(--accent); }}
.tree li.children-hidden > ul {{
  display: none;
}}
.resize-handle {{
  position: absolute;
  right: 2px;
  bottom: 2px;
  width: 14px;
  height: 14px;
  cursor: nwse-resize;
  border-right: 2px solid var(--muted);
  border-bottom: 2px solid var(--muted);
  opacity: 0.8;
}}
#selectionBox {{
  position: fixed;
  display: none;
  border: 1px solid var(--accent);
  background: rgba(56, 189, 248, 0.16);
  pointer-events: none;
  z-index: 8;
}}
#helpPanel {{
  position: fixed;
  z-index: 11;
  top: 58px;
  right: 12px;
  width: 320px;
  display: none;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-strong);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.28);
  padding: 12px;
  color: var(--text);
  font-size: 13px;
}}
#helpPanel.open {{
  display: block;
}}
#helpPanel h2 {{
  margin: 0 0 8px;
  font-size: 15px;
}}
#helpPanel dl {{
  display: grid;
  grid-template-columns: 105px 1fr;
  gap: 6px 10px;
  margin: 0;
}}
#helpPanel dt {{
  font-weight: 700;
  color: var(--text);
}}
#helpPanel dd {{
  margin: 0;
  color: var(--muted);
}}
</style>
</head>
<body>
<div class="toolbar">
  <strong>{html.escape(data['path'].name)}</strong>
  <button id="zoomOut">-</button>
  <button id="zoomIn">+</button>
  <button id="reset">Reset</button>
  <button id="fit">Fit</button>
  <button id="exportHtml">Export HTML</button>
  <button id="exportPng">Export PNG</button>
  <button id="panToggle" class="active">Pan on</button>
  <button id="autoLayout" class="active">Auto layout</button>
  <button id="themeToggle">Tone: Slate</button>
  <button id="helpToggle">Help</button>
  <span id="status" class="status"></span>
</div>
<div id="helpPanel">
  <h2>Commands</h2>
  <dl>
    <dt>Click node</dt><dd>Open or close direct Markdown body</dd>
    <dt>Small +/-</dt><dd>Show or hide child branches</dd>
    <dt>Ctrl+Click</dt><dd>Select or unselect a node</dd>
    <dt>Shift+Click</dt><dd>Select sibling range</dd>
    <dt>Alt+Drag</dt><dd>Box-select nodes</dd>
    <dt>Right click</dt><dd>Select subtree</dd>
    <dt>Drag header</dt><dd>Move selected nodes together</dd>
    <dt>Resize corner</dt><dd>Change card width and open body height</dd>
    <dt>Fit</dt><dd>Fit the full visible tree to screen</dd>
    <dt>Export HTML</dt><dd>Download this interactive map</dd>
    <dt>Export PNG</dt><dd>Download a full-map image</dd>
    <dt>Esc</dt><dd>Clear selection</dd>
  </dl>
</div>
<div id="selectionBox"></div>
<div id="viewport"><svg id="connections"></svg><div id="canvas"></div></div>
<script>
const data = {tree_json};
const viewport = document.getElementById("viewport");
const connections = document.getElementById("connections");
const canvas = document.getElementById("canvas");
const selectionBox = document.getElementById("selectionBox");
const status = document.getElementById("status");
let scale = 1;
let offsetX = 0;
let offsetY = 0;
let dragging = false;
let startX = 0;
let startY = 0;
let suppressNextClick = false;
let autoLayout = true;
let layoutFrame = null;
let selectedItems = new Set();
let lastSelectedItem = null;
let boxSelecting = false;
let panEnabled = true;
const themes = [
  {{id: "slate", label: "Slate"}},
  {{id: "graph", label: "Graph"}},
  {{id: "paper", label: "Paper"}}
];
let themeIndex = 0;

function esc(value) {{
  return String(value).replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c]));
}}

function getMaxDepth(node) {{
  return Math.max(node.depth || 0, ...(node.children || []).map(getMaxDepth));
}}

const maxDepth = Math.max(1, getMaxDepth(data));
const totalNodeCount = countNodes(data);

function countNodes(node) {{
  return 1 + (node.children || []).reduce((sum, child) => sum + countNodes(child), 0);
}}

function labelSize(depth) {{
  const normalized = Math.max(0, Math.min(1, (depth || 0) / maxDepth));
  return Math.max(13, Math.min(34, 34 - normalized * 18));
}}

function connectionWidth(depth) {{
  const minWidth = 1.2;
  const maxWidth = 10;
  const levels = Math.max(1, maxDepth);
  const index = Math.max(0, Math.min(levels, depth || 0));
  const step = levels === 0 ? 0 : (maxWidth - minWidth) / levels;
  return Math.max(minWidth, Math.min(maxWidth, maxWidth - step * index));
}}

function themeValue(name) {{
  return getComputedStyle(document.body).getPropertyValue(name).trim();
}}

function renderNode(node) {{
  const hasChildren = node.children && node.children.length;
  const depth = node.depth || 0;
  const body = node.content_html || `<div class="empty">No direct Markdown content under this heading.</div>`;
  return `<li class="${{hasChildren ? "collapsible" : "leaf"}}" data-depth="${{depth}}">
    <div class="node ${{hasChildren ? "collapsible" : ""}}">
      <div class="node-header">
        <button class="child-toggle ${{hasChildren ? "" : "empty"}}" title="Show or hide child branches" aria-label="Show or hide child branches">${{hasChildren ? "-" : ""}}</button>
        <div class="heading-text">
          <div class="label" style="--label-size: ${{labelSize(depth)}}px">${{esc(node.label)}}</div>
          <div class="meta">${{esc(node.meta || "")}}</div>
        </div>
      </div>
      <div class="content">${{body}}</div>
      <div class="resize-handle" title="Resize node"></div>
    </div>
    ${{hasChildren ? `<ul>${{node.children.map(renderNode).join("")}}</ul>` : ""}}
  </li>`;
}}

function applyTransform() {{
  canvas.style.transform = `translate(${{offsetX}}px, ${{offsetY}}px) scale(${{scale}})`;
  requestAnimationFrame(drawConnections);
}}

canvas.innerHTML = `<ul class="tree">${{renderNode(data)}}</ul>`;
applyTransform();

function isVisibleItem(item) {{
  let current = item;
  while (current && current.matches && current.matches("li")) {{
    const parentList = current.parentElement;
    const parentItem = parentList ? parentList.closest("li") : null;
    if (parentItem && parentItem.classList.contains("children-hidden")) return false;
    current = parentItem;
  }}
  return true;
}}

function visibleItems() {{
  return Array.from(document.querySelectorAll(".tree li")).filter(isVisibleItem);
}}

function drawConnections() {{
  const viewportRect = viewport.getBoundingClientRect();
  const paths = [];
  visibleItems().forEach(parentLi => {{
    const parentNode = parentLi.querySelector(":scope > .node");
    const childList = parentLi.querySelector(":scope > ul");
    if (!parentNode || !childList) return;
    if (parentLi.classList.contains("children-hidden")) return;

    Array.from(childList.querySelectorAll(":scope > li")).filter(isVisibleItem).forEach(childLi => {{
      const childNode = childLi.querySelector(":scope > .node");
      if (!childNode) return;

      const parentRect = parentNode.getBoundingClientRect();
      const childRect = childNode.getBoundingClientRect();
      const x1 = parentRect.right - viewportRect.left;
      const y1 = parentRect.top + parentRect.height / 2 - viewportRect.top;
      const x2 = childRect.left - viewportRect.left;
      const y2 = childRect.top + childRect.height / 2 - viewportRect.top;
      const curve = Math.max(70, Math.abs(x2 - x1) * 0.5);
      const childDepth = Number(childLi.dataset.depth || 1);
      const highlighted = parentLi.classList.contains("selected") || childLi.classList.contains("selected");
      const strokeWidth = connectionWidth(childDepth) + (highlighted ? 2 : 0);
      const stroke = highlighted ? themeValue("--accent-strong") : themeValue("--connector");
      const opacity = highlighted ? 1 : 0.78;
      const d = `M ${{x1}} ${{y1}} C ${{x1 + curve}} ${{y1}}, ${{x2 - curve}} ${{y2}}, ${{x2}} ${{y2}}`;
      paths.push(`<path d="${{d}}" fill="none" stroke="${{stroke}}" stroke-width="${{strokeWidth}}" stroke-linecap="round" opacity="${{opacity}}"/>`);
    }});
  }});
  connections.innerHTML = paths.join("");
}}

function updateStatus() {{
  const items = visibleItems();
  const openCount = items.filter(item => item.classList.contains("content-open")).length;
  const hiddenCount = items.filter(item => item.classList.contains("children-hidden")).length;
  const selectedCount = Array.from(selectedItems).filter(isVisibleItem).length;
  status.textContent = `${{totalNodeCount}} nodes · depth ${{maxDepth}} · ${{selectedCount}} selected · ${{openCount}} open · ${{hiddenCount}} folded`;
}}

function setNodeOpenState(item, open) {{
  item.classList.toggle("content-open", open);
  updateStatus();
  requestAnimationFrame(drawConnections);
}}

function setChildrenHidden(item, hidden) {{
  if (!item.querySelector(":scope > ul")) return;
  item.classList.toggle("children-hidden", hidden);
  const button = item.querySelector(":scope > .node .child-toggle");
  if (button) button.textContent = hidden ? "+" : "-";
  if (hidden) {{
    item.querySelectorAll("li").forEach(child => {{
      selectedItems.delete(child);
      child.classList.remove("selected");
    }});
  }}
  updateStatus();
  requestAnimationFrame(() => {{
    drawConnections();
    if (autoLayout) requestDocumentLayout();
  }});
}}

function toggleChildren(item) {{
  setChildrenHidden(item, !item.classList.contains("children-hidden"));
}}

function fitToView() {{
  scale = 1;
  offsetX = 0;
  offsetY = 0;
  canvas.style.transform = `translate(0px, 0px) scale(1)`;
  requestAnimationFrame(() => {{
    const tree = canvas.querySelector(".tree");
    if (!tree) return;
    const rect = tree.getBoundingClientRect();
    const pad = 72;
    const nextScale = Math.max(0.05, Math.min(1.35, Math.min((window.innerWidth - pad * 2) / rect.width, (window.innerHeight - pad * 2) / rect.height)));
    scale = Number.isFinite(nextScale) ? nextScale : 1;
    offsetX = pad - rect.left * scale;
    offsetY = pad - rect.top * scale;
    applyTransform();
  }});
}}

function getShift(item) {{
  return {{
    x: Number(item.dataset.x || 0),
    y: Number(item.dataset.y || 0)
  }};
}}

function setShift(item, x, y) {{
  item.dataset.x = String(x);
  item.dataset.y = String(y);
  item.style.transform = `translate(${{x}}px, ${{y}}px)`;
}}

function setSelected(item, selected) {{
  if (selected) {{
    selectedItems.add(item);
    item.classList.add("selected");
    lastSelectedItem = item;
  }} else {{
    selectedItems.delete(item);
    item.classList.remove("selected");
  }}
  updateStatus();
  requestAnimationFrame(drawConnections);
}}

function clearSelection() {{
  selectedItems.forEach(item => item.classList.remove("selected"));
  selectedItems.clear();
  lastSelectedItem = null;
  updateStatus();
  requestAnimationFrame(drawConnections);
}}

function toggleSelected(item) {{
  setSelected(item, !selectedItems.has(item));
}}

function selectSiblingRange(item) {{
  if (!lastSelectedItem) {{
    setSelected(item, true);
    return;
  }}
  const siblings = Array.from(item.parentElement.children).filter(child => child.matches("li") && isVisibleItem(child));
  if (!siblings.includes(lastSelectedItem)) {{
    setSelected(item, true);
    return;
  }}
  const start = siblings.indexOf(lastSelectedItem);
  const end = siblings.indexOf(item);
  siblings.slice(Math.min(start, end), Math.max(start, end) + 1).forEach(sibling => setSelected(sibling, true));
}}

function selectSubtree(item) {{
  setSelected(item, true);
  item.querySelectorAll("li").forEach(child => {{
    if (isVisibleItem(child)) setSelected(child, true);
  }});
}}

function resetNodeOffsets() {{
  document.querySelectorAll(".tree li").forEach(item => setShift(item, 0, 0));
  requestAnimationFrame(drawConnections);
}}

function visibleChildren(item) {{
  if (item.classList.contains("children-hidden")) return [];
  return Array.from(item.querySelectorAll(":scope > ul > li")).filter(isVisibleItem);
}}

function requestDocumentLayout() {{
  document.querySelectorAll(".tree li").forEach(item => setShift(item, 0, 0));
  requestAnimationFrame(() => {{
    const root = document.querySelector(".tree > li");
    const tree = document.querySelector(".tree");
    if (!root || !tree) return;
    const treeRect = tree.getBoundingClientRect();
    let cursorY = 0;
    const columnWidth = 390;
    const leafGap = 118;

    function assign(item, depth) {{
      const children = visibleChildren(item);
      let centerY;
      if (!children.length) {{
        centerY = cursorY;
        cursorY += leafGap;
      }} else {{
        const startY = cursorY;
        children.forEach(child => assign(child, depth + 1));
        const endY = cursorY - leafGap;
        centerY = (startY + endY) / 2;
      }}
      const node = item.querySelector(":scope > .node");
      const rect = node.getBoundingClientRect();
      const currentX = rect.left - treeRect.left;
      const currentY = rect.top - treeRect.top;
      const targetX = depth * columnWidth;
      const targetY = centerY;
      setShift(item, targetX - currentX, targetY - currentY);
    }}

    assign(root, 0);
    drawConnections();
  }});
}}

function autoLayoutTick() {{
  if (!autoLayout) return;
  const items = visibleItems();
  const nodes = items.map(item => {{
    const node = item.querySelector(":scope > .node");
    const rect = node.getBoundingClientRect();
    return {{
      item,
      node,
      rect,
      centerX: rect.left + rect.width / 2,
      centerY: rect.top + rect.height / 2,
      width: rect.width,
      height: rect.height,
      depth: Number(item.dataset.depth || 0)
    }};
  }});

  const forces = new Map(items.map(item => [item, {{x: 0, y: 0}}]));

  for (let i = 0; i < nodes.length; i += 1) {{
    for (let j = i + 1; j < nodes.length; j += 1) {{
      const a = nodes[i];
      const b = nodes[j];
      const minX = (a.width + b.width) / 2 + 42;
      const minY = (a.height + b.height) / 2 + 32;
      const dx = b.centerX - a.centerX || 1;
      const dy = b.centerY - a.centerY || 1;
      const overlapX = minX - Math.abs(dx);
      const overlapY = minY - Math.abs(dy);
      if (overlapX > 0 && overlapY > 0) {{
        const pushX = Math.sign(dx) * Math.min(10, overlapX * 0.035);
        const pushY = Math.sign(dy) * Math.min(8, overlapY * 0.025);
        forces.get(a.item).x -= pushX;
        forces.get(b.item).x += pushX;
        forces.get(a.item).y -= pushY;
        forces.get(b.item).y += pushY;
      }}
    }}
  }}

  visibleItems().forEach(parentItem => {{
    const parentNode = parentItem.querySelector(":scope > .node");
    const children = visibleChildren(parentItem);
    if (!parentNode || !children.length) return;
    const parentRect = parentNode.getBoundingClientRect();
    const parentCenterY = parentRect.top + parentRect.height / 2;
    const targetX = parentRect.right + 170;
    const spacing = 150;
    children.forEach((child, index) => {{
      const childNode = child.querySelector(":scope > .node");
      const childRect = childNode.getBoundingClientRect();
      const childCenterY = childRect.top + childRect.height / 2;
      const targetY = parentCenterY + (index - (children.length - 1) / 2) * spacing;
      forces.get(child).x += Math.max(-14, Math.min(14, (targetX - childRect.left) * 0.035));
      forces.get(child).y += Math.max(-12, Math.min(12, (targetY - childCenterY) * 0.035));
    }});
  }});

  nodes.forEach(entry => {{
    const force = forces.get(entry.item);
    const shift = getShift(entry.item);
    const damping = 0.88;
    setShift(entry.item, shift.x * damping + force.x / scale, shift.y * damping + force.y / scale);
  }});

  drawConnections();
  layoutFrame = requestAnimationFrame(autoLayoutTick);
}}

function setAutoLayout(enabled) {{
  autoLayout = enabled;
  const button = document.getElementById("autoLayout");
  button.classList.toggle("active", autoLayout);
  button.textContent = autoLayout ? "Auto layout" : "Manual layout";
  if (autoLayout) {{
    if (layoutFrame) cancelAnimationFrame(layoutFrame);
    requestDocumentLayout();
    layoutFrame = requestAnimationFrame(autoLayoutTick);
  }} else if (layoutFrame) {{
    cancelAnimationFrame(layoutFrame);
    layoutFrame = null;
  }}
}}

function setPanEnabled(enabled) {{
  panEnabled = enabled;
  const button = document.getElementById("panToggle");
  button.classList.toggle("active", panEnabled);
  button.textContent = panEnabled ? "Pan on" : "Pan off";
}}

function cycleTheme() {{
  themeIndex = (themeIndex + 1) % themes.length;
  const theme = themes[themeIndex];
  document.body.dataset.theme = theme.id;
  document.getElementById("themeToggle").textContent = `Tone: ${{theme.label}}`;
  requestAnimationFrame(drawConnections);
}}

function resetView() {{
  scale = 1;
  offsetX = 0;
  offsetY = 0;
  clearSelection();
  document.querySelectorAll(".tree li").forEach(item => item.classList.remove("content-open", "children-hidden"));
  document.querySelectorAll(".child-toggle:not(.empty)").forEach(button => button.textContent = "-");
  resetNodeOffsets();
  requestDocumentLayout();
  applyTransform();
  updateStatus();
  setTimeout(fitToView, 80);
}}

function downloadBlob(blob, filename) {{
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}}

function extensionForMime(mime) {{
  if (mime === "image/png") return ".png";
  if (mime === "text/html") return ".html";
  return "";
}}

async function saveBlob(blob, filename, mime, description) {{
  if (window.showSaveFilePicker) {{
    try {{
      const handle = await window.showSaveFilePicker({{
        suggestedName: filename,
        types: [{{description: description || "Export file", accept: {{[mime]: [extensionForMime(mime)]}}}}]
      }});
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return "picker";
    }} catch (error) {{
      if (error && error.name === "AbortError") return "cancelled";
      console.warn("File picker save failed; falling back to browser download.", error);
    }}
  }}
  downloadBlob(blob, filename);
  return "download";
}}

function openBlobPreview(blob, filename) {{
  const url = URL.createObjectURL(blob);
  const opened = window.open(url, "_blank", "noopener");
  if (!opened) {{
    alert(`Download was requested as ${{filename}}, but the browser may have blocked it. Check browser downloads or allow popups for this file.`);
  }}
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}}

function safeFilename(value, fallback) {{
  const cleaned = String(value || fallback || "markdown-map")
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, " ")
    .trim();
  return cleaned || fallback || "markdown-map";
}}

async function exportHtml() {{
  const htmlText = "<!doctype html>\\n" + document.documentElement.outerHTML;
  const filename = `${{safeFilename(data.label)}}.interactive.html`;
  await saveBlob(new Blob([htmlText], {{type: "text/html;charset=utf-8"}}), filename, "text/html", "Interactive HTML");
}}

function loadSvgImage(svgText) {{
  return new Promise((resolve, reject) => {{
    const blobUrl = URL.createObjectURL(new Blob([svgText], {{type: "image/svg+xml;charset=utf-8"}}));
    const image = new Image();
    image.decoding = "async";
    image.onload = () => {{
      URL.revokeObjectURL(blobUrl);
      resolve(image);
    }};
    image.onerror = () => {{
      URL.revokeObjectURL(blobUrl);
      const fallback = new Image();
      fallback.decoding = "async";
      fallback.onload = () => resolve(fallback);
      fallback.onerror = () => reject(new Error("PNG export image renderer could not load the generated SVG."));
      fallback.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgText);
    }};
    image.src = blobUrl;
  }});
}}

function canvasToBlob(canvasElement) {{
  return new Promise((resolve, reject) => {{
    canvasElement.toBlob(blob => {{
      if (blob) resolve(blob);
      else reject(new Error("PNG export could not create an image blob."));
    }}, "image/png");
  }});
}}

function svgEsc(value) {{
  return String(value || "").replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
}}

function wrapForSvg(text, maxWidth, fontSize) {{
  const normalized = String(text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return [];
  const units = normalized.includes(" ") ? normalized.split(" ") : Array.from(normalized);
  const lines = [];
  let current = "";
  const unitGap = normalized.includes(" ") ? " " : "";
  const approx = Math.max(6, fontSize * 0.56);
  units.forEach(unit => {{
    const next = current ? current + unitGap + unit : unit;
    if (next.length * approx > maxWidth && current) {{
      lines.push(current);
      current = unit;
    }} else {{
      current = next;
    }}
  }});
  if (current) lines.push(current);
  return lines;
}}

function collectContentLines(node, maxWidth) {{
  const lines = [];
  const content = node.querySelector(".content");
  if (!content || getComputedStyle(content).display === "none") return lines;
  content.querySelectorAll("p, li, pre, th, td, .empty").forEach(part => {{
    const prefix = part.tagName === "LI" ? "- " : "";
    const text = prefix + part.textContent.trim();
    wrapForSvg(text, maxWidth, 12).slice(0, 8).forEach(line => lines.push(line));
  }});
  return lines.slice(0, 18);
}}

async function exportPng() {{
  const button = document.getElementById("exportPng");
  const previousLabel = button.textContent;
  button.textContent = "Exporting...";
  button.disabled = true;
  try {{
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    drawConnections();
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const items = visibleItems();
    const nodes = items.map(item => item.querySelector(":scope > .node")).filter(Boolean);
    if (!nodes.length) throw new Error("No visible nodes to export.");

    const effectiveScale = Number.isFinite(scale) && scale > 0 ? scale : 1;
    const viewportRect = viewport.getBoundingClientRect();
    const nodeRects = nodes.map(node => node.getBoundingClientRect());
    const allScreenRects = nodeRects;
    const pad = 96;
    const minScreenX = Math.floor(Math.min(...allScreenRects.map(rect => rect.left)) - pad * effectiveScale);
    const minScreenY = Math.floor(Math.min(...allScreenRects.map(rect => rect.top)) - pad * effectiveScale);
    const maxScreenX = Math.ceil(Math.max(...allScreenRects.map(rect => rect.right)) + pad * effectiveScale);
    const maxScreenY = Math.ceil(Math.max(...allScreenRects.map(rect => rect.bottom)) + pad * effectiveScale);
    const width = Math.max(320, Math.ceil((maxScreenX - minScreenX) / effectiveScale));
    const height = Math.max(240, Math.ceil((maxScreenY - minScreenY) / effectiveScale));
    const toExportX = value => Math.round(((value - minScreenX) / effectiveScale) * 100) / 100;
    const toExportY = value => Math.round(((value - minScreenY) / effectiveScale) * 100) / 100;
    const toExportSize = value => Math.round((value / effectiveScale) * 100) / 100;

    const bg = themeValue("--bg");
    const grid = themeValue("--bg-grid") || "rgba(148, 163, 184, 0.08)";
    const textColor = themeValue("--text") || "#e5e7eb";
    const mutedColor = themeValue("--muted") || "#aab7c7";
    const contentColor = themeValue("--content") || "#d4dde9";
    const selectedColor = themeValue("--accent-strong") || "#f59e0b";
    const borderColor = themeValue("--border") || "#475569";
    const connectorColor = themeValue("--connector") || "#7dd3fc";

    const parts = [];
    parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${{width}}" height="${{height}}" viewBox="0 0 ${{width}} ${{height}}">`);
    parts.push(`<defs><pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M 28 0 L 0 0 0 28" fill="none" stroke="${{svgEsc(grid)}}" stroke-width="1"/></pattern><filter id="shadow" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#000000" flood-opacity="0.22"/></filter></defs>`);
    parts.push(`<rect width="100%" height="100%" fill="${{svgEsc(bg)}}"/><rect width="100%" height="100%" fill="url(#grid)"/>`);

    items.forEach(parentLi => {{
      if (parentLi.classList.contains("children-hidden")) return;
      const parentNode = parentLi.querySelector(":scope > .node");
      const childList = parentLi.querySelector(":scope > ul");
      if (!parentNode || !childList) return;
      Array.from(childList.querySelectorAll(":scope > li")).filter(isVisibleItem).forEach(childLi => {{
        const childNode = childLi.querySelector(":scope > .node");
        if (!childNode) return;
        const parentRect = parentNode.getBoundingClientRect();
        const childRect = childNode.getBoundingClientRect();
        const x1 = toExportX(parentRect.right);
        const y1 = toExportY(parentRect.top + parentRect.height / 2);
        const x2 = toExportX(childRect.left);
        const y2 = toExportY(childRect.top + childRect.height / 2);
        const curve = Math.max(70, Math.abs(x2 - x1) * 0.5);
        const childDepth = Number(childLi.dataset.depth || 1);
        const highlighted = parentLi.classList.contains("selected") || childLi.classList.contains("selected");
        const strokeWidth = connectionWidth(childDepth) + (highlighted ? 2 : 0);
        const stroke = highlighted ? selectedColor : connectorColor;
        const opacity = highlighted ? 1 : 0.78;
        const d = `M ${{x1}} ${{y1}} C ${{x1 + curve}} ${{y1}}, ${{x2 - curve}} ${{y2}}, ${{x2}} ${{y2}}`;
        parts.push(`<path d="${{svgEsc(d)}}" fill="none" stroke="${{svgEsc(stroke)}}" stroke-width="${{strokeWidth}}" stroke-linecap="round" opacity="${{opacity}}"/>`);
      }});
    }});

    nodes.forEach(node => {{
      const rect = node.getBoundingClientRect();
      const item = node.closest("li");
      const computed = getComputedStyle(node);
      const x = toExportX(rect.left);
      const y = toExportY(rect.top);
      const w = toExportSize(rect.width);
      const h = toExportSize(rect.height);
      const fill = computed.backgroundColor || themeValue("--surface");
      const accent = computed.borderLeftColor || themeValue("--accent");
      const border = item && item.classList.contains("selected") ? selectedColor : borderColor;
      const depth = Number(item ? item.dataset.depth || 0 : 0);
      const labelFont = labelSize(depth);
      parts.push(`<g filter="url(#shadow)"><rect x="${{x}}" y="${{y}}" width="${{w}}" height="${{h}}" rx="8" fill="${{svgEsc(fill)}}" stroke="${{svgEsc(border)}}" stroke-width="${{item && item.classList.contains("selected") ? 3 : 1}}"/><rect x="${{x}}" y="${{y}}" width="${{depth === 0 ? 8 : depth <= 2 ? 7 : 5}}" height="${{h}}" rx="4" fill="${{svgEsc(accent)}}"/></g>`);
      const label = node.querySelector(".label") ? node.querySelector(".label").textContent.trim() : "";
      const meta = node.querySelector(".meta") ? node.querySelector(".meta").textContent.trim() : "";
      let ty = y + 24;
      wrapForSvg(label, w - 46, labelFont).slice(0, 4).forEach(line => {{
        parts.push(`<text x="${{x + 34}}" y="${{ty}}" fill="${{svgEsc(textColor)}}" font-family="Segoe UI, Malgun Gothic, Arial, sans-serif" font-size="${{labelFont}}" font-weight="700">${{svgEsc(line)}}</text>`);
        ty += labelFont * 1.35;
      }});
      if (meta) {{
        parts.push(`<text x="${{x + 34}}" y="${{ty + 4}}" fill="${{svgEsc(mutedColor)}}" font-family="Segoe UI, Malgun Gothic, Arial, sans-serif" font-size="12">${{svgEsc(meta)}}</text>`);
        ty += 22;
      }}
      const contentLines = collectContentLines(node, w - 28);
      if (contentLines.length) {{
        parts.push(`<line x1="${{x + 12}}" y1="${{ty}}" x2="${{x + w - 12}}" y2="${{ty}}" stroke="${{svgEsc(borderColor)}}" stroke-width="1" opacity="0.85"/>`);
        ty += 18;
        contentLines.forEach(line => {{
          if (ty < y + h - 10) {{
            parts.push(`<text x="${{x + 14}}" y="${{ty}}" fill="${{svgEsc(contentColor)}}" font-family="Segoe UI, Malgun Gothic, Arial, sans-serif" font-size="12">${{svgEsc(line)}}</text>`);
            ty += 18;
          }}
        }});
      }}
    }});

    parts.push("</svg>");
    const svg = parts.join("");
    const image = await loadSvgImage(svg);
    const canvasOut = document.createElement("canvas");
    const pixelRatio = Math.min(2, window.devicePixelRatio || 1);
    canvasOut.width = Math.round(width * pixelRatio);
    canvasOut.height = Math.round(height * pixelRatio);
    const context = canvasOut.getContext("2d");
    context.scale(pixelRatio, pixelRatio);
    context.drawImage(image, 0, 0, width, height);
    const blob = await canvasToBlob(canvasOut);
    const filename = `${{safeFilename(data.label)}}.full-map.png`;
    const savedBy = await saveBlob(blob, filename, "image/png", "PNG image");
    if (savedBy === "download") {{
      setTimeout(() => openBlobPreview(blob, filename), 300);
    }}
  }} catch (error) {{
    console.error(error);
    alert(`PNG export failed: ${{error && error.message ? error.message : error}}`);
  }} finally {{
    button.textContent = previousLabel;
    button.disabled = false;
  }}
}}
canvas.addEventListener("click", event => {{
  if (suppressNextClick) {{
    suppressNextClick = false;
    return;
  }}
  const childToggle = event.target.closest(".child-toggle");
  if (childToggle && !childToggle.classList.contains("empty")) {{
    event.preventDefault();
    event.stopPropagation();
    toggleChildren(childToggle.closest("li"));
    return;
  }}
  if (!event.target.closest(".node-header")) return;
  if (window.getSelection && String(window.getSelection()).length > 0) return;
  const node = event.target.closest(".node-header").closest(".node");
  const item = node.parentElement;
  if (event.ctrlKey || event.metaKey) {{
    toggleSelected(item);
    return;
  }}
  if (event.shiftKey) {{
    selectSiblingRange(item);
    return;
  }}
  setNodeOpenState(item, !item.classList.contains("content-open"));
}});

canvas.addEventListener("pointerdown", event => {{
  const header = event.target.closest(".node-header");
  if (event.target.closest(".child-toggle")) return;
  if (!header || window.getSelection && String(window.getSelection()).length > 0) return;
  event.preventDefault();
  event.stopPropagation();
  const item = header.closest("li");
  const startTransformX = Number(item.dataset.x || 0);
  const startTransformY = Number(item.dataset.y || 0);
  const movingItems = selectedItems.has(item) ? Array.from(selectedItems) : [item];
  const movingStarts = new Map(movingItems.map(entry => [entry, getShift(entry)]));
  const startClientX = event.clientX;
  const startClientY = event.clientY;
  let moved = false;
  header.classList.add("dragging");
  header.setPointerCapture(event.pointerId);

  function move(moveEvent) {{
    const dx = (moveEvent.clientX - startClientX) / scale;
    const dy = (moveEvent.clientY - startClientY) / scale;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) moved = true;
    movingItems.forEach(entry => {{
      const start = movingStarts.get(entry);
      setShift(entry, start.x + dx, start.y + dy);
    }});
    if (autoLayout) setAutoLayout(false);
    drawConnections();
  }}

  function stop(upEvent) {{
    header.classList.remove("dragging");
    header.releasePointerCapture(upEvent.pointerId);
    header.removeEventListener("pointermove", move);
    header.removeEventListener("pointerup", stop);
    if (moved) suppressNextClick = true;
    requestAnimationFrame(drawConnections);
  }}

  header.addEventListener("pointermove", move);
  header.addEventListener("pointerup", stop);
}});

canvas.addEventListener("contextmenu", event => {{
  const node = event.target.closest(".node");
  if (!node) return;
  event.preventDefault();
  selectSubtree(node.parentElement);
}});

document.addEventListener("keydown", event => {{
  if (event.key === "Escape") clearSelection();
}});

viewport.addEventListener("pointerdown", event => {{
  if (event.altKey) {{
    event.preventDefault();
    boxSelecting = true;
    const startClientX = event.clientX;
    const startClientY = event.clientY;
    selectionBox.style.display = "block";
    selectionBox.style.left = `${{startClientX}}px`;
    selectionBox.style.top = `${{startClientY}}px`;
    selectionBox.style.width = "0px";
    selectionBox.style.height = "0px";
    viewport.setPointerCapture(event.pointerId);

    function updateBox(moveEvent) {{
      const left = Math.min(startClientX, moveEvent.clientX);
      const top = Math.min(startClientY, moveEvent.clientY);
      const width = Math.abs(moveEvent.clientX - startClientX);
      const height = Math.abs(moveEvent.clientY - startClientY);
      selectionBox.style.left = `${{left}}px`;
      selectionBox.style.top = `${{top}}px`;
      selectionBox.style.width = `${{width}}px`;
      selectionBox.style.height = `${{height}}px`;
    }}

    function finishBox(upEvent) {{
      const box = selectionBox.getBoundingClientRect();
      if (!upEvent.ctrlKey && !upEvent.metaKey) clearSelection();
      visibleItems().forEach(item => {{
        const rect = item.querySelector(":scope > .node").getBoundingClientRect();
        const intersects = rect.left <= box.right && rect.right >= box.left && rect.top <= box.bottom && rect.bottom >= box.top;
        if (intersects) setSelected(item, true);
      }});
      selectionBox.style.display = "none";
      boxSelecting = false;
      viewport.releasePointerCapture(upEvent.pointerId);
      viewport.removeEventListener("pointermove", updateBox);
      viewport.removeEventListener("pointerup", finishBox);
    }}

    viewport.addEventListener("pointermove", updateBox);
    viewport.addEventListener("pointerup", finishBox);
    return;
  }}
  if (!panEnabled) return;
  if (event.target.closest(".node")) return;
  dragging = true;
  viewport.classList.add("dragging");
  startX = event.clientX - offsetX;
  startY = event.clientY - offsetY;
  viewport.setPointerCapture(event.pointerId);
}});
viewport.addEventListener("pointermove", event => {{
  if (!dragging) return;
  offsetX = event.clientX - startX;
  offsetY = event.clientY - startY;
  applyTransform();
}});
viewport.addEventListener("pointerup", event => {{
  if (!dragging) return;
  dragging = false;
  viewport.classList.remove("dragging");
  viewport.releasePointerCapture(event.pointerId);
}});
viewport.addEventListener("wheel", event => {{
  event.preventDefault();
  const previous = scale;
  scale = Math.min(5, Math.max(0.05, scale + (event.deltaY < 0 ? 0.08 : -0.08)));
  const rect = viewport.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  offsetX = x - ((x - offsetX) / previous) * scale;
  offsetY = y - ((y - offsetY) / previous) * scale;
  applyTransform();
}}, {{ passive: false }});

document.getElementById("zoomIn").onclick = () => {{ scale = Math.min(5, scale + 0.15); applyTransform(); }};
document.getElementById("zoomOut").onclick = () => {{ scale = Math.max(0.05, scale - 0.15); applyTransform(); }};
document.getElementById("reset").onclick = resetView;
document.getElementById("fit").onclick = fitToView;
document.getElementById("exportHtml").onclick = exportHtml;
document.getElementById("exportPng").onclick = exportPng;
document.getElementById("panToggle").onclick = () => setPanEnabled(!panEnabled);
document.getElementById("autoLayout").onclick = () => setAutoLayout(!autoLayout);
document.getElementById("themeToggle").onclick = cycleTheme;
document.getElementById("helpToggle").onclick = () => document.getElementById("helpPanel").classList.toggle("open");

document.addEventListener("pointerdown", event => {{
  const handle = event.target.closest(".resize-handle");
  if (!handle) return;
  event.preventDefault();
  event.stopPropagation();
  const node = handle.closest(".node");
  const content = node.querySelector(".content");
  const startWidth = node.offsetWidth;
  const startContentHeight = content.offsetHeight || Number(node.dataset.contentHeight || 260);
  const startClientX = event.clientX;
  const startClientY = event.clientY;
  handle.setPointerCapture(event.pointerId);

  function resize(moveEvent) {{
    const nextWidth = Math.max(180, Math.min(560, startWidth + (moveEvent.clientX - startClientX) / scale));
    const nextContentHeight = Math.max(96, Math.min(640, startContentHeight + (moveEvent.clientY - startClientY) / scale));
    node.style.width = `${{nextWidth}}px`;
    node.dataset.contentHeight = String(nextContentHeight);
    content.style.maxHeight = `${{nextContentHeight}}px`;
    drawConnections();
  }}

  function stop(upEvent) {{
    handle.releasePointerCapture(upEvent.pointerId);
    handle.removeEventListener("pointermove", resize);
    handle.removeEventListener("pointerup", stop);
    requestAnimationFrame(drawConnections);
  }}

  handle.addEventListener("pointermove", resize);
  handle.addEventListener("pointerup", stop);
}});
window.addEventListener("resize", drawConnections);
setAutoLayout(true);
updateStatus();
setTimeout(fitToView, 120);
</script>
</body>
</html>
"""


def write_output(out_dir, source, suffix, content):
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{source.stem}.structure.{suffix}"
    counter = 1
    while target.exists():
        target = out_dir / f"{source.stem}.structure-{counter}.{suffix}"
        counter += 1
    target.write_text(content, encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description="Generate structure artifacts from Markdown.")
    parser.add_argument("input", type=Path, nargs="+")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument(
        "--formats",
        default="interactive,outline,excalidraw",
        help="Comma-separated list: interactive,outline,mindmap,flowchart,excalidraw,html",
    )
    args = parser.parse_args()

    formats = {item.strip().lower() for item in args.formats.split(",") if item.strip()}
    if "mermaid" in formats:
        formats.update({"mindmap"})
    if "html" in formats:
        formats.update({"interactive"})

    for input_path in args.input:
        source = input_path.resolve()
        if not source.exists():
            raise SystemExit(f"Input file not found: {source}")
        out_dir = args.out_dir.resolve() if args.out_dir else source.parent
        data = parse_markdown(source)

        outputs = []
        if "outline" in formats:
            outputs.append(write_output(out_dir, source, "outline.md", render_outline(data)))
        if "mindmap" in formats:
            outputs.append(write_output(out_dir, source, "mindmap.mmd", render_mermaid(data)))
        if "flowchart" in formats:
            outputs.append(write_output(out_dir, source, "flowchart.mmd", render_flowchart(data)))
        if "excalidraw" in formats:
            outputs.append(write_output(out_dir, source, "excalidraw", render_excalidraw(data)))
        if "interactive" in formats:
            outputs.append(write_output(out_dir, source, "interactive.html", render_html(data)))

        for output in outputs:
            print(output)


if __name__ == "__main__":
    main()
