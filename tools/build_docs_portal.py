"""
build_docs_portal.py — Vibrante-Node documentation portal generator.

Reads Markdown files from docs_src/ and generates a professional multi-page
documentation portal in docs/portal/ with:
  - Hierarchical sidebar navigation with section grouping
  - Per-page right-hand table of contents
  - Previous / Next page navigation
  - Client-side full-text search (lunr.js via CDN)
  - Syntax highlighting (highlight.js via CDN)
  - Responsive 3-panel layout (sidebar | content | toc)
  - Catppuccin Mocha dark theme matching the app UI

Usage:
    python tools/build_docs_portal.py
    python tools/build_docs_portal.py --src docs_src --out docs/portal
"""

import os
import re
import json
import argparse
from pathlib import Path

try:
    import markdown
    from markdown.extensions.toc import TocExtension
except ImportError:
    raise SystemExit("pip install markdown")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
DEFAULT_SRC = ROOT / "docs_src"
DEFAULT_OUT = ROOT / "docs" / "portal"

# ---------------------------------------------------------------------------
# Section metadata  (filename prefix → display title, icon, group)
# ---------------------------------------------------------------------------
SECTION_META = {
    "01_introduction":           ("Introduction",               "01"),
    "02_getting_started":        ("Getting Started",            "02"),
    "03_user_guide":             ("User Guide",                 "03"),
    "04_workflow_tutorials":     ("Workflow Tutorials",         "04"),
    "05_node_development":       ("Node Development Guide",     "05"),
    "06_backend_architecture":   ("Backend Architecture",       "06"),
    "07_frontend_architecture":  ("Frontend Architecture",      "07"),
    "08_api_reference":          ("API Reference",              "08"),
    "09_advanced_topics":        ("Advanced Topics",            "09"),
    "10_contribution_guide":     ("Contribution Guide",         "10"),
    "11_troubleshooting":        ("Troubleshooting",            "11"),
    "12_examples_library":       ("Examples Library",           "12"),
    "13_general_purpose_automation": ("General Purpose Automation", "13"),
    "14_custom_nodes_api":       ("Custom Nodes API",           "14"),
}

