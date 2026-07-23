(() => {
  const state = {
    items: [],
    activeKey: "",
    filter: "",
  };

  const nav = document.getElementById("nav");
  const editor = document.getElementById("editor");
  const search = document.getElementById("search");
  const snackbar = document.getElementById("snackbar");
  const template = document.getElementById("editor-template");

  let snackbarTimer = 0;

  function notify(message, isError) {
    snackbar.textContent = message;
    snackbar.classList.toggle("error", Boolean(isError));
    snackbar.classList.add("show");
    window.clearTimeout(snackbarTimer);
    snackbarTimer = window.setTimeout(() => snackbar.classList.remove("show"), 2600);
  }

  async function request(url, options) {
    const response = await fetch(url, options);
    if (response.status === 401) {
      window.location.reload();
      throw new Error("unauthorized");
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
      throw new Error(payload.message || `请求失败 (${response.status})`);
    }
    return payload.data;
  }

  function matchesFilter(item) {
    if (!state.filter) return true;
    const haystack = `${item.name} ${item.key} ${item.description} ${item.text}`.toLowerCase();
    return haystack.includes(state.filter);
  }

  function renderNav() {
    nav.textContent = "";
    let currentGroup = "";
    let visible = 0;

    state.items.filter(matchesFilter).forEach((item) => {
      if (item.group !== currentGroup) {
        currentGroup = item.group;
        const heading = document.createElement("div");
        heading.className = "nav-group";
        heading.textContent = currentGroup;
        nav.appendChild(heading);
      }

      const button = document.createElement("button");
      button.className = `nav-item${item.key === state.activeKey ? " active" : ""}`;
      button.type = "button";

      const label = document.createElement("span");
      label.className = "label";
      label.textContent = item.name;
      if (item.customized) {
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.title = "已修改";
        label.appendChild(dot);
      }

      const key = document.createElement("span");
      key.className = "key";
      key.textContent = item.key;

      button.append(label, key);
      button.addEventListener("click", () => selectItem(item.key));
      nav.appendChild(button);
      visible += 1;
    });

    if (!visible) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "没有匹配的提示词";
      nav.appendChild(empty);
    }
  }

  function findItem(key) {
    return state.items.find((item) => item.key === key);
  }

  function replaceItem(data) {
    const index = state.items.findIndex((item) => item.key === data.key);
    if (index >= 0) state.items[index] = data;
  }

  function renderEditor() {
    const item = findItem(state.activeKey);
    editor.textContent = "";
    if (!item) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "从左侧选择一个提示词开始编辑";
      editor.appendChild(empty);
      return;
    }

    editor.appendChild(template.content.cloneNode(true));
    const q = (role) => editor.querySelector(`[data-role="${role}"]`);
    const action = (name) => editor.querySelector(`[data-action="${name}"]`);

    q("name").textContent = item.name;
    q("key").textContent = item.key;
    q("description").textContent = item.description;

    const chips = q("chips");
    if (item.customized) {
      chips.appendChild(makeChip("已修改", "chip chip-flag"));
    }
    item.variables.forEach((name) => {
      const chip = makeChip(`{{${name}}}`, "chip");
      chip.title = "点击插入到光标处";
      chip.addEventListener("click", () => insertVariable(q("text"), name));
      chips.appendChild(chip);
    });
    if (!item.variables.length) {
      chips.appendChild(makeChip("此提示词没有变量", "chip chip-static"));
    }

    const textarea = q("text");
    textarea.value = item.text;

    const hint = q("hint");
    const saveButton = action("save");
    const updateDirty = () => {
      const dirty = textarea.value.trim() !== item.text.trim();
      saveButton.disabled = !dirty;
      hint.textContent = dirty
        ? "有未保存的修改 · Ctrl/Cmd + S 保存"
        : item.updated_at
          ? `上次修改：${formatTime(item.updated_at)}`
          : "当前为默认内容";
    };

    textarea.addEventListener("input", updateDirty);
    textarea.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        save(item.key, textarea.value);
      }
    });
    updateDirty();
    renderWarnings(chips, item);

    saveButton.addEventListener("click", () => save(item.key, textarea.value));
    action("reset").addEventListener("click", () => reset(item));
    action("preview").addEventListener("click", () => {
      const panel = q("preview");
      panel.hidden = !panel.hidden;
    });
    action("run-preview").addEventListener("click", () => runPreview(q));
    presetPreviewStage(q, item.key);
  }

  function renderWarnings(chips, item) {
    item.unknown_variables.forEach((name) => {
      chips.appendChild(makeChip(`未知变量 {{${name}}}`, "chip chip-warn"));
    });
    item.missing_variables.forEach((name) => {
      chips.appendChild(makeChip(`缺少 {{${name}}}`, "chip chip-warn"));
    });
  }

  function makeChip(text, className) {
    const chip = document.createElement("span");
    chip.className = className;
    chip.textContent = text;
    return chip;
  }

  function insertVariable(textarea, name) {
    const token = `{{${name}}}`;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    textarea.value = `${textarea.value.slice(0, start)}${token}${textarea.value.slice(end)}`;
    textarea.selectionStart = textarea.selectionEnd = start + token.length;
    textarea.focus();
    textarea.dispatchEvent(new Event("input"));
  }

  function formatTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }

  function presetPreviewStage(q, key) {
    const stage = key.startsWith("draft")
      ? "draft"
      : key.startsWith("polish")
        ? "polish"
        : key.startsWith("outline")
          ? "outline"
          : "strategy";
    q("stage").value = stage;
    if (key.endsWith(".geo")) q("category").value = "geo";
    if (key === "outline.v3" || key.startsWith("outline.publishing") || key.startsWith("shared.v3")) {
      q("stage").value = "outline";
      q("content_version").value = "3.0";
    }
  }

  async function save(key, text) {
    try {
      const data = await request(`/admin/api/prompts/${encodeURIComponent(key)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      replaceItem(data);
      renderNav();
      renderEditor();
      notify("已保存，新的提示词立即生效");
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function reset(item) {
    if (!item.customized) {
      notify("当前已经是默认内容");
      return;
    }
    if (!window.confirm(`确定把“${item.name}”恢复为默认内容吗？`)) return;
    try {
      const data = await request(`/admin/api/prompts/${encodeURIComponent(item.key)}/reset`, { method: "POST" });
      replaceItem(data);
      renderNav();
      renderEditor();
      notify("已恢复默认");
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function runPreview(q) {
    const output = q("preview-output");
    output.textContent = "生成中…";
    try {
      const data = await request("/admin/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stage: q("stage").value,
          category: q("category").value,
          mode_type: Number(q("mode_type").value),
          content_version: q("content_version").value,
          keyword: q("keyword").value,
          language: q("language").value,
          word_limit: Number(q("word_limit").value),
        }),
      });
      output.textContent = data.prompt;
    } catch (error) {
      output.textContent = error.message;
    }
  }

  const backupDialog = document.getElementById("backup-dialog");
  const backupList = document.getElementById("backup-list");
  const backupNote = document.getElementById("backup-note");

  function renderBackups(items) {
    backupList.textContent = "";
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "还没有备份";
      backupList.appendChild(empty);
      return;
    }

    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "backup-row";

      const meta = document.createElement("div");
      meta.className = "meta";
      const when = document.createElement("div");
      when.className = "when";
      when.textContent = formatTime(item.created_at);
      const sub = document.createElement("div");
      sub.className = "sub";
      sub.textContent = `${item.customized_count} / ${item.total_count} 条被修改${item.note ? ` · ${item.note}` : ""}`;
      meta.append(when, sub);

      const restoreButton = document.createElement("button");
      restoreButton.className = "btn btn-outlined btn-small";
      restoreButton.type = "button";
      restoreButton.textContent = "切换到此备份";
      restoreButton.addEventListener("click", () => restoreBackup(item));

      const deleteButton = document.createElement("button");
      deleteButton.className = "btn btn-small";
      deleteButton.type = "button";
      deleteButton.textContent = "删除";
      deleteButton.addEventListener("click", () => deleteBackup(item));

      row.append(meta, restoreButton, deleteButton);
      backupList.appendChild(row);
    });
  }

  async function loadBackups() {
    try {
      const data = await request("/admin/api/backups");
      renderBackups(data.items);
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function reloadPrompts() {
    const data = await request("/admin/api/prompts");
    state.items = data.items;
    if (!findItem(state.activeKey)) {
      state.activeKey = data.items.length ? data.items[0].key : "";
    }
    renderNav();
    renderEditor();
  }

  async function createBackup() {
    try {
      await request("/admin/api/backups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: backupNote.value }),
      });
      backupNote.value = "";
      await loadBackups();
      notify("已备份当前全部提示词");
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function restoreBackup(item) {
    const label = `${formatTime(item.created_at)}${item.note ? `（${item.note}）` : ""}`;
    if (!window.confirm(`确定把全部提示词切换到「${label}」的状态吗？\n当前状态会先自动备份一次。`)) return;
    try {
      await request(`/admin/api/backups/${encodeURIComponent(item.id)}/restore`, { method: "POST" });
      await Promise.all([loadBackups(), reloadPrompts()]);
      notify("已切换到该备份，立即生效");
    } catch (error) {
      notify(error.message, true);
    }
  }

  async function deleteBackup(item) {
    if (!window.confirm(`确定删除「${formatTime(item.created_at)}」这个备份吗？`)) return;
    try {
      await request(`/admin/api/backups/${encodeURIComponent(item.id)}`, { method: "DELETE" });
      await loadBackups();
      notify("备份已删除");
    } catch (error) {
      notify(error.message, true);
    }
  }

  document.getElementById("open-backups").addEventListener("click", () => {
    backupDialog.showModal();
    loadBackups();
  });
  document.getElementById("close-backups").addEventListener("click", () => backupDialog.close());
  document.getElementById("create-backup").addEventListener("click", createBackup);

  function selectItem(key) {
    state.activeKey = key;
    renderNav();
    renderEditor();
  }

  search.addEventListener("input", () => {
    state.filter = search.value.trim().toLowerCase();
    renderNav();
  });

  request("/admin/api/prompts")
    .then((data) => {
      state.items = data.items;
      state.activeKey = data.items.length ? data.items[0].key : "";
      renderNav();
      renderEditor();
    })
    .catch((error) => {
      editor.textContent = "";
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = error.message;
      editor.appendChild(empty);
    });
})();
