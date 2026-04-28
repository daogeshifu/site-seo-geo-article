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
    tokenPill.textContent = accessToken ? `${tier} token` : "No token";
    if (accessToken) {
      tokenNote.textContent = `Bearer token is active until ${expiresAt}. The demo will attach it automatically to outline requests.`;
      tokenMeta.textContent = `${tier.toUpperCase()} access · expires at ${expiresAt}`;
      tokenValue.textContent = accessToken;
      tokenDisplay.classList.remove("hidden");
      return;
    }
    tokenNote.textContent =
      "Token exchange happens once here, then the demo automatically sends `Authorization: Bearer ...` when you generate outlines.";
    tokenMeta.textContent = "Standard access · valid for 1 day";
    tokenValue.textContent = "";
    tokenDisplay.classList.add("hidden");
  }

  function resetOutlineUi(message) {
    outlineBtn.disabled = false;
    outlineBtn.innerHTML = "Start Outline Task";
    outlineMeta.textContent = message || "No outline yet";
  }

  function renderSuggestions(items) {
    if (!Array.isArray(items) || !items.length) {
      suggestionsNode.innerHTML = '<div class="empty">Writing suggestions will appear here.</div>';
      return;
    }
    suggestionsNode.innerHTML = items
      .map((item) => `<article class="outline-item"><p>${escapeHtml(item)}</p></article>`)
      .join("");
  }

  function renderLinks(items) {
    if (!Array.isArray(items) || !items.length) {
      linksNode.innerHTML = '<div class="empty">Recommended internal links will appear here.</div>';
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

  function renderOutlineResult(task) {
    const outline = task.outline || {};
    outlineMeta.textContent = `Outline ${task.outline_id || task.task_id} · ${task.status}`;
    if (task.access_tier) {
      outlineMeta.textContent += ` · ${task.access_tier}`;
    }
    outlineOutput.textContent = outline.outline_markdown || "";
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
      resetOutlineUi("Outline failed");
      return;
    }

    renderOutlineResult(payload.data || {});
    resetOutlineUi(outlineMeta.textContent);
  }

  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    tokenBtn.disabled = true;
    tokenBtn.innerHTML = "Requesting...";
    const formData = new FormData(authForm);
    const result = await requestJson("/api/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_key: formData.get("access_key") }),
    });
    const data = result.data || {};
    apiJson.textContent = JSON.stringify(data, null, 2);
    renderTokenState(data.success ? data : null);
    tokenBtn.disabled = false;
    tokenBtn.innerHTML = "Get 1-Day Token";
  });

  outlineForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearTimeout(pollTimer);
    if (!accessToken) {
      outlineMeta.textContent = "Exchange a bearer token first";
      return;
    }

    outlineBtn.disabled = true;
    outlineBtn.innerHTML = "Starting...";
    outlineMeta.textContent = "Submitting outline task...";
    outlineOutput.textContent = "Submitting outline task...";
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
      resetOutlineUi("Outline failed");
      return;
    }

    const accepted = data.data || {};
    outlineMeta.textContent = `Outline ${accepted.outline_id} created · ${accepted.access_tier || "authorized"}`;
    outlineOutput.textContent = "Outline task created. Polling result...";
    fetchOutline(accepted.outline_id);
  });

  copyBtn.addEventListener("click", async () => {
    const value = outlineOutput.textContent || "";
    if (!value || value === "Generate an outline to preview the result here.") {
      outlineMeta.textContent = "No outline to copy";
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      outlineMeta.textContent = "Outline copied";
    } catch {
      outlineMeta.textContent = "Copy failed";
    }
  });

  clearBtn.addEventListener("click", () => {
    clearTimeout(pollTimer);
    outlineOutput.textContent = "Generate an outline to preview the result here.";
    renderSuggestions([]);
    renderLinks([]);
    apiJson.textContent = "{}";
    resetOutlineUi("No outline yet");
  });

  renderTokenState(null);
  bindShellTabs();
  if (languageSelect && countrySelect) {
    languageSelect.addEventListener("change", () => syncLanguageAndCountry("language"));
    countrySelect.addEventListener("change", () => syncLanguageAndCountry("country"));
    syncLanguageAndCountry("language");
  }
});