GROUPS = [
    ("Overview",       ["01_introduction", "02_getting_started"]),
    ("Using the App",  ["03_user_guide", "04_workflow_tutorials"]),
    ("Developing Nodes", ["05_node_development", "14_custom_nodes_api", "08_api_reference"]),
    ("Architecture",   ["06_backend_architecture", "07_frontend_architecture"]),
    ("Advanced",       ["09_advanced_topics", "10_contribution_guide"]),
    ("Reference",      ["11_troubleshooting", "12_examples_library", "13_general_purpose_automation"]),
]

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
PORTAL_CSS = """
/* ── Reset & Variables ─────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:       #1e1e2e;
  --surface:  #181825;
  --surface2: #11111b;
  --border:   #313244;
  --text:     #cdd6f4;
  --subtext:  #a6adc8;
  --muted:    #6c7086;
  --lavender: #b4befe;
  --blue:     #89b4fa;
  --teal:     #94e2d5;
  --green:    #a6e3a1;
  --yellow:   #f9e2af;
  --peach:    #fab387;
  --red:      #f38ba8;
  --pink:     #f5c2e7;
  --mauve:    #cba6f7;
  --sidebar-w: 260px;
  --toc-w:    220px;
  --header-h: 56px;
  --font: 'Segoe UI', system-ui, -apple-system, sans-serif;
  --mono: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

/* ── Layout ─────────────────────────────────────────────────────────────── */
html { scroll-behavior: smooth; }
body {
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  min-height: 100vh;
  display: grid;
  grid-template-rows: var(--header-h) 1fr;
  grid-template-columns: var(--sidebar-w) 1fr var(--toc-w);
  grid-template-areas:
    "header header header"
    "sidebar content toc";
}

/* ── Header ─────────────────────────────────────────────────────────────── */
.header {
  grid-area: header;
  position: sticky; top: 0; z-index: 200;
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 16px;
  padding: 0 24px;
}
.header-logo {
  font-weight: 700; font-size: 1.05em;
  color: var(--mauve);
  text-decoration: none;
  white-space: nowrap;
}
.header-version {
  font-size: .78em;
  background: var(--border);
  color: var(--subtext);
  padding: 2px 8px; border-radius: 12px;
}
.header-spacer { flex: 1; }
.search-wrap { position: relative; }
#search-input {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-family: var(--font);
  font-size: .9em;
  padding: 6px 14px 6px 36px;
  width: 260px;
  outline: none;
  transition: border-color .15s;
}
#search-input:focus { border-color: var(--mauve); }
.search-icon {
  position: absolute; left: 11px; top: 50%; transform: translateY(-50%);
  color: var(--muted); pointer-events: none; font-size: .9em;
}
#search-results {
  position: absolute; top: calc(100% + 8px); right: 0;
  width: 380px; max-height: 420px; overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,.5);
  display: none; z-index: 300;
}
#search-results.visible { display: block; }
.search-result-item {
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background .1s;
}
.search-result-item:last-child { border-bottom: none; }
.search-result-item:hover { background: var(--bg); }
.search-result-title { color: var(--blue); font-weight: 600; font-size: .9em; }
.search-result-excerpt { color: var(--subtext); font-size: .82em; margin-top: 2px; line-height: 1.4; }
.search-no-results { padding: 16px; color: var(--muted); text-align: center; font-size: .9em; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
.sidebar {
  grid-area: sidebar;
  position: sticky; top: var(--header-h);
  height: calc(100vh - var(--header-h));
  overflow-y: auto;
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 20px 0;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.sidebar::-webkit-scrollbar { width: 4px; }
.sidebar::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

.sidebar-group { margin-bottom: 4px; }
.sidebar-group-title {
  font-size: .7em;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--muted);
  padding: 10px 20px 4px;
  font-weight: 600;
}
.sidebar-link {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 20px;
  color: var(--subtext);
  text-decoration: none;
  font-size: .88em;
  border-left: 3px solid transparent;
  transition: all .12s;
  line-height: 1.3;
}
.sidebar-link:hover { color: var(--text); background: var(--bg); }
.sidebar-link.active {
  color: var(--mauve);
  border-left-color: var(--mauve);
  background: rgba(180,190,254,.06);
  font-weight: 600;
}
.sidebar-num {
  font-size: .7em;
  color: var(--muted);
  background: var(--border);
  border-radius: 4px;
  padding: 1px 5px;
  flex-shrink: 0;
}
.sidebar-divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 12px 16px;
}

/* ── Content ─────────────────────────────────────────────────────────────── */
.content {
  grid-area: content;
  min-width: 0;
  padding: 40px 48px 80px;
  max-width: 860px;
}
.content-inner { max-width: 820px; }

/* Breadcrumb */
.breadcrumb {
  font-size: .8em;
  color: var(--muted);
  margin-bottom: 28px;
  display: flex; align-items: center; gap: 6px;
}
.breadcrumb a { color: var(--blue); text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.breadcrumb-sep { color: var(--border); }

/* Typography */
h1 { font-size: 2em; color: var(--mauve); border-bottom: 2px solid var(--border); padding-bottom: 12px; margin: 20px 0 20px; }
h2 { font-size: 1.45em; color: var(--blue); margin: 40px 0 14px; padding-top: 8px; }
h3 { font-size: 1.15em; color: var(--teal); margin: 28px 0 10px; }
h4 { font-size: 1em; color: var(--pink); margin: 20px 0 8px; }
h5 { font-size: .95em; color: var(--yellow); margin: 16px 0 6px; }
p  { margin-bottom: 16px; color: var(--text); }
a  { color: var(--blue); }
a:hover { text-decoration: underline; }
strong { color: var(--peach); }
em { color: var(--yellow); font-style: italic; }

ul, ol { margin: 10px 0 16px 24px; }
li { margin-bottom: 6px; }
li > ul, li > ol { margin-top: 4px; margin-bottom: 4px; }

blockquote {
  border-left: 4px solid var(--mauve);
  padding: 10px 20px;
  margin: 16px 0;
  background: rgba(180,190,254,.05);
  border-radius: 0 8px 8px 0;
  color: var(--subtext);
}
blockquote strong { color: var(--mauve); }

hr { border: none; border-top: 1px solid var(--border); margin: 32px 0; }

/* Code */
code {
  background: var(--surface2);
  color: var(--red);
  padding: 2px 7px; border-radius: 5px;
  font-family: var(--mono); font-size: .87em;
}
pre {
  background: var(--surface2) !important;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px 22px;
  overflow-x: auto;
  margin: 16px 0 22px;
  position: relative;
}
pre code {
  background: none !important;
  color: inherit !important;
  padding: 0; font-size: .9em;
  border-radius: 0;
}
/* Copy button */
.copy-btn {
  position: absolute; top: 10px; right: 12px;
  background: var(--border);
  color: var(--subtext);
  border: none; border-radius: 5px;
  padding: 3px 10px; font-size: .75em;
  cursor: pointer; transition: all .12s;
  font-family: var(--font);
}
.copy-btn:hover { background: var(--mauve); color: var(--surface2); }
.copy-btn.copied { background: var(--green); color: var(--surface2); }

/* Tables */
table { border-collapse: collapse; width: 100%; margin: 16px 0 22px; font-size: .9em; }
th { background: var(--border); color: var(--mauve); padding: 10px 14px; text-align: left; font-weight: 600; }
td { border-top: 1px solid var(--border); padding: 9px 14px; color: var(--text); }
tr:nth-child(even) td { background: rgba(17,17,27,.4); }
td code { font-size: .85em; }

/* Callout boxes */
.callout {
  border-radius: 8px;
  padding: 14px 18px;
  margin: 16px 0 22px;
  border-left: 4px solid;
}
.callout-note    { background: rgba(137,180,250,.08); border-color: var(--blue);   }
.callout-tip     { background: rgba(166,227,161,.08); border-color: var(--green);  }
.callout-warning { background: rgba(249,226,175,.08); border-color: var(--yellow); }
.callout-danger  { background: rgba(243,139,168,.08); border-color: var(--red);    }
.callout-title   { font-weight: 700; font-size: .85em; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }
.callout-note    .callout-title { color: var(--blue);   }
.callout-tip     .callout-title { color: var(--green);  }
.callout-warning .callout-title { color: var(--yellow); }
.callout-danger  .callout-title { color: var(--red);    }

/* Validation badges */
.val-badge {
  display: inline-block; font-size: .78em; font-weight: 600;
  padding: 4px 12px; border-radius: 20px; margin-bottom: 18px;
  border: 1px solid transparent; letter-spacing: .02em;
}
.val-badge-ok      { background: rgba(166,227,161,.12); border-color: var(--green);  color: var(--green);  }
.val-badge-warn    { background: rgba(249,226,175,.12); border-color: var(--yellow); color: var(--yellow); }
.val-badge-error   { background: rgba(243,139,168,.12); border-color: var(--red);    color: var(--red);    }
.val-badge-unknown { background: rgba(108,112,134,.12); border-color: #6c7086;       color: #6c7086;       }

/* Prev/Next navigation */
.page-nav {
  display: flex; justify-content: space-between;
  margin-top: 60px; padding-top: 24px;
  border-top: 1px solid var(--border);
  gap: 16px;
}
.page-nav-link {
  display: flex; flex-direction: column;
  text-decoration: none;
  padding: 14px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  min-width: 200px;
  transition: border-color .15s;
  max-width: 48%;
}
.page-nav-link:hover { border-color: var(--mauve); }
.page-nav-label { font-size: .75em; color: var(--muted); margin-bottom: 4px; }
.page-nav-title { color: var(--blue); font-weight: 600; font-size: .95em; }
.page-nav-link.prev .page-nav-label::before { content: '← '; }
.page-nav-link.next { margin-left: auto; text-align: right; }
.page-nav-link.next .page-nav-label::after { content: ' →'; }

/* ── TOC (right panel) ───────────────────────────────────────────────────── */
.toc {
  grid-area: toc;
  position: sticky; top: var(--header-h);
  height: calc(100vh - var(--header-h));
  overflow-y: auto;
  padding: 28px 16px 28px 8px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.toc-title {
  font-size: .72em;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--muted);
  font-weight: 600;
  margin-bottom: 12px;
  padding-left: 8px;
}
.toc-link {
  display: block;
  padding: 4px 8px;
  color: var(--subtext);
  text-decoration: none;
  font-size: .82em;
  border-left: 2px solid transparent;
  border-radius: 0 4px 4px 0;
  transition: all .12s;
  line-height: 1.35;
  margin-bottom: 1px;
}
.toc-link:hover { color: var(--text); border-left-color: var(--border); }
.toc-link.active { color: var(--mauve); border-left-color: var(--mauve); background: rgba(180,190,254,.05); }
.toc-link.toc-h3 { padding-left: 20px; font-size: .79em; }
.toc-link.toc-h4 { padding-left: 32px; font-size: .76em; color: var(--muted); }

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 1100px) {
  body { grid-template-columns: var(--sidebar-w) 1fr 0; }
  .toc { display: none; }
}
@media (max-width: 760px) {
  body { grid-template-columns: 0 1fr 0; grid-template-rows: var(--header-h) 1fr; }
  .sidebar { display: none; }
  .content { padding: 24px 20px 60px; }
  #search-input { width: 180px; }
}

/* ── Index / landing page ────────────────────────────────────────────────── */
.hero { text-align: center; padding: 60px 0 48px; }
.hero h1 { border: none; font-size: 2.8em; }
.hero .tagline { color: var(--subtext); font-size: 1.15em; margin-top: 10px; }
.hero .version-badge {
  display: inline-block;
  background: var(--border); color: var(--mauve);
  padding: 4px 14px; border-radius: 20px; font-size: .85em;
  margin-top: 14px;
}
.group-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; margin: 16px 0 36px; }
.doc-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px 24px;
  text-decoration: none;
  color: var(--text);
  transition: border-color .15s, background .15s;
  display: block;
}
.doc-card:hover { border-color: var(--mauve); background: rgba(180,190,254,.04); }
.doc-card-num { font-size: .72em; color: var(--muted); margin-bottom: 4px; }
.doc-card-title { color: var(--blue); font-weight: 700; font-size: 1em; margin-bottom: 6px; }
.doc-card-desc { color: var(--subtext); font-size: .85em; line-height: 1.5; }
.group-title { color: var(--teal); font-size: 1.1em; font-weight: 600; margin: 32px 0 10px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
"""

