document.addEventListener("DOMContentLoaded", () => {
  const authForm = document.getElementById("auth-form");
  const taskForm = document.getElementById("task-form");
  const tokenBtn = document.getElementById("token-btn");
  const submitBtn = document.getElementById("submit-btn");
  const tokenPill = document.getElementById("token-pill");
  const tokenNote = document.getElementById("token-note");
  const tokenDisplay = document.getElementById("token-display");
  const tokenValue = document.getElementById("token-value");
  const tokenMeta = document.getElementById("token-meta");
  const taskMeta = document.getElementById("task-meta");
  const summary = document.getElementById("summary");
  const results = document.getElementById("results");
  const apiJson = document.getElementById("api-json");
  const clearBtn = document.getElementById("clear-results");
  let pollTimer = null;
  let accessToken = "";

  async function requestJson(url, options = {}) {
    try {
      const response = await fetch(url, options);
      const rawText = await response.text();
      let data = null;
      try {
        data = rawText ? JSON.parse(rawText) : {};
      } catch {
        data = {
          success: false,
          message: rawText ? `Non-JSON response: ${rawText.slice(0, 180)}` : "Empty response body",
        };
      }
      return {
        ok: response.ok,
        status: response.status,
        data,
      };
    } catch (error) {
      return {
        ok: false,
        status: 0,
        data: {
          success: false,
          message: error?.message || "Network request failed",
        },
      };
    }
  }

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function resetTaskUi(message) {
    submitBtn.disabled = false;
    submitBtn.innerHTML = "Start Task";
    taskMeta.textContent = message || "No active task";
  }

  function renderSummary(progress) {
    const info = progress || { total: 0, completed: 0, cached: 0, failed: 0 };
    summary.innerHTML = `
      <div class="summary-card"><strong>${info.total || 0}</strong><span>Total</span></div>
      <div class="summary-card"><strong>${info.completed || 0}</strong><span>Completed</span></div>
      <div class="summary-card"><strong>${info.cached || 0}</strong><span>Cached</span></div>
      <div class="summary-card"><strong>${info.failed || 0}</strong><span>Failed</span></div>
    `;
  }

  function bindShellTabs() {
    document.querySelectorAll(".shell-tab-button").forEach((button) => {
      button.addEventListener("click", () => {
        const tab = button.dataset.shellTab;
        document
          .querySelectorAll(".shell-tab-button")
          .forEach((item) => item.classList.toggle("active", item === button));
        document.querySelectorAll(".shell-tab-panel").forEach((panel) => {
          panel.classList.toggle("active", panel.dataset.shellPanel === tab);
        });
      });
    });
  }

  function bindResultTabs() {
    results.querySelectorAll(".result-tabs").forEach((tabs) => {
      const buttons = tabs.querySelectorAll(".result-tab-button");
      const panels = tabs.querySelectorAll(".result-tab-panel");
      buttons.forEach((button) => {
        button.addEventListener("click", () => {
          const tab = button.dataset.tab;
          buttons.forEach((item) => item.classList.toggle("active", item === button));
          panels.forEach((panel) => {
            panel.classList.toggle("active", panel.dataset.panel === tab);
          });
        });
      });
    });
  }

  function renderTokenState(payload) {
    accessToken = payload?.data?.access_token || "";
    const tier = payload?.data?.access_tier || "authorized";
    const expiresAt = payload?.data?.expires_at || "";
    tokenPill.textContent = accessToken ? `${tier} token` : "No token";
    if (accessToken) {
      tokenNote.textContent = `Bearer token is active until ${expiresAt}. The demo will attach it automatically to task requests.`;
      tokenMeta.textContent = `${tier.toUpperCase()} access · expires at ${expiresAt}`;
      tokenValue.textContent = accessToken;
      tokenDisplay.classList.remove("hidden");
      return;
    }

    tokenNote.textContent =
      "Token exchange happens once here, then the demo automatically sends `Authorization: Bearer ...` when you create or fetch tasks.";
    tokenMeta.textContent = "Standard access · valid for 1 day";
    tokenValue.textContent = "";
    tokenDisplay.classList.add("hidden");
  }

  function renderResults(task) {
    taskMeta.textContent = `Task ${task.task_id} · ${task.status}`;
    if (task.access_tier) {
      taskMeta.textContent += ` · ${task.access_tier}`;
    }

    renderSummary(task.progress);
    apiJson.textContent = JSON.stringify(task, null, 2);
    const article = task.article || {};

    if (!article.title) {
      results.innerHTML = '<div class="empty">No article result is available for this task yet.</div>';
      return;
    }

    const statusClass =
      task.status === "failed" ? "pill-failed" : task.status === "completed" ? "pill-done" : "";
    const previewHtml = article.html ? article.html : "<p>Waiting for article output...</p>";
    const images = Array.isArray(article.images) ? article.images : [];
    const galleryHtml = images.length
      ? `
          <div class="gallery">
            ${images
              .map(
                (image) => `
              <article class="gallery-card">
                <img src="${escapeHtml(image.data_url || image.url)}" alt="${escapeHtml(image.alt)}" />
                <div class="gallery-card-body">
                  <strong>${escapeHtml(image.role)}</strong>
                  <p>${escapeHtml(image.alt)}</p>
                </div>
              </article>
            `,
              )
              .join("")}
          </div>
        `
      : "";

    results.innerHTML = `
      <article class="result-card">
        <div class="result-head">
          <div>
            <h3>${escapeHtml(task.keyword)}</h3>
            <div class="result-meta">
              <span class="pill ${statusClass}">${escapeHtml(task.status)}</span>
              ${task.cache_hit ? '<span class="pill pill-cache">cache hit</span>' : ""}
              ${article.generation_mode ? `<span class="pill">${escapeHtml(article.generation_mode)}</span>` : ""}
              ${
                article.image_generation_mode
                  ? `<span class="pill">${escapeHtml(article.image_generation_mode)} images</span>`
                  : ""
              }
              ${task.access_tier ? `<span class="pill">${escapeHtml(task.access_tier)} access</span>` : ""}
            </div>
          </div>
        </div>
        ${task.error_message ? `<p class="muted" style="color:#b91c1c">${escapeHtml(task.error_message)}</p>` : ""}
        <div class="article-meta">
          <div><strong>Title:</strong> ${escapeHtml(article.title)}</div>
          <div><strong>Meta Title:</strong> ${escapeHtml(article.meta_title)}</div>
          <div><strong>Meta Description:</strong> ${escapeHtml(article.meta_description)}</div>
        </div>
        <div class="result-tabs">
          <div class="result-tab-buttons">
            <button class="result-tab-button active" type="button" data-tab="preview">Preview</button>
            <button class="result-tab-button" type="button" data-tab="html">View HTML</button>
          </div>
          <div class="result-tab-panel active" data-panel="preview">
            <div class="preview-surface">${previewHtml}</div>
          </div>
          <div class="result-tab-panel" data-panel="html">
            <pre class="code-block">${escapeHtml(article.html)}</pre>
          </div>
        </div>
        ${galleryHtml}
      </article>
    `;

    bindResultTabs();
  }

  async function fetchTask(taskId) {
    const result = await requestJson(`/api/tasks/${taskId}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    const payload = result.data || {};

    if (!payload.success) {
      if (["queued", "running"].includes(payload.status)) {
        taskMeta.textContent = `Task ${payload.task_id || taskId} · ${payload.status}`;
        apiJson.textContent = JSON.stringify(payload, null, 2);
        pollTimer = setTimeout(() => fetchTask(taskId), 1500);
        return;
      }
      taskMeta.textContent = payload.message || `Task lookup failed (${result.status || "network"})`;
      apiJson.textContent = JSON.stringify(payload, null, 2);
      resetTaskUi(taskMeta.textContent);
      return;
    }

    const task = payload.data;
    renderResults(task);

    if (!["completed", "failed", "partial_failed"].includes(task.status)) {
      pollTimer = setTimeout(() => fetchTask(taskId), 1500);
    } else {
      resetTaskUi(taskMeta.textContent);
    }
  }

  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    tokenBtn.disabled = true;
    tokenBtn.innerHTML =
      '<span class="spinner" style="width:18px;height:18px;border-width:3px;margin:0"></span> Exchanging...';

    const formData = new FormData(authForm);
    const payload = {
      access_key: formData.get("access_key"),
    };

    const result = await requestJson("/api/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = result.data || {};
    apiJson.textContent = JSON.stringify(data, null, 2);

    if (!data.success) {
      accessToken = "";
      renderTokenState(null);
      tokenNote.textContent = data.message || "Token exchange failed.";
      tokenBtn.disabled = false;
      tokenBtn.innerHTML = "Get 1-Day Token";
      return;
    }

    renderTokenState(data);
    tokenBtn.disabled = false;
    tokenBtn.innerHTML = "Get 1-Day Token";
  });

  taskForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearTimeout(pollTimer);

    if (!accessToken) {
      taskMeta.textContent = "Exchange a bearer token first";
      results.innerHTML = '<div class="empty">A valid token is required before the task can start.</div>';
      return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML =
      '<span class="spinner" style="width:18px;height:18px;border-width:3px;margin:0"></span> Starting...';
    taskMeta.textContent = "Submitting task...";
    results.innerHTML = `
      <div class="loading-card loading-card-immersive">
        <div class="generation-shell">
          <div class="generation-orbit">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div class="generation-copy">
            <strong>Generating content now</strong>
            <div class="generation-subtitle">Analyzing the keyword, building strategy, drafting HTML, and preparing requested visuals.</div>
          </div>
          <div class="generation-steps">
            <div class="generation-step"><span class="generation-dot"></span><span>Intent and outline planning</span></div>
            <div class="generation-step"><span class="generation-dot"></span><span>SEO / GEO article drafting</span></div>
            <div class="generation-step"><span class="generation-dot"></span><span>HTML polishing and image packaging</span></div>
          </div>
          <div class="generation-bars">
            <span></span>
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    `;
    apiJson.textContent = JSON.stringify({ status: "submitting" }, null, 2);
    renderSummary();

    const formData = new FormData(taskForm);
    const payload = {
      category: formData.get("category"),
      language: formData.get("language"),
      keyword: formData.get("keyword"),
      info: formData.get("info"),
      force_refresh: formData.get("force_refresh") === "true",
      word_limit: Number(formData.get("word_limit") || 1200),
      include_cover: Number(formData.get("include_cover") || 1),
      content_image_count: Number(formData.get("content_image_count") || 3),
    };

    const result = await requestJson("/api/tasks", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(payload),
    });
    const data = result.data || {};

    if (!data.success) {
      taskMeta.textContent = data.message || `Task creation failed (${result.status || "network"})`;
      results.innerHTML = '<div class="empty">The request could not be processed.</div>';
      apiJson.textContent = JSON.stringify(data, null, 2);
      resetTaskUi(taskMeta.textContent);
      return;
    }

    taskMeta.textContent = `Task ${data.data.task_id} created · ${data.data.access_tier || "authorized"}`;
    apiJson.textContent = JSON.stringify(data, null, 2);
    fetchTask(data.data.task_id);
  });

  clearBtn.addEventListener("click", () => {
    clearTimeout(pollTimer);
    resetTaskUi("No active task");
    renderSummary();
    results.innerHTML = '<div class="empty">Exchange a token and submit a task to preview generated SEO or GEO article output.</div>';
    apiJson.textContent = "{}";
  });

  renderTokenState(null);
  bindShellTabs();
});
