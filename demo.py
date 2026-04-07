from __future__ import annotations


def render_demo_page(*, llm_enabled: bool, image_enabled: bool, image_mode: str) -> str:
    llm_label = "Live LLM" if llm_enabled else "Mock Mode"
    llm_badge_class = "badge-live" if llm_enabled else "badge-mock"
    llm_tip = (
        "Real model calls are enabled. The generated output comes from your configured OpenAI-compatible endpoint."
        if llm_enabled
        else "No API key is configured, so the demo is currently using mock article output for safe local testing."
    )
    image_label = "Azure Images" if image_enabled else "Mock Images"
    image_badge_class = "badge-live" if image_enabled else "badge-mock"
    image_tip = (
        "Azure OpenAI image generation is active. Each article can create one cover plus 2-3 supporting images."
        if image_enabled
        else "Azure image credentials are not configured, so the app will generate local SVG mock images for demo use."
    )

    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SEO / GEO Article Writer Console</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}

    :root {{
      --bg: #eef2f6;
      --surface: rgba(255,255,255,0.88);
      --surface-strong: #ffffff;
      --line: rgba(15, 23, 42, 0.09);
      --text: #0f172a;
      --muted: #5b6474;
      --subtle: #8b96a8;
      --hero: #09111f;
      --accent: #0f766e;
      --accent-2: #0ea5e9;
      --accent-soft: rgba(15,118,110,0.10);
      --warning: #b45309;
      --warning-soft: rgba(245,158,11,0.12);
      --danger: #b91c1c;
      --danger-soft: rgba(239,68,68,0.12);
      --code: #0b1220;
      --radius: 22px;
      --shadow: 0 18px 70px rgba(15, 23, 42, 0.10);
    }}

    html, body {{
      margin: 0;
      min-height: 100%;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(14,165,233,0.18), transparent 30%),
        radial-gradient(circle at top right, rgba(15,118,110,0.16), transparent 28%),
        linear-gradient(180deg, #f8fafc 0%, var(--bg) 100%);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
    }}

    a {{ color: inherit; }}

    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      backdrop-filter: blur(18px);
      background: rgba(255,255,255,0.74);
      border-bottom: 1px solid rgba(15,23,42,0.05);
    }}

    .topbar-inner {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 14px 20px;
      display: flex;
      align-items: center;
      gap: 14px;
    }}

    .logo {{
      width: 34px;
      height: 34px;
      border-radius: 12px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 800;
      background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
      box-shadow: 0 10px 24px rgba(14,165,233,0.24);
    }}

    .brand {{
      display: flex;
      flex-direction: column;
      min-width: 0;
    }}

    .brand strong {{
      font-size: 14px;
      letter-spacing: 0.01em;
    }}

    .brand span {{
      font-size: 12px;
      color: var(--muted);
    }}

    .top-links {{
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}

    .container {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 24px 20px 56px;
    }}

    .hero {{
      position: relative;
      overflow: hidden;
      background:
        radial-gradient(circle at top right, rgba(14,165,233,0.22), transparent 30%),
        radial-gradient(circle at bottom left, rgba(15,118,110,0.18), transparent 28%),
        linear-gradient(135deg, #07111d 0%, #0b1628 55%, #13203a 100%);
      color: #f8fafc;
      border-radius: 30px;
      padding: 32px;
      box-shadow: var(--shadow);
      margin-bottom: 20px;
    }}

    .hero-grid {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 22px;
      align-items: end;
    }}

    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: rgba(226,232,240,0.8);
      margin-bottom: 14px;
    }}

    h1 {{
      margin: 0 0 14px;
      font-size: clamp(1rem, 5vw, 2rem);
      line-height: 1.05;
      letter-spacing: -0.04em;
      max-width: 760px;
    }}

    .hero p {{
      margin: 0;
      color: rgba(226,232,240,0.82);
      max-width: 760px;
      font-size: 1.03rem;
    }}

    .hero-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}

    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 7px 12px;
      border-radius: 999px;
      border: 1px solid transparent;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.02em;
    }}

    .badge-live {{
      background: rgba(15,118,110,0.16);
      color: #9af0e2;
      border-color: rgba(154,240,226,0.18);
    }}

    .badge-mock {{
      background: rgba(245,158,11,0.14);
      color: #fde68a;
      border-color: rgba(253,230,138,0.14);
    }}

    .badge-neutral {{
      background: rgba(255,255,255,0.08);
      color: rgba(241,245,249,0.88);
      border-color: rgba(255,255,255,0.10);
    }}

    .hero-note {{
      padding: 18px;
      border-radius: 20px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.08);
    }}

    .hero-note h2 {{
      margin: 0 0 12px;
      font-size: 15px;
      font-weight: 700;
    }}

    .hero-note ul {{
      margin: 0;
      padding-left: 18px;
      color: rgba(226,232,240,0.82);
      font-size: 14px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1.08fr 0.92fr;
      gap: 20px;
      margin-bottom: 20px;
    }}

    .stack {{
      display: grid;
      gap: 20px;
    }}

    .section-stack {{
      display: grid;
      gap: 20px;
    }}

    .card {{
      border-radius: var(--radius);
      border: 1px solid var(--line);
      background: var(--surface);
      backdrop-filter: blur(16px);
      box-shadow: 0 10px 38px rgba(15, 23, 42, 0.06);
      overflow: hidden;
    }}

    .card-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 18px 22px 14px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.86) 0%, rgba(255,255,255,0.52) 100%);
    }}

    .card-title {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}

    .card-title strong {{
      font-size: 15px;
    }}

    .card-title span {{
      font-size: 12px;
      color: var(--muted);
    }}

    .card-body {{
      padding: 22px;
    }}

    .form-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}

    .full {{
      grid-column: 1 / -1;
    }}

    label {{
      display: grid;
      gap: 8px;
      font-size: 13px;
      font-weight: 600;
      color: var(--muted);
    }}

    input, select, textarea, button {{
      font: inherit;
    }}

    input[type="text"], select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.92);
      color: var(--text);
      border-radius: 16px;
      padding: 14px 15px;
      outline: none;
      transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
    }}

    textarea {{
      resize: vertical;
      min-height: 120px;
    }}

    input[type="text"]:focus, select:focus, textarea:focus {{
      border-color: rgba(14,165,233,0.4);
      box-shadow: 0 0 0 4px rgba(14,165,233,0.10);
    }}

    .toggle {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.75);
      color: var(--text);
      cursor: pointer;
    }}

    .actions {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      grid-column: 1 / -1;
      margin-top: 4px;
    }}

    .btn {{
      border: none;
      border-radius: 16px;
      padding: 14px 18px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
    }}

    .btn-primary {{
      background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
      color: white;
      box-shadow: 0 14px 30px rgba(14,165,233,0.20);
    }}

    .btn-ghost {{
      background: rgba(15,23,42,0.04);
      color: var(--text);
      border: 1px solid var(--line);
    }}

    .btn:hover {{
      transform: translateY(-1px);
    }}

    .mini-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}

    .mini-card {{
      padding: 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
    }}

    .mini-card strong {{
      display: block;
      margin-bottom: 8px;
      font-size: 14px;
    }}

    .mini-card p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }}

    .code-block {{
      margin: 0;
      padding: 16px;
      overflow-x: auto;
      border-radius: 18px;
      background: var(--code);
      color: #dbeafe;
      border: 1px solid rgba(148,163,184,0.14);
      font-size: 12.5px;
      line-height: 1.7;
    }}

    .doc-block + .doc-block {{
      margin-top: 16px;
    }}

    .doc-block h3, .result-card h3 {{
      margin: 0 0 10px;
      font-size: 14px;
    }}

    .doc-block p, .muted {{
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 13px;
    }}

    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}

    .summary-card {{
      padding: 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: var(--surface-strong);
    }}

    .summary-card strong {{
      display: block;
      font-size: 1.7rem;
      line-height: 1;
      margin-bottom: 8px;
    }}

    .summary-card span {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 700;
    }}

    .results {{
      display: grid;
      gap: 14px;
    }}

    .shell-tabs {{
      margin-top: 10px;
    }}

    .shell-tab-buttons {{
      display: inline-flex;
      gap: 6px;
      padding: 6px;
      border-radius: 14px;
      background: rgba(15,23,42,0.05);
      border: 1px solid var(--line);
      margin-bottom: 16px;
    }}

    .shell-tab-button {{
      border: none;
      background: transparent;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.03em;
      padding: 9px 14px;
      border-radius: 10px;
      cursor: pointer;
    }}

    .shell-tab-button.active {{
      background: white;
      color: var(--text);
      box-shadow: 0 6px 16px rgba(15,23,42,0.08);
    }}

    .shell-tab-panel {{
      display: none;
    }}

    .shell-tab-panel.active {{
      display: block;
    }}

    .api-surface {{
      border-radius: 18px;
      overflow: hidden;
    }}

    .result-card {{
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.84);
      padding: 18px;
    }}

    .result-head {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
    }}

    .result-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .pill {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      background: rgba(15,23,42,0.06);
      color: var(--muted);
    }}

    .pill-cache {{
      background: rgba(79,70,229,0.10);
      color: #4f46e5;
    }}

    .pill-done {{
      background: var(--accent-soft);
      color: var(--accent);
    }}

    .pill-failed {{
      background: var(--danger-soft);
      color: var(--danger);
    }}

    .article-meta {{
      display: grid;
      gap: 8px;
      margin-top: 14px;
      color: var(--muted);
      font-size: 13px;
    }}

    .result-tabs {{
      margin-top: 16px;
    }}

    .result-tab-buttons {{
      display: inline-flex;
      gap: 6px;
      padding: 6px;
      border-radius: 14px;
      background: rgba(15,23,42,0.05);
      border: 1px solid var(--line);
      margin-bottom: 14px;
    }}

    .result-tab-button {{
      border: none;
      background: transparent;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.03em;
      padding: 9px 14px;
      border-radius: 10px;
      cursor: pointer;
      transition: background 0.15s ease, color 0.15s ease;
    }}

    .result-tab-button.active {{
      background: white;
      color: var(--text);
      box-shadow: 0 6px 16px rgba(15,23,42,0.08);
    }}

    .result-tab-panel {{
      display: none;
    }}

    .result-tab-panel.active {{
      display: block;
    }}

    .preview-surface {{
      border-radius: 18px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.92) 100%);
      padding: 18px;
    }}

    .preview-surface h1,
    .preview-surface h2,
    .preview-surface h3 {{
      letter-spacing: normal;
      max-width: none;
      color: var(--text);
    }}

    .preview-surface h1 {{
      font-size: 1.8rem;
      margin: 0 0 12px;
      line-height: 1.15;
    }}

    .preview-surface h2 {{
      font-size: 1.15rem;
      margin: 18px 0 8px;
    }}

    .preview-surface h3 {{
      font-size: 1rem;
      margin: 14px 0 6px;
    }}

    .preview-surface p,
    .preview-surface li {{
      color: var(--muted);
      font-size: 14px;
    }}

    .preview-surface ul {{
      padding-left: 18px;
    }}

    .preview-surface img.article-generated-image {{
      display: block;
      width: 100%;
      max-width: 100%;
      margin: 16px 0;
      border-radius: 18px;
      border: 1px solid var(--line);
      box-shadow: 0 10px 26px rgba(15,23,42,0.08);
      background: #e2e8f0;
    }}

    .image-toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      grid-column: 1 / -1;
    }}

    .gallery {{
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}

    .gallery-card {{
      border-radius: 18px;
      overflow: hidden;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.92);
    }}

    .gallery-card img {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 10;
      object-fit: cover;
      background: #e2e8f0;
    }}

    .gallery-card-body {{
      padding: 12px;
    }}

    .gallery-card-body strong {{
      display: block;
      margin-bottom: 6px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text);
    }}

    .gallery-card-body p {{
      margin: 0;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.55;
    }}

    .loading-card {{
      display: grid;
      place-items: center;
      min-height: 220px;
      border-radius: 22px;
      border: 1px dashed rgba(15,23,42,0.12);
      background: linear-gradient(180deg, rgba(255,255,255,0.5) 0%, rgba(255,255,255,0.84) 100%);
      color: var(--muted);
      text-align: center;
      padding: 24px;
    }}

    .spinner {{
      width: 48px;
      height: 48px;
      border-radius: 999px;
      border: 4px solid rgba(14,165,233,0.14);
      border-top-color: var(--accent-2);
      animation: spin 0.8s linear infinite;
      margin-bottom: 14px;
    }}

    .loading-card strong {{
      display: block;
      margin-bottom: 6px;
      color: var(--text);
      font-size: 15px;
    }}

    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}

    pre {{
      white-space: pre-wrap;
      word-break: break-word;
    }}

    .empty {{
      padding: 20px;
      border-radius: 18px;
      border: 1px dashed rgba(15,23,42,0.12);
      color: var(--muted);
      background: linear-gradient(180deg, rgba(255,255,255,0.5) 0%, rgba(255,255,255,0.82) 100%);
      text-align: center;
    }}

    .inline-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}

    .inline-list span {{
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(15,23,42,0.05);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}

    @media (max-width: 1080px) {{
      .hero-grid, .grid {{
        grid-template-columns: 1fr;
      }}
      .summary-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .gallery {{
        grid-template-columns: 1fr;
      }}
    }}

    @media (max-width: 720px) {{
      .form-grid, .mini-grid, .summary-grid {{
        grid-template-columns: 1fr;
      }}
      .container {{
        padding-inline: 14px;
      }}
      .hero {{
        padding: 24px;
      }}
      .topbar-inner {{
        padding-inline: 14px;
      }}
      .result-head {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="logo">SG</div>
      <div class="brand">
        <strong>SEO / GEO Article Writer</strong>
        <span>Flask console for AI-ready content generation</span>
      </div>
      <div class="top-links">
        <a class="pill" href="https://www.idtcpack.com/" target="_blank" rel="noreferrer">Live Preview</a>
        <a class="pill" href="/api/health" target="_blank" rel="noreferrer">Health API</a>
      </div>
    </div>
  </header>

  <main class="container">
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">Open Source • SEO + GEO • Async Tasks</div>
          <h1>Create one article per keyword, guided by brand context, cache reuse, and optional images.</h1>
          <p>
            This demo is designed as a clean product-style console: it lets you submit jobs, poll results,
            preview generated HTML, and understand how the API works without leaving the page.
          </p>
          <div class="hero-badges">
            <span class="badge __LLM_BADGE_CLASS__">__LLM_LABEL__</span>
            <span class="badge __IMAGE_BADGE_CLASS__">__IMAGE_LABEL__</span>
            <span class="badge badge-neutral">POST /api/tasks</span>
            <span class="badge badge-neutral">GET /api/tasks/&lt;task_id&gt;</span>
            <span class="badge badge-neutral">Keyword-level cache</span>
          </div>
        </div>
        <aside class="hero-note">
          <h2>Console Notes</h2>
          <ul>
            <li>SEO mode follows title, meta, outline, FAQ, and readability constraints.</li>
            <li>GEO mode focuses on answer-first structure, citability, trust signals, and entity clarity.</li>
            <li>__LLM_TIP__</li>
            <li>__IMAGE_TIP__</li>
          </ul>
        </aside>
      </div>
    </section>

    <section class="section-stack">
      <article class="card">
        <div class="card-header">
          <div class="card-title">
            <strong>Create Task</strong>
            <span>Submit one or more keywords and generate article drafts asynchronously.</span>
          </div>
          <span class="pill">Demo Console</span>
        </div>
        <div class="card-body">
          <form id="task-form" class="form-grid">
            <label>
              Category
              <select name="category" required>
                <option value="seo">SEO</option>
                <option value="geo">GEO</option>
              </select>
            </label>
            <label>
              Language
              <input type="text" name="language" value="English" />
            </label>
            <label class="full">
              Keywords
              <textarea name="keywords" rows="5" required placeholder="portable charger on plane&#10;tsa power bank rules&#10;best travel charger for flights"></textarea>
            </label>
            <label class="full">
              Brand / Product Info
              <textarea name="info" rows="6" placeholder="Brand: VoltGo&#10;Product: 20000mAh portable charger&#10;Highlights: airline-safe, fast charging, digital display"></textarea>
            </label>
            <div class="image-toolbar">
              <label class="toggle">
                <input type="checkbox" name="generate_images" value="true" checked />
                Generate cover + content images
              </label>
              <span class="pill">1 cover + 2-3 body images</span>
            </div>
            <label class="toggle full">
              <input type="checkbox" name="force_refresh" value="true" />
              Force refresh and ignore cache for this run
            </label>
            <div class="actions">
              <button class="btn btn-primary" type="submit" id="submit-btn">Start Task</button>
              <button class="btn btn-ghost" type="button" id="clear-results">Clear Panel</button>
            </div>
          </form>
        </div>
      </article>

      <section class="card">
        <div class="card-header">
          <div class="card-title">
            <strong>Task Result</strong>
            <span>Status, article output, and raw API payload appear here.</span>
          </div>
          <span id="task-meta" class="pill">No active task</span>
        </div>
        <div class="card-body">
          <div id="summary" class="summary-grid">
            <div class="summary-card"><strong>0</strong><span>Total</span></div>
            <div class="summary-card"><strong>0</strong><span>Completed</span></div>
            <div class="summary-card"><strong>0</strong><span>Cached</span></div>
            <div class="summary-card"><strong>0</strong><span>Failed</span></div>
          </div>
          <div class="shell-tabs">
            <div class="shell-tab-buttons">
              <button class="shell-tab-button active" type="button" data-shell-tab="articles">Article Results</button>
              <button class="shell-tab-button" type="button" data-shell-tab="api">API Response</button>
            </div>
            <div class="shell-tab-panel active" data-shell-panel="articles">
              <div id="results" class="results">
                <div class="empty">Submit a task to preview generated SEO or GEO article output.</div>
              </div>
            </div>
            <div class="shell-tab-panel" data-shell-panel="api">
              <div class="api-surface">
                <pre id="api-json" class="code-block">{}</pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="grid">
        <div class="stack">
          <article class="card">
            <div class="card-header">
              <div class="card-title">
                <strong>Writing Model</strong>
                <span>Two different content strategies are used depending on the selected category.</span>
              </div>
            </div>
            <div class="card-body">
              <div class="mini-grid">
                <div class="mini-card">
                  <strong>SEO</strong>
                  <p>Intent analysis, meta structure, H1/H2/H3 outline, long-tail coverage, conclusion, and FAQ.</p>
                </div>
                <div class="mini-card">
                  <strong>GEO</strong>
                  <p>Answer-first layout, extractable headings, proof blocks, references, trust cues, and entity alignment.</p>
                </div>
                <div class="mini-card">
                  <strong>Cache</strong>
                  <p>Each keyword is cached independently using category + normalized keyword + normalized brand info.</p>
                </div>
              </div>
              <div class="inline-list">
                <span>SEO title/meta rules</span>
                <span>GEO answer-first</span>
                <span>FAQ blocks</span>
                <span>Azure image generation</span>
                <span>Async task polling</span>
                <span>Reusable article cache</span>
              </div>
            </div>
          </article>

          <article class="card">
            <div class="card-header">
              <div class="card-title">
                <strong>Image Generation</strong>
                <span>Article generation can now produce one cover image plus supporting in-content visuals.</span>
              </div>
              <span class="pill">Azure OpenAI</span>
            </div>
            <div class="card-body">
              <div class="mini-grid">
                <div class="mini-card">
                  <strong>Cover</strong>
                  <p>A polished editorial hero image is generated from the article title, keyword, and product context.</p>
                </div>
                <div class="mini-card">
                  <strong>Content Images</strong>
                  <p>2-3 supporting images are generated from strategy image briefs or core H2 sections.</p>
                </div>
                <div class="mini-card">
                  <strong>Output</strong>
                  <p>Images are saved locally and injected back into the final HTML preview automatically.</p>
                </div>
              </div>
            </div>
          </article>
        </div>

        <div class="stack">
          <article class="card">
            <div class="card-header">
              <div class="card-title">
                <strong>How It Works</strong>
                <span>The page doubles as a product demo and a developer quickstart.</span>
              </div>
            </div>
            <div class="card-body">
              <div class="doc-block">
                <h3>1. Submit a job</h3>
                <p>Send category, keywords, and brand context to the task API.</p>
                <pre class="code-block">curl -X POST http://127.0.0.1:8028/api/tasks \\
  -H "Content-Type: application/json" \\
  -d '{{"category":"seo","keywords":["portable charger on plane","tsa power bank rules"],"info":"Brand: VoltGo. Product: 20000mAh portable charger.","language":"English","generate_images":true}}'</pre>
              </div>
              <div class="doc-block">
                <h3>2. Poll the task result</h3>
                <p>The server processes each keyword independently and marks cache hits when available.</p>
                <pre class="code-block">curl http://127.0.0.1:8028/api/tasks/&lt;task_id&gt;</pre>
              </div>
              <div class="doc-block">
                <h3>3. Read the article payload</h3>
                <p>Each item returns title, meta title, meta description, HTML, strategy snapshot, and generated image metadata.</p>
              </div>
            </div>
          </article>

          <article class="card">
            <div class="card-header">
              <div class="card-title">
                <strong>Startup</strong>
                <span>Structured to feel closer to the `site-geo` app entry style.</span>
              </div>
            </div>
            <div class="card-body">
              <div class="doc-block">
                <h3>Recommended command</h3>
                <pre class="code-block">python -m flask --app app.main run --debug --host 0.0.0.0 --port 8028</pre>
              </div>
              <div class="doc-block">
                <h3>Shell launcher</h3>
                <pre class="code-block">./start.sh</pre>
              </div>
              <div class="doc-block">
                <h3>Health check</h3>
                <pre class="code-block">curl http://127.0.0.1:8028/api/health</pre>
              </div>
            </div>
          </article>
        </div>
      </section>
    </section>
  </main>

  <script>
    const form = document.getElementById("task-form");
    const submitBtn = document.getElementById("submit-btn");
    const taskMeta = document.getElementById("task-meta");
    const summary = document.getElementById("summary");
    const results = document.getElementById("results");
    const apiJson = document.getElementById("api-json");
    const clearBtn = document.getElementById("clear-results");
    let pollTimer = null;

    function escapeHtml(value) {{
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }}

    function renderSummary(progress) {{
      const info = progress || {{ total: 0, completed: 0, cached: 0, failed: 0 }};
      summary.innerHTML = `
        <div class="summary-card"><strong>${{info.total || 0}}</strong><span>Total</span></div>
        <div class="summary-card"><strong>${{info.completed || 0}}</strong><span>Completed</span></div>
        <div class="summary-card"><strong>${{info.cached || 0}}</strong><span>Cached</span></div>
        <div class="summary-card"><strong>${{info.failed || 0}}</strong><span>Failed</span></div>
      `;
    }}

    function renderResults(task) {{
      taskMeta.textContent = `Task ${{task.task_id}} · ${{task.status}}`;
      renderSummary(task.progress);
      apiJson.textContent = JSON.stringify(task, null, 2);
      const items = task.items || [];

      if (!items.length) {{
        results.innerHTML = '<div class="empty">No task items returned.</div>';
        return;
      }}

      results.innerHTML = items.map((item) => {{
        const article = item.article || {{}};
        const statusClass = item.status === "failed" ? "pill-failed" : item.status === "completed" ? "pill-done" : "";
        const previewHtml = article.html ? article.html : "<p>Waiting for article output...</p>";
        const images = Array.isArray(article.images) ? article.images : [];
        const galleryHtml = images.length ? `
          <div class="gallery">
            ${images.map((image) => `
              <article class="gallery-card">
                <img src="${escapeHtml(image.url)}" alt="${escapeHtml(image.alt)}" />
                <div class="gallery-card-body">
                  <strong>${escapeHtml(image.role)}</strong>
                  <p>${escapeHtml(image.alt)}</p>
                </div>
              </article>
            `).join("")}
          </div>
        ` : "";
        return `
          <article class="result-card">
            <div class="result-head">
              <div>
                <h3>${{escapeHtml(item.keyword)}}</h3>
                <div class="result-meta">
                  <span class="pill ${{statusClass}}">${{escapeHtml(item.status)}}</span>
                  ${{item.cache_hit ? '<span class="pill pill-cache">cache hit</span>' : ''}}
                  ${{article.generation_mode ? `<span class="pill">${{escapeHtml(article.generation_mode)}}</span>` : ''}}
                  ${{article.image_generation_mode ? `<span class="pill">${{escapeHtml(article.image_generation_mode)} images</span>` : ''}}
                </div>
              </div>
            </div>
            ${{item.error ? `<p class="muted" style="color:#b91c1c">${{escapeHtml(item.error)}}</p>` : ''}}
            ${{article.title ? `
              <div class="article-meta">
                <div><strong>Title:</strong> ${{escapeHtml(article.title)}}</div>
                <div><strong>Meta Title:</strong> ${{escapeHtml(article.meta_title)}}</div>
                <div><strong>Meta Description:</strong> ${{escapeHtml(article.meta_description)}}</div>
              </div>
              <div class="result-tabs">
                <div class="result-tab-buttons">
                  <button class="result-tab-button active" type="button" data-tab="preview">Preview</button>
                  <button class="result-tab-button" type="button" data-tab="html">View HTML</button>
                </div>
                <div class="result-tab-panel active" data-panel="preview">
                  <div class="preview-surface">${{previewHtml}}</div>
                </div>
                <div class="result-tab-panel" data-panel="html">
                  <pre class="code-block">${{escapeHtml(article.html)}}</pre>
                </div>
              </div>
              ${{galleryHtml}}
            ` : '<div class="muted">Waiting for article output...</div>'}
          </article>
        `;
      }}).join("");

      results.querySelectorAll(".result-tabs").forEach((tabs) => {{
        const buttons = tabs.querySelectorAll(".result-tab-button");
        const panels = tabs.querySelectorAll(".result-tab-panel");
        buttons.forEach((button) => {{
          button.addEventListener("click", () => {{
            const tab = button.dataset.tab;
            buttons.forEach((item) => item.classList.toggle("active", item === button));
            panels.forEach((panel) => {{
              panel.classList.toggle("active", panel.dataset.panel === tab);
            }});
          }});
        }});
      }});
    }}

    async function fetchTask(taskId) {{
      const response = await fetch(`/api/tasks/${{taskId}}`);
      const payload = await response.json();
      if (!payload.success) {{
        taskMeta.textContent = payload.message || "Task lookup failed";
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Start Task';
        return;
      }}

      const task = payload.data;
      renderResults(task);

      if (!["completed", "failed", "partial_failed"].includes(task.status)) {{
        pollTimer = setTimeout(() => fetchTask(taskId), 1500);
      }} else {{
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Start Task';
      }}
    }}

    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      clearTimeout(pollTimer);
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:3px;margin:0"></span> Starting...';
      taskMeta.textContent = "Submitting task...";
      results.innerHTML = `
        <div class="loading-card">
          <div>
            <div class="spinner"></div>
            <strong>Creating task and generating content...</strong>
            <div>The app is analyzing keywords, drafting the article, and preparing images.</div>
          </div>
        </div>
      `;
      apiJson.textContent = JSON.stringify({ status: "submitting" }, null, 2);
      renderSummary();

      const formData = new FormData(form);
      const payload = {{
        category: formData.get("category"),
        language: formData.get("language"),
        keywords: formData.get("keywords"),
        info: formData.get("info"),
        force_refresh: formData.get("force_refresh") === "true",
        generate_images: formData.get("generate_images") === "true"
      }};

      const response = await fetch("/api/tasks", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload)
      }});
      const data = await response.json();

      if (!data.success) {{
        taskMeta.textContent = data.message || "Task creation failed";
        results.innerHTML = '<div class="empty">The request could not be processed.</div>';
        apiJson.textContent = JSON.stringify(data, null, 2);
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Start Task';
        return;
      }}

      taskMeta.textContent = `Task ${{data.data.task_id}} created`;
      apiJson.textContent = JSON.stringify(data, null, 2);
      fetchTask(data.data.task_id);
    }});

    clearBtn.addEventListener("click", () => {{
      clearTimeout(pollTimer);
      submitBtn.disabled = false;
      submitBtn.innerHTML = 'Start Task';
      taskMeta.textContent = "No active task";
      renderSummary();
      results.innerHTML = '<div class="empty">Submit a task to preview generated SEO or GEO article output.</div>';
      apiJson.textContent = '{}';
    }});

    document.querySelectorAll(".shell-tab-button").forEach((button) => {{
      button.addEventListener("click", () => {{
        const tab = button.dataset.shellTab;
        document.querySelectorAll(".shell-tab-button").forEach((item) => item.classList.toggle("active", item === button));
        document.querySelectorAll(".shell-tab-panel").forEach((panel) => {{
          panel.classList.toggle("active", panel.dataset.shellPanel === tab);
        }});
      }});
    }});
  </script>
</body>
</html>"""

    return (
        html.replace("__LLM_BADGE_CLASS__", llm_badge_class)
        .replace("__LLM_LABEL__", llm_label)
        .replace("__LLM_TIP__", llm_tip)
        .replace("__IMAGE_BADGE_CLASS__", image_badge_class)
        .replace("__IMAGE_LABEL__", image_label)
        .replace("__IMAGE_TIP__", image_tip)
        .replace("{{", "{")
        .replace("}}", "}")
    )