# ---------------------------------------------------------------------------
# JavaScript (search + TOC highlighting + copy buttons)
# ---------------------------------------------------------------------------
PORTAL_JS = r"""
// ── Search ──────────────────────────────────────────────────────────────
let _idx = null, _docs = [];

async function initSearch() {
  try {
    const base = document.getElementById('portal-base').dataset.base;
    const resp = await fetch(base + 'search.json');
    _docs = await resp.json();
    _idx = lunr(function() {
      this.ref('id');
      this.field('title', { boost: 10 });
      this.field('body');
      _docs.forEach((d, i) => {
        this.add({ id: i, title: d.title, body: d.body });
      });
    });
  } catch(e) { console.warn('Search index not available', e); }
}

function doSearch(q) {
  const box = document.getElementById('search-results');
  if (!q || q.length < 2) { box.classList.remove('visible'); return; }
  if (!_idx) { box.innerHTML = '<div class="search-no-results">Search index loading…</div>'; box.classList.add('visible'); return; }
  const results = _idx.search(q + '~1');
  if (!results.length) {
    box.innerHTML = '<div class="search-no-results">No results for "' + q + '"</div>';
    box.classList.add('visible'); return;
  }
  box.innerHTML = results.slice(0, 8).map(r => {
    const d = _docs[r.ref];
    const excerpt = d.body.substring(0, 140).replace(/[#*`]/g, '').trim() + '…';
    return `<a class="search-result-item" href="${d.url}">
      <div class="search-result-title">${d.title}</div>
      <div class="search-result-excerpt">${excerpt}</div>
    </a>`;
  }).join('');
  box.classList.add('visible');
}

document.addEventListener('DOMContentLoaded', () => {
  initSearch();
  const inp = document.getElementById('search-input');
  if (inp) {
    inp.addEventListener('input', e => doSearch(e.target.value));
    inp.addEventListener('keydown', e => { if (e.key === 'Escape') { e.target.value=''; document.getElementById('search-results').classList.remove('visible'); }});
  }
  document.addEventListener('click', e => {
    if (!e.target.closest('.search-wrap')) document.getElementById('search-results')?.classList.remove('visible');
  });
  // Keyboard shortcut: / to focus search
  document.addEventListener('keydown', e => {
    if (e.key === '/' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) {
      e.preventDefault(); document.getElementById('search-input')?.focus();
    }
  });

  // ── TOC active section ──────────────────────────────────────────────
  const tocLinks = document.querySelectorAll('.toc-link');
  const headings = document.querySelectorAll('h2[id],h3[id],h4[id]');
  if (tocLinks.length && headings.length) {
    const obs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          tocLinks.forEach(l => l.classList.remove('active'));
          const link = document.querySelector(`.toc-link[href="#${entry.target.id}"]`);
          if (link) link.classList.add('active');
        }
      });
    }, { rootMargin: '-20% 0px -70% 0px' });
    headings.forEach(h => obs.observe(h));
  }

  // ── Copy buttons ────────────────────────────────────────────────────
  document.querySelectorAll('pre').forEach(pre => {
    const btn = document.createElement('button');
    btn.className = 'copy-btn'; btn.textContent = 'Copy';
    btn.addEventListener('click', () => {
      const code = pre.querySelector('code');
      navigator.clipboard.writeText(code ? code.innerText : pre.innerText).then(() => {
        btn.textContent = 'Copied!'; btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
      });
    });
    pre.style.position = 'relative';
    pre.appendChild(btn);
  });

  // ── Sidebar active ──────────────────────────────────────────────────
  const cur = window.location.pathname.split('/').pop();
  document.querySelectorAll('.sidebar-link').forEach(l => {
    if (l.getAttribute('href') === cur || l.getAttribute('href').endsWith(cur)) l.classList.add('active');
  });

  // ── highlight.js ────────────────────────────────────────────────────
  if (window.hljs) {
    hljs.configure({ ignoreUnescapedHTML: true });
    hljs.highlightAll();
  }
});
"""

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
def make_page(
    title, body_html, sidebar_html, toc_html,
    prev_page, next_page, breadcrumb, base_path
):
    prev_link = ""
    if prev_page:
        prev_link = (
            f'<a class="page-nav-link prev" href="{prev_page["file"]}">'
            f'<span class="page-nav-label">Previous</span>'
            f'<span class="page-nav-title">{prev_page["title"]}</span>'
            f'</a>'
        )
    next_link = ""
    if next_page:
        next_link = (
            f'<a class="page-nav-link next" href="{next_page["file"]}">'
            f'<span class="page-nav-label">Next</span>'
            f'<span class="page-nav-title">{next_page["title"]}</span>'
            f'</a>'
        )
    bc_html = ""
    if breadcrumb:
        parts = [f'<a href="{base_path}index.html">Docs</a>']
        for label, _ in breadcrumb:
            parts.append(f'<span class="breadcrumb-sep">›</span><span>{label}</span>')
        bc_html = f'<nav class="breadcrumb">{"".join(parts)}</nav>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Vibrante-Node v2.4.0 — {title}">
