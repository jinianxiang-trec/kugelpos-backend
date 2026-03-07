#!/usr/bin/env python3
"""
Convert Markdown docs to standalone HTML files for ZIP distribution.
Preserves directory structure, embeds CSS, generates an index.html.
"""

import os
import re
import sys
import shutil
from pathlib import Path

try:
    import markdown
    from markdown.extensions.toc import TocExtension
except ImportError:
    print("Installing markdown library...")
    os.system(f"{sys.executable} -m pip install markdown --quiet")
    import markdown
    from markdown.extensions.toc import TocExtension

# ── Embedded CSS (GitHub-inspired, works offline) ──────────────────────────
CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 16px; line-height: 1.6; color: #24292f;
  display: flex; min-height: 100vh;
}
nav#sidebar {
  width: 260px; min-width: 260px; background: #f6f8fa;
  border-right: 1px solid #d0d7de; padding: 1.5rem 1rem;
  overflow-y: auto; position: sticky; top: 0; height: 100vh;
}
nav#sidebar h2 { font-size: 0.8rem; color: #57606a; text-transform: uppercase;
  letter-spacing: .08em; margin-bottom: 0.75rem; padding-bottom: 0.5rem;
  border-bottom: 1px solid #d0d7de; }
nav#sidebar ul { list-style: none; }
nav#sidebar li { margin: 0; }
nav#sidebar a {
  display: block; padding: 0.3rem 0.5rem; font-size: 0.875rem;
  color: #0969da; text-decoration: none; border-radius: 4px;
}
nav#sidebar a:hover { background: #e6edf3; }
nav#sidebar .nav-section { font-weight: 600; color: #24292f;
  font-size: 0.8rem; padding: 0.4rem 0.5rem 0.2rem; margin-top: 0.5rem; }
