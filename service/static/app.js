(() => {
  const state = {
    status: {},
    tasks: [],
    accounts: [],
    selectedTaskId: null,
    taskType: "search",
    taskMode: "single",
    cookieAccountId: null,
    qrSessionId: "",
    qrTimer: null,
    refreshing: false,
  };

  const $ = (id) => document.getElementById(id);
  const config = window.__XHS_CONFIG__ || {};
  const apiBase = String(config.apiBase || "").replace(/\/$/, "");
  const apiUrl = (path) => `${apiBase}${path}`;
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
  const fmt = (value) => value ? String(value).slice(0, 19).replace("T", " ") : "-";
  const num = (value) => Number(value || 0).toLocaleString("zh-CN");
  const compact = (value, length = 80) => {
    const text = String(value || "");
    return text.length > length ? `${text.slice(0, length)}...` : text;
  };

  async function api(path, options = {}) {
    const response = await fetch(apiUrl(path), options);
    if (!response.ok) {
      let message = response.statusText || `HTTP ${response.status}`;
      try {
        const body = await response.json();
        message = body.detail || body.message || JSON.stringify(body);
      } catch (_) {}
      throw new Error(message);
    }
    return response;
  }

  async function json(path, options = {}) {
    return api(path, options).then(r => r.json());
  }

  function headers() {
    return { "Content-Type": "application/json" };
  }

  function parseParams(task) {
    if (!task || !task.params) return {};
    if (typeof task.params === "object") return task.params;
    try { return JSON.parse(task.params); } catch (_) { return {}; }
  }

  function progressData(task) {
    if (!task || !task.progress_data) return {};
    if (typeof task.progress_data === "object") return task.progress_data;
    try { return JSON.parse(task.progress_data); } catch (_) { return {}; }
  }

  function taskKeyword(task) {
    const params = parseParams(task);
    return task.task_type === "search" ? (params.keyword || "") : "";
  }

  function taskTarget(task) {
    const params = parseParams(task);
    return Number(params.max_notes || 0);
  }

  function taskTitle(task) {
    const params = parseParams(task);
    if (task.task_type === "search") return `搜索：${params.keyword || "-"}`;
    if (task.task_type === "creator") return `博主：${compact(params.creator_input, 50)}`;
    if (task.task_type === "note") return `指定笔记：${(params.notes || []).length || 0} 条`;
    return task.task_type || "-";
  }

  function statusText(status) {
    return { pending: "等待中", running: "运行中", paused: "已暂停", completed: "完成", failed: "失败" }[status] || status || "-";
  }

  function statusClass(status) {
    if (["completed"].includes(status)) return "completed";
    if (["running"].includes(status)) return "running";
    if (["pending", "paused"].includes(status)) return status;
    if (["failed"].includes(status)) return "failed";
    return "neutral";
  }

  function accountRuntime(account) {
    return account.runtime_status || account.status || "unknown";
  }

  function isAccountReady(account) {
    const s = accountRuntime(account);
    return s === "ready" || s === "active";
  }

  function renderTop() {
    const readyCount = state.accounts.filter(isAccountReady).length;
    const total = state.accounts.length;
    const serviceReady = state.status.status === "ready" || readyCount > 0;
    const limiter = state.status.rate_limiter || {};
    const penalties = Object.keys(limiter.active_penalties_sec || {}).length;
    $("servicePill").className = `pill ${serviceReady ? "ready" : "paused"}`;
    $("servicePill").textContent = serviceReady ? "服务可运行" : "等待账号";
    $("protectionPill").className = `pill ${penalties ? "paused" : "ready"}`;
    $("protectionPill").textContent = penalties ? `保护退避 ${penalties}` : "保护开启";
    $("queueSize").textContent = state.status.queue_size ?? 0;
    $("readyAccounts").textContent = readyCount;
    $("totalAccounts").textContent = total;
    $("lastRefresh").textContent = `刷新 ${new Date().toLocaleTimeString()}`;
  }

  function renderMetrics() {
    const running = state.tasks.filter(t => t.status === "running").length;
    const pending = state.tasks.filter(t => t.status === "pending").length;
    const paused = state.tasks.filter(t => t.status === "paused").length;
    const failed = state.tasks.filter(t => t.status === "failed").length;
    const notes = state.tasks.reduce((sum, t) => sum + Number(t.notes_count || progressData(t).notes_count || 0), 0);
    const comments = state.tasks.reduce((sum, t) => sum + Number(t.comments_count || progressData(t).comments_count || 0), 0);
    const ready = state.accounts.filter(isAccountReady).length;
    const total = state.accounts.length;
    $("mRunning").textContent = running;
    $("mPending").textContent = pending;
    $("mBlocked").textContent = paused + failed;
    $("mBlockedText").textContent = `${paused} 暂停 / ${failed} 失败`;
    $("mNotes").textContent = num(notes);
    $("mComments").textContent = num(comments);
    $("mAccountRate").textContent = total ? `${Math.round(ready * 100 / total)}%` : "0%";
    $("mAccountText").textContent = `${ready} 可用 / ${total} 总账号`;
  }

  function renderAccounts() {
    const ready = state.accounts.filter(isAccountReady).length;
    const captcha = state.accounts.filter(a => accountRuntime(a) === "captcha" || Number(a.captcha_count || 0) > 0).length;
    const bad = state.accounts.filter(a => ["invalid", "deleted", "failed", "error"].includes(accountRuntime(a))).length;
    $("aReady").textContent = ready;
    $("aCaptcha").textContent = captcha;
    $("aBad").textContent = bad;
    $("aTotal").textContent = state.accounts.length;

    if (!state.accounts.length) {
      $("accountList").innerHTML = `<div class="empty">暂无账号</div>`;
      return;
    }
    $("accountList").innerHTML = state.accounts.map(account => {
      const runtime = accountRuntime(account);
      const cls = isAccountReady(account) ? "ready" : (runtime === "captcha" ? "captcha" : statusClass(runtime));
      const msg = account.message ? `<div class="small-text warn-text mt-xxs">${escapeHtml(compact(account.message, 90))}</div>` : "";
      return `
        <div class="account-item">
          <div class="row-between">
            <div class="truncate"><b>${escapeHtml(account.name || `账号 ${account.id}`)}</b></div>
            <span class="pill ${cls}">${escapeHtml(runtime)}</span>
          </div>
          <div class="small-text muted mono truncate mt-xs">${escapeHtml(account.cookie_preview || "")}</div>
          <div class="small-text muted mt-xs">ID ${account.id} · 验证码 ${account.captcha_count ?? 0} · 检查 ${fmt(account.last_checked)}</div>
          ${msg}
          <div class="row mt-md">
            <button class="btn ghost small" data-cookie-id="${account.id}">替换 Cookie</button>
            <button class="btn danger small" data-delete-id="${account.id}">删除</button>
          </div>
        </div>
      `;
    }).join("");
  }

  function filteredTasks() {
    const status = $("taskStatusFilter").value;
    const keyword = $("taskKeywordFilter").value.trim().toLowerCase();
    return state.tasks.filter(task => {
      if (status && task.status !== status) return false;
      if (!keyword) return true;
      return `${taskTitle(task)} ${task.progress || ""} ${task.error || ""}`.toLowerCase().includes(keyword);
    });
  }

  function renderTasks() {
    const rows = filteredTasks();
    if (!rows.length) {
      $("taskRows").innerHTML = `<tr><td colspan="7"><div class="empty">没有匹配的任务</div></td></tr>`;
      return;
    }
    $("taskRows").innerHTML = rows.map(task => {
      const params = parseParams(task);
      const prog = progressData(task);
      const notes = Number(task.notes_count ?? prog.notes_count ?? 0);
      const comments = Number(task.comments_count ?? prog.comments_count ?? 0);
      const target = Number(params.max_notes || 0);
      const pct = target ? Math.min(100, Math.round(notes * 100 / target)) : 0;
      const message = prog.message || task.progress || task.error || "";
      const updated = prog.updated_at || task.heartbeat_at || task.completed_at || task.started_at || task.created_at;
      const selected = Number(state.selectedTaskId) === Number(task.id) ? " selected" : "";
      const canRun = !["pending", "running"].includes(task.status) && task.task_type !== "note";
      const source = taskKeyword(task);
      return `
        <tr class="task-row${selected}" data-task-id="${task.id}">
          <td class="mono muted">#${task.id}</td>
          <td>
            <div class="truncate strong">${escapeHtml(taskTitle(task))}</div>
            <div class="small-text muted">${escapeHtml(task.task_type || "-")} · 创建 ${fmt(task.created_at)}</div>
          </td>
          <td><span class="pill ${statusClass(task.status)}">${statusText(task.status)}</span></td>
          <td>
            <div><b>${num(notes)}</b>${target ? ` / ${num(target)}` : ""} 篇</div>
            <div class="progress"><span style="width:${pct}%"></span></div>
            <div class="small-text muted">${pct}%${source ? ` · ${escapeHtml(source)}` : ""}</div>
          </td>
          <td><b>${num(comments)}</b><div class="small-text muted">目标 ${num(params.max_comments || 0)} / 篇</div></td>
          <td>
            <div class="truncate">${escapeHtml(message || "-")}</div>
            <div class="small-text muted">更新 ${fmt(updated)}</div>
          </td>
          <td>
            <div class="row">
              <button class="btn ghost small" data-view-id="${task.id}">查看</button>
              ${canRun ? `<button class="btn ghost small" data-resume-id="${task.id}">续爬</button><button class="btn danger small" data-recrawl-id="${task.id}">重爬</button>` : ""}
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }

  function renderAll() {
    renderTop();
    renderMetrics();
    renderAccounts();
    renderTasks();
  }

  async function refreshAll() {
    if (state.refreshing) return;
    state.refreshing = true;
    $("refreshBtn").disabled = true;
    try {
      const [status, tasks, accounts] = await Promise.all([
        json("/api/status"),
        json("/api/tasks"),
        json("/api/accounts"),
      ]);
      state.status = status;
      state.tasks = tasks;
      state.accounts = accounts;
      $("apiError").classList.add("hidden");
      renderAll();
    } catch (error) {
      $("apiError").textContent = `接口异常：${error.message || error}`;
      $("apiError").classList.remove("hidden");
    } finally {
      state.refreshing = false;
      $("refreshBtn").disabled = false;
    }
  }

  function selectTask(taskId) {
    const task = state.tasks.find(t => Number(t.id) === Number(taskId));
    if (!task) return;
    state.selectedTaskId = task.id;
    renderTasks();
  }

  async function submitJson(path, payload) {
    const result = await json(path, { method: "POST", headers: headers(), body: JSON.stringify(payload) });
    await refreshAll();
    alert(result.message || "提交成功");
  }

  function formData(form) {
    const data = new FormData(form);
    return Object.fromEntries(data.entries());
  }

  function lines(value) {
    return String(value || "").split(/\r?\n/).map(v => v.trim()).filter(Boolean);
  }

  function renderTaskForm() {
    const activeKey = `${state.taskType}-${state.taskMode}`;
    document.querySelectorAll("[data-task-type]").forEach(tab => {
      tab.classList.toggle("active", tab.dataset.taskType === state.taskType);
    });
    document.querySelectorAll("[data-task-mode]").forEach(tab => {
      tab.classList.toggle("active", tab.dataset.taskMode === state.taskMode);
    });
    document.querySelectorAll("[data-task-form]").forEach(form => {
      form.classList.toggle("hidden", form.dataset.taskForm !== activeKey);
    });
  }

  function openModal(id) { $(id).classList.add("open"); }
  function closeModal(id) { $(id).classList.remove("open"); }

  async function closeQr() {
    if (state.qrTimer) clearInterval(state.qrTimer);
    state.qrTimer = null;
    if (state.qrSessionId) {
      await json(`/api/accounts/qrcode/${state.qrSessionId}`, { method: "DELETE" }).catch(() => null);
    }
    state.qrSessionId = "";
    $("qrImage").classList.add("hidden");
    $("qrImage").removeAttribute("src");
    $("qrMessage").textContent = "生成后请扫码确认登录";
    closeModal("qrModal");
  }

  async function pollQr() {
    if (!state.qrSessionId) return;
    try {
      const result = await json(`/api/accounts/qrcode/${state.qrSessionId}/poll`);
      $("qrMessage").textContent = result.message || "等待扫码确认";
      if (result.status === "success") {
        clearInterval(state.qrTimer);
        state.qrTimer = null;
        state.qrSessionId = "";
        await refreshAll();
        setTimeout(() => closeQr(), 800);
      }
    } catch (error) {
      $("qrMessage").textContent = `登录检查失败：${error.message || error}`;
    }
  }

  function bindEvents() {
    $("refreshBtn").addEventListener("click", refreshAll);
    $("taskStatusFilter").addEventListener("change", renderTasks);
    $("taskKeywordFilter").addEventListener("input", renderTasks);
    $("exportBtn").addEventListener("click", async () => {
      try {
        const response = await api("/api/export/notes");
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "xhs_notes_export.xlsx";
        a.click();
        URL.revokeObjectURL(url);
      } catch (error) {
        alert(`导出失败：${error.message || error}`);
      }
    });
    document.querySelectorAll("[data-task-type]").forEach(tab => {
      tab.addEventListener("click", () => {
        state.taskType = tab.dataset.taskType;
        renderTaskForm();
      });
    });
    document.querySelectorAll("[data-task-mode]").forEach(tab => {
      tab.addEventListener("click", () => {
        state.taskMode = tab.dataset.taskMode;
        renderTaskForm();
      });
    });
    $("taskRows").addEventListener("click", async event => {
      const view = event.target.closest("[data-view-id]");
      const resume = event.target.closest("[data-resume-id]");
      const recrawl = event.target.closest("[data-recrawl-id]");
      const row = event.target.closest("[data-task-id]");
      try {
        if (view) return selectTask(view.dataset.viewId);
        if (resume && confirm(`续爬任务 #${resume.dataset.resumeId}？`)) {
          await submitJson(`/api/tasks/${resume.dataset.resumeId}/resume`, {});
          return;
        }
        if (recrawl && confirm(`重爬任务 #${recrawl.dataset.recrawlId}？`)) {
          await submitJson(`/api/tasks/${recrawl.dataset.recrawlId}/recrawl`, {});
          return;
        }
        if (row) await selectTask(row.dataset.taskId);
      } catch (error) {
        alert(`操作失败：${error.message || error}`);
      }
    });
    $("accountList").addEventListener("click", async event => {
      const cookieBtn = event.target.closest("[data-cookie-id]");
      const deleteBtn = event.target.closest("[data-delete-id]");
      if (cookieBtn) {
        const account = state.accounts.find(a => Number(a.id) === Number(cookieBtn.dataset.cookieId));
        state.cookieAccountId = account.id;
        $("cookieModalTitle").textContent = `替换 Cookie：${account.name}`;
        $("accountName").value = account.name || "";
        $("accountName").disabled = true;
        $("accountCookie").value = "";
        openModal("cookieModal");
      }
      if (deleteBtn && confirm(`确认删除账号 #${deleteBtn.dataset.deleteId}？`)) {
        await json(`/api/accounts/${deleteBtn.dataset.deleteId}`, { method: "DELETE" });
        await refreshAll();
      }
    });
    $("openCookieBtn").addEventListener("click", () => {
      state.cookieAccountId = null;
      $("cookieModalTitle").textContent = "添加 Cookie";
      $("accountName").disabled = false;
      $("accountName").value = "";
      $("accountCookie").value = "";
      openModal("cookieModal");
    });
    $("saveCookieBtn").addEventListener("click", async () => {
      const cookie = $("accountCookie").value.trim();
      const name = $("accountName").value.trim();
      if (!cookie) return alert("请粘贴 Cookie");
      try {
        if (state.cookieAccountId) {
          await json(`/api/accounts/${state.cookieAccountId}/cookie`, { method: "POST", headers: headers(), body: JSON.stringify({ cookie }) });
        } else {
          if (!name) return alert("请填写账号备注");
          await json("/api/accounts", { method: "POST", headers: headers(), body: JSON.stringify({ name, cookie }) });
        }
        closeModal("cookieModal");
        await refreshAll();
      } catch (error) {
        alert(`保存失败：${error.message || error}`);
      }
    });
    $("healthBtn").addEventListener("click", async () => {
      try {
        const result = await json("/api/accounts/health_check", { method: "POST" });
        await refreshAll();
        alert(result.message || "健康检查完成");
      } catch (error) {
        alert(`健康检查失败：${error.message || error}`);
      }
    });
    $("qrBtn").addEventListener("click", () => openModal("qrModal"));
    $("startQrBtn").addEventListener("click", async () => {
      try {
        $("qrMessage").textContent = "正在启动浏览器并生成二维码...";
        const name = $("qrAccountName").value.trim() || `account-${Date.now()}`;
        const result = await json("/api/accounts/qrcode/start", { method: "POST", headers: headers(), body: JSON.stringify({ name }) });
        state.qrSessionId = result.session_id;
        $("qrImage").src = result.qrcode;
        $("qrImage").classList.remove("hidden");
        $("qrMessage").textContent = "请扫码登录，登录成功后会自动加入账号池。";
        if (state.qrTimer) clearInterval(state.qrTimer);
        state.qrTimer = setInterval(pollQr, 3000);
      } catch (error) {
        $("qrMessage").textContent = `二维码启动失败：${error.message || error}`;
      }
    });
    $("closeQrBtn").addEventListener("click", closeQr);
    document.querySelectorAll("[data-close]").forEach(btn => btn.addEventListener("click", () => closeModal(btn.dataset.close)));

    $("searchSingleForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      await submitJson("/api/tasks/search", {
        keyword: data.keyword.trim(),
        max_notes: Number(data.max_notes),
        max_comments: Number(data.max_comments),
        sort_type: data.sort_type,
        days_limit: Number(data.days_limit),
        force: Boolean(data.force),
      });
    });
    $("searchBatchForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      const keywords = lines(data.keywords);
      if (!keywords.length) return alert("请输入至少一个关键词");
      await submitJson("/api/tasks/batch_search", {
        keywords,
        max_notes: Number(data.max_notes),
        max_comments: Number(data.max_comments),
        sort_type: data.sort_type,
        days_limit: Number(data.days_limit),
      });
    });
    $("creatorSingleForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      await submitJson("/api/tasks/creator", {
        creator_input: data.creator_input.trim(),
        max_notes: Number(data.max_notes),
        force: Boolean(data.force),
      });
    });
    $("creatorBatchForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      const creator_urls = lines(data.creator_urls);
      if (!creator_urls.length) return alert("请输入至少一个博主主页或用户 ID");
      await submitJson("/api/tasks/batch_creator", {
        creator_urls,
        max_notes: Number(data.max_notes),
      });
    });
    $("noteSingleForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      const note_input = String(data.note_input || "").trim();
      if (!note_input) return alert("请输入笔记链接或 ID");
      await submitJson("/api/tasks/note", {
        notes: [{
          note_input,
          d_level: data.d_level,
          quality: data.quality,
        }],
      });
    });
    $("noteBatchForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      const notes = lines(data.inputs).map(note_input => ({
        note_input,
        d_level: data.d_level,
        quality: data.quality,
      }));
      if (!notes.length) return alert("请输入至少一个笔记链接或 ID");
      await submitJson("/api/tasks/note", { notes });
    });
  }

  bindEvents();
  renderTaskForm();
  refreshAll();
  setInterval(refreshAll, 10000);
})();