<title>{title} — Vibrante-Node Docs</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/atom-one-dark.min.css">
<style>{PORTAL_CSS}</style>
<span id="portal-base" data-base="{base_path}" style="display:none"></span>
</head>
<body>

<!-- ── Header ─────────────────────────────────────────────────────────── -->
<header class="header">
  <a class="header-logo" href="{base_path}index.html">Vibrante-Node</a>
  <span class="header-version">v2.4.0</span>
  <div class="header-spacer"></div>
  <div class="search-wrap">
    <span class="search-icon">&#128269;</span>
    <input id="search-input" type="text" placeholder="Search docs… (/)" autocomplete="off" spellcheck="false">
    <div id="search-results"></div>
  </div>
</header>

<!-- ── Sidebar ────────────────────────────────────────────────────────── -->
<nav class="sidebar">
{sidebar_html}
</nav>

<!-- ── Main content ───────────────────────────────────────────────────── -->
<main class="content">
  <div class="content-inner">
    {bc_html}
    {body_html}
    <nav class="page-nav">
      {prev_link}
      {next_link}
    </nav>
  </div>
</main>

<!-- ── TOC ────────────────────────────────────────────────────────────── -->
<aside class="toc">
  <div class="toc-title">On this page</div>
{toc_html}
</aside>

