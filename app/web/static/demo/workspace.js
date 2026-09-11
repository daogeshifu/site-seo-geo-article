document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#task-form, #outline-form");
  const feedback = document.getElementById("form-feedback");
  const keyword = form.elements.keyword;
  const auth = document.getElementById("auth-section");
  const tokenDisplay = document.getElementById("token-display");
  const result = document.getElementById("result-panel");
  const toast = document.getElementById("workspace-toast");
  let toastTimer;
  function notify(message) {
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 4500);
  }
  const fullscreen = document.getElementById("fullscreen-btn");
  fullscreen.addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      notify("当前浏览器不支持进入全屏，页面已使用全宽布局。");
    }
  });
  document.addEventListener("fullscreenchange", () => {
    fullscreen.textContent = document.fullscreenElement ? "⛶ 退出全屏" : "⛶ 全屏";
    fullscreen.setAttribute("aria-pressed", String(Boolean(document.fullscreenElement)));
  });
  fullscreen.setAttribute("aria-pressed", "false");
  function updateSettings() {
    const outlineMode = form.elements.mode_type?.value === "2";
    document.getElementById("keyword-label").innerHTML = (outlineMode ? "文章大纲" : "主题关键词") + ' <em>必填</em>';
    keyword.placeholder = outlineMode ? "# 文章标题\n## 第一部分\n## 第二部分\n### 需要展开的细节" : "例如：便携充电宝可以带上飞机吗？";
    document.getElementById("keyword-hint").textContent = outlineMode
      ? "粘贴完整大纲，使用 #、##、### 区分标题层级，生成时将遵循此结构。"
      : "建议每次填写一个明确主题，描述越具体，生成内容越聚焦。";
    const parts = [form.elements.category.value.toUpperCase(), form.elements.language.selectedOptions[0].text, (form.elements.word_limit.value || "1200") + " 字"];
    if (form.elements.include_cover) parts.push("封面 " + form.elements.include_cover.value + " 张", "正文配图 " + form.elements.content_image_count.value + " 张");
    document.getElementById("settings-summary").textContent = parts.join(" · ");
    const url = form.elements.shopify_url;
    const requires = form.elements.requires_shopify_link;
    const needsUrl = requires.type === "checkbox" ? requires.checked : requires.value === "true";
    url.required = needsUrl;
    url.setCustomValidity(needsUrl && !url.value.trim() ? "请填写产品页面链接，或关闭加入产品链接选项。" : "");
  }
  form.addEventListener("input", () => {
    keyword.setCustomValidity("");
    feedback.classList.remove("is-error");
    updateSettings();
  });
  form.addEventListener("change", updateSettings);
  // Open collapsed sections before native validation tries to focus a field.
  form.addEventListener("invalid", event => {
    let parent = event.target.parentElement;
    while (parent && parent !== form) {
      if (parent.tagName === "DETAILS") parent.open = true;
      parent = parent.parentElement;
    }
    feedback.textContent = event.target.validationMessage;
    feedback.classList.add("is-error");
  }, true);
  form.addEventListener("submit", event => {
    if (!keyword.value.trim()) {
      event.preventDefault();
      event.stopImmediatePropagation();
      keyword.setCustomValidity("请先输入主题关键词或文章大纲。");
      keyword.reportValidity();
      return;
    }
    if (tokenDisplay.classList.contains("hidden")) {
      event.preventDefault();
      event.stopImmediatePropagation();
      auth.open = true;
      document.querySelector('[name="access_key"]').focus();
      feedback.textContent = "还差一步：请先连接上方的访问密钥，再开始生成。";
      feedback.classList.add("is-error");
      notify("请先连接访问密钥");
      return;
    }
    feedback.textContent = "正在提交，请稍候。生成进度会在结果区自动更新。";
    feedback.classList.remove("is-error");
    result.scrollIntoView({behavior: "smooth", block: "start"});
  }, true);
  new MutationObserver(() => {
    const connected = !tokenDisplay.classList.contains("hidden");
    document.getElementById("token-pill").classList.toggle("pill-done", connected);
    if (connected) {
      auth.open = false;
      feedback.textContent = "已连接，可以开始创作。";
      notify("连接成功，访问授权有效期 1 天");
    }
  }).observe(tokenDisplay, {attributes: true, attributeFilter: ["class"]});
  const status = document.querySelector("#task-meta, #outline-meta");
  status.setAttribute("role", "status");
  new MutationObserver(() => {
    feedback.textContent = status.textContent;
  }).observe(status, {childList: true, characterData: true, subtree: true});
  updateSettings();
});