nav#sidebar .nav-sub { padding-left: 1rem; }
main#content {
  flex: 1; padding: 2rem 3rem; max-width: 900px; overflow-x: auto;
}
h1,h2,h3,h4,h5,h6 { margin: 1.5rem 0 0.75rem; line-height: 1.3; font-weight: 600; }
h1 { font-size: 2rem; border-bottom: 2px solid #d0d7de; padding-bottom: 0.5rem; }
h2 { font-size: 1.5rem; border-bottom: 1px solid #d0d7de; padding-bottom: 0.3rem; }
h3 { font-size: 1.25rem; }
p  { margin: 0.75rem 0; }
code {
  background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 4px;
  padding: 0.15em 0.4em; font-size: 0.9em; font-family: "SFMono-Regular", Consolas, monospace;
}
pre { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px;
  padding: 1rem; overflow-x: auto; margin: 1rem 0; }
pre code { background: none; border: none; padding: 0; font-size: 0.875rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th,td { border: 1px solid #d0d7de; padding: 0.5rem 0.75rem; text-align: left; }
th { background: #f6f8fa; font-weight: 600; }
tr:nth-child(even) { background: #f6f8fa; }
a { color: #0969da; }
a:hover { text-decoration: underline; }
blockquote { border-left: 4px solid #d0d7de; padding: 0 1rem;
  color: #57606a; margin: 1rem 0; }
ul,ol { margin: 0.5rem 0 0.5rem 1.5rem; }
li { margin: 0.25rem 0; }
img { max-width: 100%; height: auto; }
.breadcrumb { font-size: 0.8rem; color: #57606a; margin-bottom: 1rem; }
.breadcrumb a { color: #57606a; }
"""

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - Kugelpos Documentation</title>
<style>{css}</style>
</head>
<body>
<nav id="sidebar">
  <h2>📖 Kugelpos Docs</h2>
  {nav}
</nav>
<main id="content">
  <div class="breadcrumb">{breadcrumb}</div>
  {body}
</main>
</body>
</html>
"""


def extract_title(md_text: str, filepath: Path) -> str:
    """Extract title from first H1, front matter title, or filename."""
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return filepath.stem.replace("-", " ").replace("_", " ").title()


def strip_front_matter(text: str) -> str:
    """Remove YAML front matter block."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].lstrip("\n")
    return text


def collect_docs(src: Path) -> list[Path]:
    """Collect all .md files, sorted by path."""
    files = []
    for p in sorted(src.rglob("*.md")):
        # skip jekyll includes/layouts
        parts = p.parts
        if any(part.startswith("_") for part in parts):
            continue
        files.append(p)
    return files


def rel_path_to_root(html_path: Path, out_root: Path) -> str:
    """Return '../' repeated for depth of html_path relative to out_root."""
    depth = len(html_path.relative_to(out_root).parts) - 1
    return "../" * depth if depth > 0 else "./"


def build_nav(all_files: list[Path], src: Path, out: Path, current: Path) -> str:
    """Build a simple sidebar nav."""
    prefix = rel_path_to_root(current, out)
    lines = ['<ul>']
    lines.append(f'<li><a href="{prefix}index.html">🏠 Home</a></li>')

    groups: dict[str, list[Path]] = {}
    for f in all_files:
        rel = f.relative_to(src)
        parts = rel.parts
        top = parts[0] if len(parts) > 1 else ""
        groups.setdefault(top, []).append(f)

    for group, files in sorted(groups.items()):
        if group == "":
            continue
        lines.append(f'<li><span class="nav-section">{group.upper()}</span><ul class="nav-sub">')
        for f in files:
            rel = f.relative_to(src)
            html_rel = str(rel.with_suffix(".html"))
            href = prefix + html_rel
            title = extract_title(f.read_text(encoding="utf-8"), f)
            active = " style=\"font-weight:600;color:#24292f\"" if (out / html_rel) == current else ""
            lines.append(f'  <li><a href="{href}"{active}>{title}</a></li>')
        lines.append('</ul></li>')

    lines.append('</ul>')
    return "\n".join(lines)


def build_breadcrumb(html_path: Path, out: Path, src: Path) -> str:
    rel = html_path.relative_to(out)
    parts = list(rel.parts)
    crumbs = ['<a href="' + rel_path_to_root(html_path, out) + 'index.html">Home</a>']
    for i, part in enumerate(parts[:-1]):
        crumbs.append(f'<span>{part}</span>')
    crumbs.append(f'<span>{parts[-1]}</span>')
    return " / ".join(crumbs)


def convert_file(md_path: Path, src: Path, out: Path, all_files: list[Path]) -> None:
    rel = md_path.relative_to(src)
    out_path = out / rel.with_suffix(".html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    raw = md_path.read_text(encoding="utf-8")
    title = extract_title(raw, md_path)
    content = strip_front_matter(raw)

    md = markdown.Markdown(extensions=[
        "fenced_code", "tables", "toc", "attr_list",
        "def_list", "admonition", "codehilite"
    ])
    body = md.convert(content)

    nav = build_nav(all_files, src, out, out_path)
    breadcrumb = build_breadcrumb(out_path, out, src)

    html = HTML_TEMPLATE.format(
        title=title, css=CSS, nav=nav, body=body, breadcrumb=breadcrumb
    )
    out_path.write_text(html, encoding="utf-8")


def build_index(all_files: list[Path], src: Path, out: Path) -> None:
    index_md = src / "index.md"
    index_out = out / "index.html"

    if index_md.exists():
        convert_file(index_md, src, out, all_files)
        # Rename if output was placed in a subdir due to permalink
        potential = out / "index.html"
        if not potential.exists():
            # fallback: find any index.html
            pass
    else:
        # Generate a simple index listing
        nav = build_nav(all_files, src, out, index_out)
        body = "<h1>Kugelpos Documentation</h1><p>Select a document from the sidebar.</p>"
        html = HTML_TEMPLATE.format(
            title="Home", css=CSS, nav=nav, body=body, breadcrumb="Home"
        )
        index_out.write_text(html, encoding="utf-8")


def copy_assets(src: Path, out: Path) -> None:
    """Copy images and SVG files."""
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg", "*.webp"]:
        for img in src.rglob(ext):
            if any(p.startswith("_") for p in img.parts):
                continue
            rel = img.relative_to(src)
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img, dest)


def main():
    if len(sys.argv) < 3:
        print("Usage: md_to_html.py <docs_src_dir> <output_dir>")
        sys.exit(1)

    src = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    all_files = collect_docs(src)
    print(f"Found {len(all_files)} markdown files")

    for f in all_files:
        print(f"  Converting: {f.relative_to(src)}")
        convert_file(f, src, out, all_files)

    # Ensure index.html exists even if index.md was already in all_files
    index_html = out / "index.html"
    if not index_html.exists():
        build_index(all_files, src, out, all_files if True else [])

    copy_assets(src, out)

    total_html = sum(1 for _ in out.rglob("*.html"))
    print(f"Done. Generated {total_html} HTML files in: {out}")


if __name__ == "__main__":
    main()