<script src="https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/highlight.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/lunr@2.3.9/lunr.min.js"></script>
<script>{PORTAL_JS}</script>
</body>
</html>"""


def make_index(groups, pages, base_path=""):
    CARD_DESCS = {
        "01_introduction":           "What Vibrante-Node is, core philosophy, feature overview, and supported integrations.",
        "02_getting_started":        "Installation, first workflow tutorial, UI walkthrough, and running the app.",
        "03_user_guide":             "Canvas navigation, nodes, connections, exec flow, shortcuts, and all UI features.",
        "04_workflow_tutorials":     "Step-by-step tutorials: file automation, DCC workflows, loops, conditions, and more.",
        "05_node_development":       "Create custom nodes from scratch: ports, async execute, registration, and best practices.",
        "06_backend_architecture":   "Execution engine internals: async model, graph evaluation, loops, state management.",
        "07_frontend_architecture":  "PyQt5 UI architecture: canvas, widgets, events, theming, and extensibility.",
        "08_api_reference":          "Complete class and method reference for all public APIs.",
        "09_advanced_topics":        "Plugins, remote execution, DCC bridges, production deployment, and scaling.",
        "10_contribution_guide":     "How to contribute: setup, coding standards, testing, PRs, and versioning.",
        "11_troubleshooting":        "Common problems and solutions: installation, execution, DCC integration, debugging.",
        "12_examples_library":       "Production-ready node examples, complete workflows, and reusable templates.",
        "13_general_purpose_automation": "Using Vibrante-Node for automation beyond VFX: files, APIs, AI, DevOps, and more.",
        "14_custom_nodes_api":       "Complete SDK reference for the node API: every method, hook, pattern, and lifecycle.",
    }
    cards_by_group = ""
    for group_name, keys in groups:
        cards = ""
        for key in keys:
            page = next((p for p in pages if p["key"] == key), None)
            if not page:
                continue
            desc = CARD_DESCS.get(key, "")
            cards += f"""<a class="doc-card" href="{page['file']}">
  <div class="doc-card-num">{page['num']}</div>
  <div class="doc-card-title">{page['title']}</div>
  <div class="doc-card-desc">{desc}</div>
