document.addEventListener("DOMContentLoaded", () => {
  const authForm = document.getElementById("auth-form");
  const outlineForm = document.getElementById("outline-form");
  const tokenBtn = document.getElementById("token-btn");
  const outlineBtn = document.getElementById("outline-btn");
  const copyBtn = document.getElementById("copy-outline-btn");
  const clearBtn = document.getElementById("clear-outline-btn");
  const tokenPill = document.getElementById("token-pill");
  const tokenNote = document.getElementById("token-note");
  const tokenDisplay = document.getElementById("token-display");
  const tokenMeta = document.getElementById("token-meta");
  const tokenValue = document.getElementById("token-value");
  const outlineMeta = document.getElementById("outline-meta");
  const outlineOutput = document.getElementById("outline-output");
  const suggestionsNode = document.getElementById("outline-suggestions");
  const linksNode = document.getElementById("outline-links");
  const apiJson = document.getElementById("api-json");
  const languageSelect = document.getElementById("language-select");
  const countrySelect = document.getElementById("country-select");
  const contentVersionSelect = document.getElementById("content-version-select");
  const publishingContextSelect = document.getElementById("publishing-context-select");
  const publishingContextField = document.getElementById("publishing-context-field");
  let accessToken = "";
  let pollTimer = null;
  const languageCountryMap = {
    English: "us",
    Chinese: "cn",
    French: "fr",
    German: "de",
    Dutch: "nl",
  };
  const countryLanguageMap = Object.fromEntries(
    Object.entries(languageCountryMap).map(([language, country]) => [country, language]),
  );

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

  function renderTokenState(payload) {
    accessToken = payload?.data?.access_token || "";
    const tier = payload?.data?.access_tier || "authorized";
    const expiresAt = payload?.data?.expires_at || "";
    tokenPill.textContent = accessToken ? `${tier} · 已连接` : "未连接";
    if (accessToken) {
      tokenNote.textContent = `授权有效期至 ${expiresAt}，生成时会自动验证。`;
      tokenMeta.textContent = `${tier.toUpperCase()} 访问 · 到期时间 ${expiresAt}`;
      tokenValue.textContent = accessToken;
      tokenDisplay.classList.remove("hidden");
      return;
    }
    tokenNote.textContent =
      "请先连接访问密钥，生成时会自动完成验证。";
    tokenMeta.textContent = "标准访问 · 有效期 1 天";
    tokenValue.textContent = "";
    tokenDisplay.classList.add("hidden");
  }

  function resetOutlineUi(message) {
    outlineBtn.disabled = false;
    outlineBtn.innerHTML = "生成大纲";
    outlineMeta.textContent = message || "等待生成";
  }

  function renderSuggestions(items) {
    if (!Array.isArray(items) || !items.length) {
      suggestionsNode.innerHTML = '<div class="empty">大纲生成后，这里会显示写作建议。</div>';
      return;
    }
    suggestionsNode.innerHTML = items
      .map((item) => `<article class="outline-item"><p>${escapeHtml(item)}</p></article>`)
      .join("");
  }

  function renderLinks(items) {
    if (!Array.isArray(items) || !items.length) {
      linksNode.innerHTML = '<div class="empty">大纲生成后，这里会显示推荐内链。</div>';
      return;
    }
    linksNode.innerHTML = items
      .map(
        (item) => `
          <article class="outline-item">
            <strong>${escapeHtml(item.label || item.url)}</strong>
            <p><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.url)}</a></p>
            <p>${escapeHtml(item.reason || "")}</p>
          </article>
        `
      )
      .join("");
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

  function syncLanguageAndCountry(source) {
    if (!languageSelect || !countrySelect) {
      return;
    }
    if (source === "language") {
      const mappedCountry = languageCountryMap[languageSelect.value];
      if (mappedCountry) {
        countrySelect.value = mappedCountry;
      }
      return;
    }
    const mappedLanguage = countryLanguageMap[countrySelect.value];
    if (mappedLanguage) {
      languageSelect.value = mappedLanguage;
    }
  }

  function syncContentVersion() {
    if (!contentVersionSelect || !publishingContextSelect || !publishingContextField) {
      return;
    }
    const isV3 = contentVersionSelect.value === "3.0";
    publishingContextSelect.disabled = !isV3;
    publishingContextField.classList.toggle("field-disabled", !isV3);
  }

  function renderOutlineResult(task) {
    const outline = task.outline || {};
    outlineMeta.textContent = `Outline ${task.outline_id || task.task_id} · ${task.status}`;
    if (task.access_tier) {
      outlineMeta.textContent += ` · ${task.access_tier}`;
    }
    outlineOutput.textContent = outline.outline_markdown || "";
    copyBtn.disabled = !outline.outline_markdown;
    renderSuggestions(outline.writing_suggestions || []);
    renderLinks(outline.recommended_internal_links || []);
    apiJson.textContent = JSON.stringify(task, null, 2);
  }

  async function fetchOutline(outlineId) {
    const result = await requestJson(`/api/outline/${outlineId}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    const payload = result.data || {};

    if (!payload.success) {
      apiJson.textContent = JSON.stringify(payload, null, 2);
      if (["queued", "running"].includes(payload.status)) {
        outlineMeta.textContent = `Outline ${payload.outline_id || outlineId} · ${payload.status}`;
        pollTimer = setTimeout(() => fetchOutline(outlineId), 1500);
        return;
      }
      outlineOutput.textContent = payload.message || "Unable to generate outline.";
      resetOutlineUi("大纲生成失败");
      return;
    }

    renderOutlineResult(payload.data || {});
    resetOutlineUi(outlineMeta.textContent);
  }

  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    tokenBtn.disabled = true;
    tokenBtn.innerHTML = "连接中…";
    const formData = new FormData(authForm);
    const result = await requestJson("/api/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_key: formData.get("access_key") }),
    });
    const data = result.data || {};
    apiJson.textContent = JSON.stringify(data, null, 2);
    renderTokenState(data.success ? data : null);
    if (!data.success) tokenNote.textContent = data.message || "连接失败，请检查访问密钥后重试。";
    tokenBtn.disabled = false;
    tokenBtn.innerHTML = "连接密钥";
  });

  outlineForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearTimeout(pollTimer);
    if (!accessToken) {
      outlineMeta.textContent = "请先连接访问密钥";
      return;
    }

    outlineBtn.disabled = true;
    outlineBtn.innerHTML = "提交中…";
    outlineMeta.textContent = "正在提交大纲任务…";
    outlineOutput.textContent = "正在提交大纲任务…";
    copyBtn.disabled = true;
    renderSuggestions([]);
    renderLinks([]);
    apiJson.textContent = JSON.stringify({ status: "submitting" }, null, 2);

    const formData = new FormData(outlineForm);
    const payload = {
      category: formData.get("category"),
      language: formData.get("language") || "English",
      provider: formData.get("provider") || "openai",
      word_limit: Number(formData.get("word_limit") || 1200),
      keyword: formData.get("keyword"),
      info: formData.get("info") || "",
      task_context: {
        content_version: formData.get("content_version") || "2.0",
        publishing_context: formData.get("publishing_context") || "official_website",
        country: formData.get("country") || "",
        requires_shopify_link: formData.get("requires_shopify_link") === "true",
        shopify_url: formData.get("shopify_url") || "",
        ai_qa_content: formData.get("ai_qa_content") || "",
        ai_qa_source: formData.get("ai_qa_source") || "",
      },
    };

    const result = await requestJson("/api/outline", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(payload),
    });
    const data = result.data || {};
    apiJson.textContent = JSON.stringify(data, null, 2);

    if (!data.success) {
      outlineOutput.textContent = data.message || "Unable to generate outline.";
      resetOutlineUi("大纲生成失败");
      return;
    }

    const accepted = data.data || {};
    outlineMeta.textContent = `Outline ${accepted.outline_id} created · ${accepted.access_tier || "authorized"}`;
    outlineOutput.textContent = "Outline task created. Polling result...";
    fetchOutline(accepted.outline_id);
  });

  copyBtn.addEventListener("click", async () => {
    const value = outlineOutput.textContent || "";
    if (!value || value === "填写左侧主题并生成大纲，内容将在这里显示。") {
      outlineMeta.textContent = "暂无可复制的大纲";
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      outlineMeta.textContent = "大纲已复制";
    } catch {
      outlineMeta.textContent = "复制失败，请手动选择大纲文本复制。";
    }
  });

  clearBtn.addEventListener("click", () => {
    clearTimeout(pollTimer);
    copyBtn.disabled = true;
    outlineOutput.textContent = "填写左侧主题并生成大纲，内容将在这里显示。";
    renderSuggestions([]);
    renderLinks([]);
    apiJson.textContent = "{}";
    resetOutlineUi("等待生成");
  });

  renderTokenState(null);
  bindShellTabs();
  if (languageSelect && countrySelect) {
    languageSelect.addEventListener("change", () => syncLanguageAndCountry("language"));
    countrySelect.addEventListener("change", () => syncLanguageAndCountry("country"));
    syncLanguageAndCountry("language");
  }
  if (contentVersionSelect) {
    contentVersionSelect.addEventListener("change", syncContentVersion);
    syncContentVersion();
  }
});
