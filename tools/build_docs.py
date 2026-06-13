"""Convert project Markdown docs to styled HTML files in docs/."""
import os, re, markdown

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_OUT = os.path.join(ROOT, "docs")
os.makedirs(DOCS_OUT, exist_ok=True)

MAIN_DOCS = [
    ("USER_GUIDE.md",       "User Guide"),
    ("NODE_BUILDER_API.md", "Node Builder API"),
    ("AUTOMATION_API.md",   "Automation API"),
    ("DEVELOPER.md",        "Developer Documentation"),
    ("DOCUMENTATION.md",    "Technical Feature List"),
]

RELEASE_DOCS = [
    ("RELEASE_v2.5.0.md",          "Release Notes v2.5.0"),
    ("RELEASE_v2.4.0.md",          "Release Notes v2.4.0"),
    ("releases/RELEASE_v2.3.0.md", "Release Notes v2.3.0"),
    ("releases/RELEASE_v2.2.1.md", "Release Notes v2.2.1"),
    ("releases/RELEASE_v2.2.0.md", "Release Notes v2.2.0"),
    ("releases/RELEASE_v2.1.1.md", "Release Notes v2.1.1"),
    ("releases/RELEASE_v2.1.0.md", "Release Notes v2.1.0"),
    ("releases/RELEASE_v2.0.0.md", "Release Notes v2.0.0"),
    ("releases/RELEASE_v1.8.5.md", "Release Notes v1.8.5"),
    ("releases/RELEASE_v1.8.4.md", "Release Notes v1.8.4"),
    ("releases/RELEASE_v1.8.3.md", "Release Notes v1.8.3"),
    ("releases/RELEASE_v1.8.2.md", "Release Notes v1.8.2"),
    ("releases/RELEASE_v1.8.1.md", "Release Notes v1.8.1"),
    ("releases/RELEASE_v1.8.0.md", "Release Notes v1.8.0"),
    ("releases/RELEASE_v1.7.0.md", "Release Notes v1.7.0"),
    ("releases/RELEASE_v1.6.1.md", "Release Notes v1.6.1"),
    ("releases/RELEASE_v1.6.0.md", "Release Notes v1.6.0"),
    ("releases/RELEASE_v1.5.0.md", "Release Notes v1.5.0"),
    ("releases/RELEASE_v1.4.0.md", "Release Notes v1.4.0"),
    ("releases/RELEASE_v1.3.0.md", "Release Notes v1.3.0"),
    ("releases/RELEASE_v1.2.0.md", "Release Notes v1.2.0"),
    ("releases/RELEASE_v1.1.5.md", "Release Notes v1.1.5"),
    ("releases/RELEASE_v1.1.0.md", "Release Notes v1.1.0"),
    ("releases/RELEASE_v1.0.5.md", "Release Notes v1.0.5"),
]

ALL_DOCS = MAIN_DOCS + RELEASE_DOCS

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
       background: #1e1e2e; color: #cdd6f4; line-height: 1.7; }