</a>
"""
        if cards:
            cards_by_group += f'<div class="group-title">{group_name}</div>\n<div class="group-grid">\n{cards}</div>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vibrante-Node v2.4.0 — Documentation</title>
<style>{PORTAL_CSS}
body {{ grid-template-columns: 0 1fr 0; }}
.sidebar, .toc {{ display:none; }}
.content {{ max-width: 960px; margin: 0 auto; padding: 40px 32px 80px; }}
</style>
<span id="portal-base" data-base="{base_path}" style="display:none"></span>
</head>
<body>
<header class="header">
  <a class="header-logo" href="index.html">Vibrante-Node</a>
  <span class="header-version">v2.4.0</span>
  <div class="header-spacer"></div>
  <div class="search-wrap">
    <span class="search-icon">&#128269;</span>
    <input id="search-input" type="text" placeholder="Search docs… (/)" autocomplete="off">
    <div id="search-results"></div>
  </div>
</header>
<nav class="sidebar"></nav>
<main class="content">
  <div class="content-inner">
    <div class="hero">
      <h1>Vibrante-Node</h1>
      <p class="tagline">Node-Based Visual Automation Platform</p>
      <span class="version-badge">v2.4.0 Documentation</span>
    </div>
    {cards_by_group}
  </div>
</main>
<aside class="toc"></aside>
<script src="https://cdn.jsdelivr.net/npm/lunr@2.3.9/lunr.min.js"></script>
<script>{PORTAL_JS}</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slugify(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text)


def add_heading_ids(html_body):
    def replacer(m):
        tag = m.group(1)
        content = m.group(2)
        hid = slugify(content)
        return f'<{tag} id="{hid}">{content}</{tag}>'
    return re.sub(r'<(h[1-4])>(.*?)</\1>', replacer, html_body, flags=re.S)


def build_toc(html_body):
    items = []
    for m in re.finditer(r'<(h[234])[^>]*id="([^"]*)"[^>]*>(.*?)</h[234]>', html_body, re.S):
        tag, hid, raw = m.group(1), m.group(2), m.group(3)
        text = re.sub(r'<[^>]+>', '', raw).strip()
        css_class = f"toc-link toc-{tag}"
        items.append(f'<a class="{css_class}" href="#{hid}">{text}</a>')
    return "\n".join(items)


def build_sidebar(pages, current_key, groups):
    html = ""
    for group_name, keys in groups:
        html += f'<div class="sidebar-group">\n<div class="sidebar-group-title">{group_name}</div>\n'
        for key in keys:
            page = next((p for p in pages if p["key"] == key), None)
            if not page:
                continue
            active = ' active' if key == current_key else ''
            html += (
                f'<a class="sidebar-link{active}" href="{page["file"]}">'
                f'<span class="sidebar-num">{page["num"]}</span>'
                f'{page["title"]}</a>\n'
            )
        html += '</div>\n'
    return html


def post_process_callouts(html):
    """Convert > [!NOTE], > [!TIP], > [!WARNING], > [!DANGER] blockquotes to styled callouts."""
    def replace_callout(m):
        kind = m.group(1).lower()
        inner = m.group(2)
        inner = re.sub(r'^<p>\s*\[!(NOTE|TIP|WARNING|DANGER)\]\s*', '', inner, flags=re.I)
        title = kind.capitalize()
        return f'<div class="callout callout-{kind}"><div class="callout-title">{title}</div>{inner}</div>'
    return re.sub(
        r'<blockquote>\s*<p>\[!(NOTE|TIP|WARNING|DANGER)\](.*?)</blockquote>',
        replace_callout, html, flags=re.S | re.I
    )


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------
def _load_validation(out_dir: Path) -> dict:
    """Load validation.json from the parent docs/ directory (written by validate_docs.py)."""
    # out_dir is docs/portal/; validation.json lives in docs/
    vpath = out_dir.parent / "validation.json"
    if not vpath.exists():
        return {}
    try:
        import json as _json
        return _json.loads(vpath.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _validation_badge_html(md_filename: str, val_data: dict) -> str:
    """
    Return an HTML banner to prepend to the page body.
    Green = verified, Yellow = warnings, Red = errors, Grey = not validated.
    """
    per_page = val_data.get("per_page", {})
    info = per_page.get(md_filename)
    if not info:
        return (
            '<div class="val-badge val-badge-unknown" title="Not yet validated against source code">'
            '&#9679; Not validated</div>'
        )
    errs = info.get("errors", 0)
    warns = info.get("warnings", 0)
    if errs > 0:
        label = f"&#10006; {errs} error{'s' if errs != 1 else ''}"
        if warns:
            label += f", {warns} warning{'s' if warns != 1 else ''}"
        return f'<div class="val-badge val-badge-error" title="Documentation accuracy issues found">{label}</div>'
    if warns > 0:
        return (
            f'<div class="val-badge val-badge-warn" title="{warns} warning(s) — review recommended">'
            f'&#9888; {warns} warning{"s" if warns != 1 else ""}</div>'
        )
    return '<div class="val-badge val-badge-ok" title="Verified against source code">&#10003; Verified</div>'


def build(src_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load validation data (may be empty if validate_docs.py hasn't run yet)
    val_data = _load_validation(out_dir)

    # Collect source files
    md_files = sorted(src_dir.glob("*.md"))
    if not md_files:
        print(f"  WARNING: No .md files found in {src_dir}")
        return

    # Build page list
    pages = []
    for md_path in md_files:
        stem = md_path.stem
        meta = SECTION_META.get(stem)
        if not meta:
            title = stem.replace("_", " ").title()
            num = stem[:2] if stem[:2].isdigit() else "??"
        else:
            title, num = meta
        html_name = stem + ".html"
        pages.append({
            "key":   stem,
            "title": title,
            "num":   num,
            "file":  html_name,
            "src":   md_path,
        })

    # Markdown processor
    md_proc = markdown.Markdown(extensions=[
        'tables', 'fenced_code', 'nl2br',
        TocExtension(permalink=False),
        'attr_list',
        'def_list',
        'abbr',
    ])

    search_docs = []

    for i, page in enumerate(pages):
        md_proc.reset()
        src_text = page["src"].read_text(encoding="utf-8", errors="replace")
        body_html = md_proc.convert(src_text)
        body_html = add_heading_ids(body_html)
        body_html = post_process_callouts(body_html)

        toc_html = build_toc(body_html)
        sidebar_html = build_sidebar(pages, page["key"], GROUPS)

        # Prepend validation badge
        badge = _validation_badge_html(page["src"].name, val_data)
        body_html = badge + "\n" + body_html

        prev_page = pages[i - 1] if i > 0 else None
        next_page = pages[i + 1] if i < len(pages) - 1 else None

        breadcrumb = [(page["title"], page["file"])]

        html = make_page(
            title=page["title"],
            body_html=body_html,
            sidebar_html=sidebar_html,
            toc_html=toc_html,
            prev_page=prev_page,
            next_page=next_page,
            breadcrumb=breadcrumb,
            base_path="",
        )

        out_path = out_dir / page["file"]
        out_path.write_text(html, encoding="utf-8")
        print(f"  OK: {page['file']}")

        # Search index entry
        plain = re.sub(r'<[^>]+>', ' ', body_html)
        plain = re.sub(r'\s+', ' ', plain).strip()
        search_docs.append({
            "id":    i,
            "title": page["title"],
            "url":   page["file"],
            "body":  plain[:8000],
        })

    # Search index
    search_path = out_dir / "search.json"
    search_path.write_text(json.dumps(search_docs, ensure_ascii=False, separators=(',', ':')), encoding="utf-8")
    print("  OK: search.json")

    # Index page
    index_html = make_index(GROUPS, pages, base_path="")
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    print("  OK: index.html")

    print(f"\n  Portal written to: {out_dir}")
    print(f"  Pages: {len(pages)}  |  Search entries: {len(search_docs)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Build Vibrante-Node documentation portal")
    parser.add_argument("--src", default=str(DEFAULT_SRC), help="Path to docs_src/ directory")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output directory (docs/portal/)")
    args = parser.parse_args()

    src = Path(args.src)
    out = Path(args.out)

    if not src.exists():
        raise SystemExit(f"Source directory not found: {src}\nCreate docs_src/ and add .md files.")

    print(f"Building documentation portal...")
    print(f"  Source: {src}")
    print(f"  Output: {out}")
    build(src, out)


if __name__ == "__main__":
    main()
