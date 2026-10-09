(() => {
  const state = {
    status: {},
    tasks: [],
    accounts: [],
    candidates: [],
    selectedTaskId: null,
    selectedTaskIds: new Set(),
    taskType: "search",
    taskMode: "single",
    taskProvider: "local",
    cookieAccountId: null,
    qrSessionId: "",
    qrTimer: null,
    qrStarting: false,
    qrPolling: "",
    qrGeneration: 0,
    refreshing: false,
  };

  const $ = (id) => document.getElementById(id);
  let modalReturnFocus = null;
  let taskDrawerReturnFocus = null;
  function showToast(message, type = "success") {
    const region = $("toastRegion");
    if (!region) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type === "error" ? "error" : (type === "warn" ? "warn" : "")}`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    toast.textContent = message;
    region.appendChild(toast);
    if (type !== "error") window.setTimeout(() => toast.remove(), 4200);
  }
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

  function apiErrorMessage(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map(item => {
        if (!item || typeof item !== "object") return String(item);
        const location = Array.isArray(item.loc) ? item.loc.join(".") : "";
        return `${location ? `${location}: ` : ""}${item.msg || JSON.stringify(item)}`;
      }).join("; ");
    }
    if (detail && typeof detail === "object") {
      return detail.message || JSON.stringify(detail);
    }
    return String(detail || "");
  }

  async function api(path, options = {}) {
    const response = await fetch(apiUrl(path), options);
    if (!response.ok) {
      let message = response.statusText || `HTTP ${response.status}`;
      try {
        const body = await response.json();
        message = apiErrorMessage(body.detail ?? body.message ?? body);
      } catch (_) {}
      const error = new Error(message);
      error.status = response.status;
      throw error;
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
    if (task.task_type === "note" && Array.isArray(params.notes)) return params.notes.length;
    return Number(params.max_notes || 0);
  }

  function taskTitle(task) {
    const params = parseParams(task);
    if (task.task_type === "search") return `搜索：${params.keyword || "-"}`;
    if (task.task_type === "creator") return `博主：${compact(params.creator_input, 50)}`;
    if (task.task_type === "note") return `指定笔记：${(params.notes || []).length || 0} 条`;
    return task.task_type || "-";
  }

  function taskProvider(task) {
    return task.provider || parseParams(task).provider || "local";
  }

  function providerLabel(provider) {
    return provider === "justoneapi" ? "JustOneAPI" : "本地爬虫";
  }

  function providerReason(reason) {
    return {
      no_ready_account: "无可用账号",
      missing_token: "未配置 Token",
      disabled: "未启用",
      quota_exceeded: "额度已用尽",
      daily_quota: "今日额度已用尽",
      rate_limit: "请求频率受限",
      credential: "凭证无效",
      insufficient_balance: "余额不足",
      token_limit: "Token 额度受限",
      client_closed: "客户端已关闭",
      crawler_engine_stopped: "本地引擎未启动",
    }[reason] || reason || "不可用";
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
    return s === "ready" || s === "crawling";
  }

  function setServiceStatus(label, tone) {
    const indicator = $("serviceStatus");
    if ($("serviceStatusText").textContent !== label) $("serviceStatusText").textContent = label;
    indicator.dataset.state = tone;
  }

  function renderServiceStatus() {
    const status = state.status;
    const providerReady = Object.values(status.providers || {}).some(provider => provider.ready);
    const running = Number(status.task_counts?.running || 0);
    const queued = Number(status.queue_size || 0);
    if (running || status.status === "crawling") return setServiceStatus("运行中", "running");
    if (providerReady && queued) return setServiceStatus("等待执行", "waiting");
    if (providerReady) return setServiceStatus("就绪", "ready");
    const fallback = {
      initializing: ["初始化中", "loading"],
      waiting_qrcode: ["等待扫码", "waiting"],
      need_login: ["等待登录", "waiting"],
      captcha: ["需要验证", "error"],
      error: ["服务异常", "error"],
      stopped: ["已停止", "waiting"],
    }[status.status] || ["无可用来源", "waiting"];
    setServiceStatus(...fallback);
  }

  function renderSummary() {
    const healthy = state.accounts.filter(isAccountReady).length;
    const accountTotal = state.accounts.length;
    const counts = state.status.task_counts || {};
    const total = Object.values(counts).reduce((sum, count) => sum + Number(count || 0), 0);
    const completed = Number(counts.completed || 0);
    $("accountHealthValue").textContent = accountTotal ? `${Math.round(healthy * 100 / accountTotal)}%` : "-";
    $("accountHealthDetail").textContent = `可用 ${num(healthy)} / ${num(accountTotal)}`;
    $("taskTotalValue").textContent = num(total);
    $("taskCompletedValue").textContent = num(completed);
    $("taskCompletionValue").textContent = total ? `${Math.round(completed * 100 / total)}%` : "-";
  }

  function candidateCookieReady(candidate) {
    return Boolean(
      candidate.has_web_session &&
      candidate.has_a1 &&
      candidate.has_web_id &&
      candidate.has_gid &&
      candidate.has_xsecappid &&
      candidate.has_id_token
    );
  }

  function renderProviderPicker() {
    const selected = state.taskProvider;
    document.querySelectorAll("[data-task-provider]").forEach(tab => {
      const active = tab.dataset.taskProvider === selected;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-checked", String(active));
      tab.setAttribute("tabindex", active ? "0" : "-1");
    });
    $("justoneApiOptions").classList.toggle("hidden", selected !== "justoneapi");
    document.querySelectorAll("[data-local-only]").forEach(field => {
      field.classList.toggle("hidden", selected !== "local");
    });

    const providers = state.status.providers || {};
    const detail = providers[selected];
    const fallbackReady = selected === "local" && state.accounts.some(isAccountReady);
    const ready = detail === undefined
      ? fallbackReady
      : (typeof detail === "boolean" ? detail : Boolean(detail && (
        detail.ready === true || detail.readiness === true || ["ready", "ok"].includes(detail.status || detail.readiness)
      )));
    const statusKnown = detail !== undefined || selected === "local";
    const pill = $("providerReadiness");
    pill.className = `pill ${ready ? "ready" : (statusKnown ? "paused" : "neutral")}`;
    pill.textContent = ready ? "可用" : (statusKnown ? providerReason(detail && (detail.reason || detail.message)) : "状态未知");
  }

  function renderAccounts() {
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

  function renderCandidates() {
    if (!$("candidateList")) return;
    if (!state.candidates.length) {
      $("candidateList").innerHTML = `<div class="empty">暂无候选账号</div>`;
      return;
    }
    $("candidateList").innerHTML = state.candidates.map(candidate => {
      const ready = candidateCookieReady(candidate);
      const cookieLabel = ready ? "网页 Cookie 完整" : "缺网页 Cookie";
      const cookieClass = ready ? "ready" : "paused";
      return `
        <div class="candidate-item" data-candidate-id="${candidate.id}">
          <div class="row-between">
            <div class="truncate"><b>${escapeHtml(candidate.nickname || `候选账号 ${candidate.id}`)}</b></div>
            <span class="pill ${cookieClass}">${cookieLabel}</span>
          </div>
          <div class="candidate-grid">
            <div class="candidate-field"><div class="label">手机号</div><div class="value mono">${escapeHtml(candidate.phone || "-")}</div></div>
            <div class="candidate-field"><div class="label">密码</div><div class="value mono sensitive-value">已保护</div></div>
            <div class="candidate-field"><div class="label">用户 ID</div><div class="value mono">${escapeHtml(candidate.user_id || "-")}</div></div>
            <div class="candidate-field"><div class="label">注册日期</div><div class="value">${escapeHtml(candidate.registered_at || "-")}</div></div>
            <div class="candidate-field"><div class="label">短信链接</div><div class="value">${candidate.sms_link ? "已保存" : "-"}</div></div>
            <div class="candidate-field"><div class="label">辅助链接</div><div class="value">${candidate.fm_link ? "已保存" : "-"}</div></div>
            <div class="candidate-field"><div class="label">Cookie 数</div><div class="value">${num(candidate.cookie_count || 0)}</div></div>
            <div class="candidate-field"><div class="label">来源</div><div class="value">${escapeHtml(candidate.source || "-")}</div></div>
          </div>
          <div class="candidate-actions">
            <button class="btn ghost small" data-candidate-copy="login" data-candidate-id="${candidate.id}">复制登录信息</button>
            <button class="btn ghost small" data-candidate-copy="sms" data-candidate-id="${candidate.id}">复制短信链接</button>
            <button class="btn ghost small" data-candidate-copy="fm" data-candidate-id="${candidate.id}">复制辅助链接</button>
            <button class="btn ghost small" data-candidate-copy="cookie" data-candidate-id="${candidate.id}">复制候选 Cookie</button>
            <button class="btn danger small" data-candidate-delete="${candidate.id}">删除</button>
          </div>
        </div>
      `;
    }).join("");
  }

  function filteredTasks() {
    const status = $("taskStatusFilter").value;
    return state.tasks.filter(task => !status || task.status === status);
  }

  function renderTasks() {
    const rows = filteredTasks();
    const visibleIds = rows.map(task => Number(task.id));
    const selectedVisible = visibleIds.filter(id => state.selectedTaskIds.has(id)).length;
    $("selectionCount").textContent = `已选 ${state.selectedTaskIds.size} 项`;
    $("exportBtn").disabled = state.selectedTaskIds.size === 0;
    $("deleteTasksBtn").disabled = state.selectedTaskIds.size === 0;
    $("selectVisibleTasks").checked = visibleIds.length > 0 && selectedVisible === visibleIds.length;
    $("selectVisibleTasks").indeterminate = selectedVisible > 0 && selectedVisible < visibleIds.length;
    $("selectVisibleTasks").disabled = visibleIds.length === 0;
    if (!rows.length) {
      $("taskRows").innerHTML = `<div class="empty">没有匹配的任务</div>`;
      return;
    }
    $("taskRows").innerHTML = rows.map(task => {
      const params = parseParams(task);
      const prog = progressData(task);
      const notes = Number(task.notes_count ?? prog.notes_count ?? 0);
      const comments = Number(task.comments_count ?? prog.comments_count ?? 0);
      const target = taskTarget(task);
      const pct = target ? Math.min(100, Math.round(notes * 100 / target)) : 0;
      const message = prog.message || task.progress || task.error || "";
      const selected = Number(state.selectedTaskId) === Number(task.id) ? " selected" : "";
      const canResume = !["pending", "running"].includes(task.status);
      const canRecrawl = canResume && task.task_type !== "note";
      return `
        <article class="task-card${selected}${state.selectedTaskIds.has(Number(task.id)) ? " checked" : ""}" role="listitem" data-task-id="${task.id}" tabindex="0" aria-label="打开${escapeHtml(taskTitle(task))}详情">
          <div class="task-card-primary">
            <input type="checkbox" data-select-task-id="${task.id}" aria-label="选择${escapeHtml(taskTitle(task))}" ${state.selectedTaskIds.has(Number(task.id)) ? "checked" : ""}>
            <h3 class="task-card-title">${escapeHtml(taskTitle(task))}</h3>
            <span class="pill ${statusClass(task.status)}">${escapeHtml(statusText(task.status))}</span>
            <span class="task-message" title="${escapeHtml(message || "-")}">${escapeHtml(compact(message || "-", 48))}</span>
            <div class="task-card-actions">
              <button class="btn ghost small" data-view-id="${task.id}">查看</button>
              ${canResume ? `<button class="btn ghost small" data-resume-id="${task.id}">续爬</button>` : ""}
              ${canRecrawl ? `<button class="btn danger small" data-recrawl-id="${task.id}">重爬</button>` : ""}
            </div>
          </div>
          <div class="task-card-secondary">
            <span>笔记 <strong>${num(notes)}${target ? ` / ${num(target)}` : ""}</strong></span>
            <span>评论 <strong>${num(comments)}</strong><span class="muted"> · 目标 ${num(params.max_comments || 0)} / 篇</span></span>
            <div class="task-card-progress">
              <div class="progress" role="progressbar" aria-label="笔记进度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}"><span style="width:${pct}%"></span></div>
              <span>${pct}%</span>
            </div>
          </div>
        </article>
      `;
    }).join("");
  }

  function renderTaskDetail(task) {
    const title = taskTitle(task);
    const params = parseParams(task);
    const prog = progressData(task);
    const notes = Number(task.notes_count ?? prog.notes_count ?? 0);
    const comments = Number(task.comments_count ?? prog.comments_count ?? 0);
    const updated = prog.updated_at || task.heartbeat_at || task.completed_at || task.started_at || task.created_at;
    $("taskDetailTitle").textContent = title;
    $("taskDetailStatus").textContent = `${statusText(task.status)} · #${task.id}`;
    $("taskDetailBody").innerHTML = `
      <div class="detail-grid">
        <div class="detail-item"><div class="detail-label">执行方式</div><div class="detail-value">${escapeHtml(providerLabel(taskProvider(task)))}</div></div>
        <div class="detail-item"><div class="detail-label">任务类型</div><div class="detail-value">${escapeHtml(task.task_type || "-")}</div></div>
        <div class="detail-item"><div class="detail-label">笔记数量</div><div class="detail-value">${num(notes)}</div></div>
        <div class="detail-item"><div class="detail-label">评论数量</div><div class="detail-value">${num(comments)}</div></div>
        <div class="detail-item"><div class="detail-label">创建时间</div><div class="detail-value">${escapeHtml(fmt(task.created_at))}</div></div>
        <div class="detail-item"><div class="detail-label">最近更新</div><div class="detail-value">${escapeHtml(fmt(updated))}</div></div>
      </div>
      <div class="field mt-md"><div class="label">最近消息</div><div class="detail-item">${escapeHtml(prog.message || task.progress || task.error || "暂无消息")}</div></div>
      <div class="field mt-md"><div class="label">任务参数</div><pre class="detail-item mono small-text" style="white-space:pre-wrap;margin:0">${escapeHtml(JSON.stringify(params, null, 2))}</pre></div>
    `;
  }

  function renderAll() {
    renderServiceStatus();
    renderSummary();
    renderAccounts();
    renderCandidates();
    renderTasks();
    renderProviderPicker();
  }

  async function refreshAll() {
    if (state.refreshing) return;
    state.refreshing = true;
    $("refreshBtn").disabled = true;
    try {
      const [status, tasks, accounts, candidates] = await Promise.all([
        json("/api/status"),
        json("/api/tasks"),
        json("/api/accounts"),
        json("/api/accounts/candidates"),
      ]);
      state.status = status;
      state.tasks = tasks;
      const existingIds = new Set(tasks.map(task => Number(task.id)));
      state.selectedTaskIds.forEach(id => { if (!existingIds.has(id)) state.selectedTaskIds.delete(id); });
      state.accounts = accounts;
      state.candidates = candidates;
      $("apiError").classList.add("hidden");
      renderAll();
    } catch (error) {
      setServiceStatus("连接异常", "error");
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
    taskDrawerReturnFocus = document.activeElement;
    renderTasks();
    renderTaskDetail(task);
    $("taskDetailDrawer").classList.add("open");
    window.setTimeout(() => $("closeTaskDetailBtn").focus(), 0);
  }

  function closeTaskDetail() {
    $("taskDetailDrawer").classList.remove("open");
    const focusTarget = taskDrawerReturnFocus?.isConnected
      ? taskDrawerReturnFocus
      : $("taskRows").querySelector(`[data-task-id="${state.selectedTaskId}"]`);
    focusTarget?.focus();
    taskDrawerReturnFocus = null;
  }

  async function submitJson(path, payload) {
    const result = await json(path, { method: "POST", headers: headers(), body: JSON.stringify(payload) });
    await refreshAll();
    showToast(result.message || "提交成功");
  }

  async function submitTask(path, payload) {
    try {
      await submitJson(path, payload);
      closeModal("createTaskModal");
    } catch (error) {
      showToast(`任务提交失败：${error.message || error}`, "error");
    }
  }

  function formData(form) {
    const data = new FormData(form);
    return Object.fromEntries(data.entries());
  }

  function lines(value) {
    return String(value || "").split(/\r?\n/).map(v => v.trim()).filter(Boolean);
  }

  function providerPayload() {
    const provider = state.taskProvider;
    if (provider !== "justoneapi") return { provider };
    const maxPages = Math.min(100, Math.max(1, Math.trunc(Number($("justoneMaxPages").value) || 3)));
    const maxRequests = Math.min(1000, Math.max(1, Math.trunc(Number($("justoneMaxRequests").value) || 20)));
    $("justoneMaxPages").value = maxPages;
    $("justoneMaxRequests").value = maxRequests;
    return {
      provider,
      provider_options: {
        include_details: $("justoneIncludeDetails").checked,
        include_comments: $("justoneIncludeComments").checked,
        include_replies: $("justoneIncludeReplies").checked,
        max_pages: maxPages,
        max_requests: maxRequests,
        note_type: $("justoneNoteType").value,
        time_filter: $("justoneTimeFilter").value,
      },
    };
  }

  function renderTaskForm() {
    const activeKey = `${state.taskType}-${state.taskMode}`;
    document.querySelectorAll("[data-task-type]").forEach(tab => {
      tab.classList.toggle("active", tab.dataset.taskType === state.taskType);
      tab.setAttribute("aria-selected", String(tab.dataset.taskType === state.taskType));
    });
    document.querySelectorAll("[data-task-mode]").forEach(tab => {
      tab.classList.toggle("active", tab.dataset.taskMode === state.taskMode);
      tab.setAttribute("aria-selected", String(tab.dataset.taskMode === state.taskMode));
    });
    renderProviderPicker();
    document.querySelectorAll("[data-task-form]").forEach(form => {
      form.classList.toggle("hidden", form.dataset.taskForm !== activeKey);
    });
  }

  function applyProviderSearchDefaults(provider) {
    const sortType = provider === "justoneapi" ? "general" : "popularity_descending";
    document.querySelectorAll('[data-task-form^="search-"] select[name="sort_type"]').forEach(select => {
      select.value = sortType;
    });
  }

  function openModal(id) {
    const modal = $(id);
    if (!modal) return;
    modalReturnFocus = document.activeElement;
    modal.classList.add("open");
    const focusable = modal.querySelector("button, input, select, textarea");
    if (focusable) window.setTimeout(() => focusable.focus(), 0);
  }
  function closeModal(id) {
    const modal = $(id);
    if (modal) modal.classList.remove("open");
    if (modalReturnFocus && typeof modalReturnFocus.focus === "function") modalReturnFocus.focus();
    modalReturnFocus = null;
  }

  function trapFocus(container, event) {
    if (!container || event.key !== "Tab") return;
    const items = [...container.querySelectorAll("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex=\"-1\"])")]
      .filter(item => item.getClientRects().length > 0 && getComputedStyle(item).visibility !== "hidden");
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  async function copyText(text) {
    if (!text) return showToast("没有可复制的内容", "warn");
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const input = document.createElement("textarea");
      input.value = text;
      input.style.position = "fixed";
      input.style.left = "-9999px";
      document.body.appendChild(input);
      input.focus();
      input.select();
      document.execCommand("copy");
      input.remove();
    }
    showToast("已复制");
  }

  function candidateCopyText(candidate, kind) {
    if (kind === "login") {
      return [
        `手机号：${candidate.phone || ""}`,
        `密码：${candidate.password || ""}`,
        `昵称：${candidate.nickname || ""}`,
        `用户ID：${candidate.user_id || ""}`,
        `短信链接：${candidate.sms_link || ""}`,
        `辅助链接：${candidate.fm_link || ""}`,
      ].join("\n");
    }
    if (kind === "sms") return candidate.sms_link || "";
    if (kind === "fm") return candidate.fm_link || "";
    if (kind === "cookie") return candidate.cookie_json || "";
    return "";
  }

  async function closeQr() {
    state.qrGeneration += 1;
    if (state.qrTimer) clearTimeout(state.qrTimer);
    state.qrTimer = null;
    const sessionId = state.qrSessionId;
    state.qrSessionId = "";
    state.qrStarting = false;
    $("startQrBtn").disabled = false;
    $("qrImage").classList.add("hidden");
    $("qrImage").removeAttribute("src");
    $("qrMessage").textContent = "生成后请扫码确认登录";
    closeModal("qrModal");
    if (sessionId) await json(`/api/accounts/qrcode/${sessionId}`, { method: "DELETE" }).catch(() => null);
  }

  async function pollQr() {
    if (!state.qrSessionId || state.qrPolling === state.qrSessionId) return;
    const sessionId = state.qrSessionId;
    state.qrPolling = sessionId;
    try {
      const result = await json(`/api/accounts/qrcode/${sessionId}/poll`);
      if (sessionId !== state.qrSessionId) return;
      $("qrMessage").textContent = result.message || "等待扫码确认";
      if (result.status === "success") {
        state.qrSessionId = "";
        await refreshAll();
        const generation = state.qrGeneration;
        setTimeout(() => {
          if (generation === state.qrGeneration && !state.qrSessionId) closeQr();
        }, 800);
      }
    } catch (error) {
      if (sessionId !== state.qrSessionId) return;
      $("qrMessage").textContent = `登录检查失败：${error.message || error}`;
      if (error.status === 400 || error.status === 404) {
        state.qrSessionId = "";
        $("startQrBtn").disabled = false;
        $("qrImage").classList.add("hidden");
        $("qrImage").removeAttribute("src");
        await json(`/api/accounts/qrcode/${sessionId}`, { method: "DELETE" }).catch(() => null);
      }
    } finally {
      if (state.qrPolling === sessionId) state.qrPolling = "";
      if (sessionId === state.qrSessionId) state.qrTimer = setTimeout(pollQr, 3000);
    }
  }

  function bindEvents() {
    document.querySelectorAll("label:not([for])").forEach(label => {
      const control = label.querySelector("input, select, textarea") || label.parentElement?.querySelector("input, select, textarea");
      if (!control) return;
      if (!control.id) control.id = `field-${Math.random().toString(36).slice(2, 9)}`;
      label.htmlFor = control.id;
    });
    $("refreshBtn").addEventListener("click", refreshAll);
    $("openCreateBtn").addEventListener("click", () => openModal("createTaskModal"));
    $("taskStatusFilter").addEventListener("change", renderTasks);
    $("selectVisibleTasks").addEventListener("change", event => {
      filteredTasks().forEach(task => {
        const id = Number(task.id);
        if (event.target.checked) state.selectedTaskIds.add(id);
        else state.selectedTaskIds.delete(id);
      });
      renderTasks();
    });
    $("taskRows").addEventListener("change", event => {
      const checkbox = event.target.closest("[data-select-task-id]");
      if (!checkbox) return;
      const id = Number(checkbox.dataset.selectTaskId);
      if (checkbox.checked) state.selectedTaskIds.add(id);
      else state.selectedTaskIds.delete(id);
      renderTasks();
      $("taskRows").querySelector(`[data-select-task-id="${id}"]`)?.focus();
    });
    $("exportBtn").addEventListener("click", async () => {
      const taskIds = [...state.selectedTaskIds].sort((a, b) => a - b);
      if (!taskIds.length) return;
      try {
        const response = await api("/api/export/tasks", {
          method: "POST", headers: headers(), body: JSON.stringify({ task_ids: taskIds }),
        });
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "xhs_selected_tasks.xlsx";
        a.click();
        URL.revokeObjectURL(url);
      } catch (error) {
        showToast(`导出失败：${error.message || error}`, "error");
      }
    });
    $("deleteTasksBtn").addEventListener("click", async () => {
      const taskIds = [...state.selectedTaskIds].sort((a, b) => a - b);
      if (!taskIds.length || !confirm(`删除选中的 ${taskIds.length} 个任务？采集内容会保留。`)) return;
      try {
        const result = await json("/api/tasks", {
          method: "DELETE", headers: headers(), body: JSON.stringify({ task_ids: taskIds }),
        });
        state.selectedTaskIds.clear();
        await refreshAll();
        showToast(result.message || `已删除 ${taskIds.length} 个任务`);
      } catch (error) {
        showToast(`删除失败：${error.message || error}`, "error");
      }
    });
    document.querySelectorAll("[data-task-type]").forEach(tab => {
      tab.addEventListener("click", () => {
        state.taskType = tab.dataset.taskType;
        renderTaskForm();
      });
      tab.addEventListener("keydown", event => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        const tabs = [...document.querySelectorAll("[data-task-type]")];
        const index = tabs.indexOf(tab);
        const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        event.preventDefault(); tabs[next].focus(); tabs[next].click();
      });
    });
    document.querySelectorAll("[data-task-mode]").forEach(tab => {
      tab.addEventListener("click", () => {
        state.taskMode = tab.dataset.taskMode;
        renderTaskForm();
      });
      tab.addEventListener("keydown", event => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        const tabs = [...document.querySelectorAll("[data-task-mode]")];
        const index = tabs.indexOf(tab);
        const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        event.preventDefault(); tabs[next].focus(); tabs[next].click();
      });
    });
    document.querySelectorAll("[data-task-provider]").forEach(tab => {
      tab.addEventListener("click", () => {
        const provider = tab.dataset.taskProvider;
        if (provider !== state.taskProvider) applyProviderSearchDefaults(provider);
        state.taskProvider = provider;
        renderTaskForm();
      });
      tab.addEventListener("keydown", event => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End", " ", "Enter"].includes(event.key)) return;
        const tabs = [...document.querySelectorAll("[data-task-provider]")];
        if ([" ", "Enter"].includes(event.key)) { event.preventDefault(); tab.click(); return; }
        const index = tabs.indexOf(tab);
        const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        event.preventDefault(); tabs[next].focus(); tabs[next].click();
      });
    });
    $("justoneIncludeComments").addEventListener("change", event => {
      const enabled = event.target.checked;
      $("justoneIncludeReplies").disabled = !enabled;
      if (!enabled) $("justoneIncludeReplies").checked = false;
    });
    $("taskRows").addEventListener("click", async event => {
      if (event.target.closest("[data-select-task-id]")) return;
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
        showToast(`操作失败：${error.message || error}`, "error");
      }
    });
    $("taskRows").addEventListener("keydown", event => {
      if (!(["Enter", " "].includes(event.key))) return;
      const row = event.target.closest("[data-task-id]");
      if (!row || event.target.closest("button, input, select, textarea")) return;
      event.preventDefault();
      selectTask(row.dataset.taskId);
    });
    $("closeTaskDetailBtn").addEventListener("click", closeTaskDetail);
    $("taskDetailDrawer").addEventListener("click", event => {
      if (event.target === $("taskDetailDrawer")) closeTaskDetail();
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
    $("candidateBtn").addEventListener("click", async () => {
      await refreshAll();
      openModal("candidateModal");
    });
    $("reloadCandidatesBtn").addEventListener("click", refreshAll);
    $("candidateList").addEventListener("click", async event => {
      const copyBtn = event.target.closest("[data-candidate-copy]");
      const deleteBtn = event.target.closest("[data-candidate-delete]");
      if (copyBtn) {
        const candidate = state.candidates.find(c => Number(c.id) === Number(copyBtn.dataset.candidateId));
        if (!candidate) return;
        await copyText(candidateCopyText(candidate, copyBtn.dataset.candidateCopy));
      }
      if (deleteBtn && confirm(`确认删除候选账号 #${deleteBtn.dataset.candidateDelete}？`)) {
        await json(`/api/accounts/candidates/${deleteBtn.dataset.candidateDelete}`, { method: "DELETE" });
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
      if (!cookie) return showToast("请粘贴 Cookie", "warn");
      try {
        if (state.cookieAccountId) {
          await json(`/api/accounts/${state.cookieAccountId}/cookie`, { method: "POST", headers: headers(), body: JSON.stringify({ cookie }) });
        } else {
          if (!name) return showToast("请填写账号备注", "warn");
          await json("/api/accounts", { method: "POST", headers: headers(), body: JSON.stringify({ name, cookie }) });
        }
        closeModal("cookieModal");
        await refreshAll();
      } catch (error) {
        showToast(`保存失败：${error.message || error}`, "error");
      }
    });
    $("healthBtn").addEventListener("click", async () => {
      try {
        const result = await json("/api/accounts/health_check", { method: "POST" });
        await refreshAll();
        showToast(result.message || "健康检查完成");
      } catch (error) {
        showToast(`健康检查失败：${error.message || error}`, "error");
      }
    });
    $("qrBtn").addEventListener("click", () => openModal("qrModal"));
    $("startQrBtn").addEventListener("click", async () => {
      if (state.qrStarting || state.qrSessionId) return;
      state.qrStarting = true;
      $("startQrBtn").disabled = true;
      $("qrImage").classList.add("hidden");
      $("qrImage").removeAttribute("src");
      const generation = state.qrGeneration;
      try {
        $("qrMessage").textContent = "正在启动浏览器并生成二维码...";
        const name = $("qrAccountName").value.trim() || `account-${Date.now()}`;
        const result = await json("/api/accounts/qrcode/start", { method: "POST", headers: headers(), body: JSON.stringify({ name }) });
        if (generation !== state.qrGeneration) {
          await json(`/api/accounts/qrcode/${result.session_id}`, { method: "DELETE" }).catch(() => null);
          return;
        }
        state.qrSessionId = result.session_id;
        $("qrImage").src = result.qrcode;
        $("qrImage").classList.remove("hidden");
        $("qrMessage").textContent = "请扫码登录，登录成功后会自动加入账号池。";
        state.qrTimer = setTimeout(pollQr, 3000);
      } catch (error) {
        if (generation === state.qrGeneration) $("qrMessage").textContent = `二维码启动失败：${error.message || error}`;
      } finally {
        if (generation === state.qrGeneration) {
          state.qrStarting = false;
          if (!state.qrSessionId) $("startQrBtn").disabled = false;
        }
      }
    });
    $("closeQrBtn").addEventListener("click", closeQr);
    document.querySelectorAll("[data-close]").forEach(btn => btn.addEventListener("click", () => closeModal(btn.dataset.close)));
    document.querySelectorAll(".modal").forEach(modal => modal.addEventListener("click", event => {
      if (event.target === modal) modal.id === "qrModal" ? closeQr() : closeModal(modal.id);
    }));
    document.addEventListener("keydown", event => {
      const openModalElement = document.querySelector(".modal.open");
      if (openModalElement) {
        trapFocus(openModalElement, event);
        if (event.key === "Escape") return openModalElement.id === "qrModal" ? closeQr() : closeModal(openModalElement.id);
        return;
      }
      if (event.key === "Tab" && $("taskDetailDrawer").classList.contains("open")) return trapFocus($("taskDetailDrawer"), event);
      if (event.key === "Escape" && $("taskDetailDrawer").classList.contains("open")) closeTaskDetail();
    });

    $("searchSingleForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      await submitTask("/api/tasks/search", {
        ...providerPayload(),
        keyword: data.keyword.trim(),
        max_notes: Number(data.max_notes),
        max_comments: Number(data.max_comments),
        sort_type: data.sort_type,
        ...(state.taskProvider === "local" ? { days_limit: Number(data.days_limit) } : {}),
        force: Boolean(data.force),
      });
    });
    $("searchBatchForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      const keywords = lines(data.keywords);
      if (!keywords.length) return showToast("请输入至少一个关键词", "warn");
      await submitTask("/api/tasks/batch_search", {
        ...providerPayload(),
        keywords,
        max_notes: Number(data.max_notes),
        max_comments: Number(data.max_comments),
        sort_type: data.sort_type,
        ...(state.taskProvider === "local" ? { days_limit: Number(data.days_limit) } : {}),
      });
    });
    $("creatorSingleForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      await submitTask("/api/tasks/creator", {
        ...providerPayload(),
        creator_input: data.creator_input.trim(),
        max_notes: Number(data.max_notes),
        force: Boolean(data.force),
      });
    });
    $("creatorBatchForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      const creator_urls = lines(data.creator_urls);
      if (!creator_urls.length) return showToast("请输入至少一个博主主页或用户 ID", "warn");
      await submitTask("/api/tasks/batch_creator", {
        ...providerPayload(),
        creator_urls,
        max_notes: Number(data.max_notes),
      });
    });
    $("noteSingleForm").addEventListener("submit", async event => {
      event.preventDefault();
      const data = formData(event.target);
      const note_input = String(data.note_input || "").trim();
      if (!note_input) return showToast("请输入笔记链接或 ID", "warn");
      await submitTask("/api/tasks/note", {
        ...providerPayload(),
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
      if (!notes.length) return showToast("请输入至少一个笔记链接或 ID", "warn");
      await submitTask("/api/tasks/note", { ...providerPayload(), notes });
    });
  }

  bindEvents();
  renderTaskForm();
  refreshAll();
  setInterval(refreshAll, 10000);
})();