.sidebar { position: fixed; top: 0; left: 0; width: 220px; height: 100vh;
           background: #181825; overflow-y: auto; padding: 20px 0; z-index: 100; }
.sidebar h2 { font-size: 13px; color: #6c7086; text-transform: uppercase;
              letter-spacing: .08em; padding: 0 18px 10px; }
.sidebar a  { display: block; padding: 6px 18px; color: #a6adc8; text-decoration: none;
              font-size: 13px; border-left: 3px solid transparent; transition: all .15s; }
.sidebar a:hover, .sidebar a.active { color: #cba6f7; border-left-color: #cba6f7;
                                       background: #1e1e2e; }
.sidebar .nav-release { font-size: 12px; padding: 4px 18px; }
.content { margin-left: 220px; max-width: 920px; padding: 40px 48px; }
h1 { font-size: 2em; color: #cba6f7; border-bottom: 2px solid #313244; padding-bottom: 10px; margin: 28px 0 16px; }
h2 { font-size: 1.45em; color: #89b4fa; margin: 32px 0 12px; }
h3 { font-size: 1.15em; color: #94e2d5; margin: 22px 0 8px; }
h4 { font-size: 1em; color: #f5c2e7; margin: 16px 0 6px; }
p  { margin-bottom: 14px; color: #cdd6f4; }
a  { color: #89b4fa; }
ul, ol { margin: 10px 0 14px 22px; }
li { margin-bottom: 5px; }
code { background: #313244; color: #f38ba8; padding: 2px 6px; border-radius: 4px; font-size: .88em; font-family: 'Consolas','Courier New',monospace; }
pre  { background: #181825; border: 1px solid #313244; border-radius: 8px;
       padding: 18px 20px; overflow-x: auto; margin: 14px 0 20px; }
pre code { background: none; color: #a6e3a1; padding: 0; font-size: .9em; }
table { border-collapse: collapse; width: 100%; margin: 14px 0 20px; font-size: .92em; }
th { background: #313244; color: #cba6f7; padding: 9px 14px; text-align: left; }
td { border-top: 1px solid #313244; padding: 8px 14px; }
tr:nth-child(even) td { background: #1e1e2e; }
hr { border: none; border-top: 1px solid #313244; margin: 28px 0; }
blockquote { border-left: 4px solid #6c7086; padding-left: 16px; color: #a6adc8; margin: 14px 0; }
@media (max-width: 700px) { .sidebar { display: none; } .content { margin-left: 0; padding: 24px 18px; } }
"""

JS = """
document.addEventListener('DOMContentLoaded', function() {
    var links = document.querySelectorAll('.sidebar a');
    var headings = document.querySelectorAll('h1,h2,h3');
    window.addEventListener('scroll', function() {
        var cur = '';
        headings.forEach(function(h) { if (h.offsetTop <= window.scrollY + 80) cur = h.id; });
        links.forEach(function(a) {
            a.classList.toggle('active', a.getAttribute('href') === '#' + cur);
        });
    });
});
"""

MAIN_NAV = "\n".join(
    f'<a href="{fn.replace(".md", ".html")}">{title}</a>'
    for fn, title in MAIN_DOCS
)

RELEASE_NAV = "\n".join(
    f'<a class="nav-release" href="{os.path.basename(fn).replace(".md", ".html")}">{title}</a>'
    for fn, title in RELEASE_DOCS
)

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text)

def build_sidebar(html_body):
    items = []
    for m in re.finditer(r'<h([123])[^>]*id="([^"]*)"[^>]*>(.*?)</h\1>', html_body, re.S):
        level, hid, text = m.group(1), m.group(2), re.sub(r'<[^>]+>', '', m.group(3))
        indent = {"1": 0, "2": 0, "3": 14}.get(level, 0)
        items.append(f'<a href="#{hid}" style="padding-left:{18+indent}px">{text}</a>')
    return "\n".join(items)

def add_ids(html_body):
    def replacer(m):
        tag, content = m.group(1), m.group(2)
        hid = slugify(re.sub(r'<[^>]+>', '', content))
        return f'<{tag} id="{hid}">{content}</{tag}>'
    return re.sub(r'<(h[123])>(.*?)</\1>', replacer, html_body, flags=re.S)

md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc', 'nl2br'])

for filename, title in ALL_DOCS:
    src = os.path.join(ROOT, filename)
    if not os.path.exists(src):
        print(f"  SKIP (not found): {filename}")
        continue
    with open(src, encoding="utf-8") as f:
        text = f.read()
    md.reset()
    body = md.convert(text)
    body = add_ids(body)
    sidebar_items = build_sidebar(body)
    out_name = os.path.basename(filename).replace(".md", ".html")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Vibrante-Node v2.5.0</title>
<style>{CSS}</style>
</head>
<body>
<nav class="sidebar">
  <h2>Vibrante-Node</h2>
  {MAIN_NAV}
  <hr style="border-color:#313244;margin:10px 18px">
  <h2 style="margin-top:8px">Release Notes</h2>
  {RELEASE_NAV}
  <hr style="border-color:#313244;margin:10px 18px">
  <h2 style="margin-top:8px">On this page</h2>
  {sidebar_items}
</nav>
<main class="content">
{body}
</main>
<script>{JS}</script>
</body>
</html>"""
    out_path = os.path.join(DOCS_OUT, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  OK: {out_name}")

# index page
main_cards = "\n".join(
    f'  <a class="card" href="{fn.replace(".md",".html")}"><h3>{title}</h3></a>'
    for fn, title in MAIN_DOCS
)
release_cards = "\n".join(
    f'  <a class="card" href="{os.path.basename(fn).replace(".md",".html")}"><h3>{title}</h3></a>'
    for fn, title in RELEASE_DOCS
)

index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Vibrante-Node v2.5.0 — Help</title>
<style>{CSS}
.hero {{ text-align:center; padding: 60px 0 40px; }}
.hero h1 {{ border:none; font-size:2.4em; }}
.hero p {{ color:#a6adc8; font-size:1.1em; margin-top:8px; }}
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:18px; margin-top:30px; }}
.card {{ background:#181825; border:1px solid #313244; border-radius:10px; padding:22px 24px; text-decoration:none; color:#cdd6f4; transition:.15s; }}
.card:hover {{ border-color:#cba6f7; background:#1e1e2e; }}
.card h3 {{ color:#cba6f7; margin-bottom:6px; font-size:1.05em; }}
.card p {{ color:#a6adc8; font-size:.9em; margin:0; }}
.section-title {{ color:#89b4fa; font-size:1.2em; margin: 36px 0 12px; border-bottom: 1px solid #313244; padding-bottom:8px; }}
</style>
</head>
<body>
<main class="content" style="margin-left:0;max-width:900px;margin:0 auto">
<div class="hero">
  <h1>Vibrante-Node v2.5.0</h1>
  <p>Documentation &amp; Help</p>
</div>
<h2 class="section-title">Documentation</h2>
<div class="card-grid">
{main_cards}
</div>
<h2 class="section-title">Release Notes</h2>
<div class="card-grid">
{release_cards}
</div>
</main>
</body>
</html>"""
with open(os.path.join(DOCS_OUT, "index.html"), "w", encoding="utf-8") as f:
    f.write(index_html)
print("  OK: index.html")
print(f"\nDocs written to: {DOCS_OUT}")

# Run documentation validation (docs_src/ ↔ source code)
import subprocess, sys
docs_src = os.path.join(ROOT, "docs_src")
portal_out = os.path.join(ROOT, "docs", "portal")
validate_script = os.path.join(os.path.dirname(__file__), "validate_docs.py")
if os.path.isdir(docs_src):
    print("\nValidating documentation against source code...")
    subprocess.run(
        [sys.executable, validate_script, "--src", docs_src, "--out", os.path.join(ROOT, "docs")],
        check=False,
    )

# Build the full documentation portal (docs_src/ → docs/portal/)
portal_script = os.path.join(os.path.dirname(__file__), "build_docs_portal.py")
if os.path.isdir(docs_src):
    print("\nBuilding documentation portal...")
    subprocess.run([sys.executable, portal_script, "--src", docs_src, "--out", portal_out], check=False)
else:
    print(f"\n  SKIP portal (docs_src/ not found — run once docs_src/ is populated)")
