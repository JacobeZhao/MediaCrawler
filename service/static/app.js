(() => {
  const state = {
    status: {},
    tasks: [],
    accounts: [],
    candidates: [],
    proxies: [],
    proxyError: "",
    selectedTaskId: null,
    taskType: "search",
    taskMode: "single",
    taskProvider: "local",
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
    return s === "ready" || s === "active";
  }

  function activeProxies() {
    return state.proxies.filter(proxy => proxy.status !== "inactive");
  }

  function proxyName(proxyId) {
    if (!proxyId) return "未绑定代理";
    const proxy = state.proxies.find(p => Number(p.id) === Number(proxyId));
    return proxy ? `${proxy.name || `代理 ${proxy.id}`} (#${proxy.id})` : `代理 #${proxyId}`;
  }

  function proxyOptions(selectedId, allowEmptyLabel = "不使用代理") {
    const selected = selectedId ? Number(selectedId) : "";
    const emptySelected = selected === "" ? " selected" : "";
    const options = activeProxies();
    if (selected && !options.some(proxy => Number(proxy.id) === selected)) {
      const current = state.proxies.find(proxy => Number(proxy.id) === selected);
      options.unshift(current || { id: selected, name: `代理 ${selected}`, masked_url: "当前绑定" });
    }
    return [
      `<option value=""${emptySelected}>${escapeHtml(allowEmptyLabel)}</option>`,
      ...options.map(proxy => {
        const isSelected = Number(proxy.id) === selected ? " selected" : "";
        return `<option value="${proxy.id}"${isSelected}>${escapeHtml(proxy.name || `代理 ${proxy.id}`)} · ${escapeHtml(proxy.masked_url || proxy.server || "")}</option>`;
      })
    ].join("");
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

  function renderTop() {
    const readyCount = state.accounts.filter(isAccountReady).length;
    const total = state.accounts.length;
    const providers = Object.values(state.status.providers || {});
    const providerReady = providers.some(detail => (
      detail === true || Boolean(detail && detail.ready === true)
    ));
    const serviceReady = state.status.status === "ready" || readyCount > 0 || providerReady;
    const limiter = state.status.rate_limiter || {};
    const penalties = Object.keys(limiter.active_penalties_sec || {}).length;
    $("servicePill").className = `pill ${serviceReady ? "ready" : "paused"}`;
    $("servicePill").textContent = serviceReady ? "服务可运行" : "等待可用来源";
    $("protectionPill").className = `pill ${penalties ? "paused" : "ready"}`;
    $("protectionPill").textContent = penalties ? `保护退避 ${penalties}` : "保护开启";
    $("queueSize").textContent = state.status.queue_size ?? 0;
    $("readyAccounts").textContent = readyCount;
    $("totalAccounts").textContent = total;
    $("lastRefresh").textContent = `刷新 ${new Date().toLocaleTimeString()}`;
  }

  function renderProviderPicker() {
    const selected = state.taskProvider;
    document.querySelectorAll("[data-task-provider]").forEach(tab => {
      const active = tab.dataset.taskProvider === selected;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-checked", String(active));
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
    renderProxies();

    if (!state.accounts.length) {
      $("accountList").innerHTML = `<div class="empty">暂无账号</div>`;
      return;
    }
    $("accountList").innerHTML = state.accounts.map(account => {
      const runtime = accountRuntime(account);
      const cls = isAccountReady(account) ? "ready" : (runtime === "captcha" ? "captcha" : statusClass(runtime));
      const msg = account.message ? `<div class="small-text warn-text mt-xxs">${escapeHtml(compact(account.message, 90))}</div>` : "";
      const proxyText = account.proxy_name || proxyName(account.proxy_id);
      const proxyServer = account.proxy_server ? ` · ${escapeHtml(account.proxy_server)}` : "";
      return `
        <div class="account-item">
          <div class="row-between">
            <div class="truncate"><b>${escapeHtml(account.name || `账号 ${account.id}`)}</b></div>
            <span class="pill ${cls}">${escapeHtml(runtime)}</span>
          </div>
          <div class="small-text muted mono truncate mt-xs">${escapeHtml(account.cookie_preview || "")}</div>
          <div class="small-text muted mt-xs">ID ${account.id} · 验证码 ${account.captcha_count ?? 0} · 检查 ${fmt(account.last_checked)}</div>
          <div class="small-text muted mt-xs truncate">代理：${escapeHtml(proxyText)}${proxyServer}</div>
          ${msg}
          <div class="proxy-bind-row mt-sm">
            <select class="select small-select" data-account-proxy-select="${account.id}">
              ${proxyOptions(account.proxy_id)}
            </select>
            <button class="btn ghost small" data-proxy-save="${account.id}">绑定并重启</button>
            <button class="btn ghost small" data-proxy-clear="${account.id}">解绑并重启</button>
          </div>
          <div class="row mt-md">
            <button class="btn ghost small" data-cookie-id="${account.id}">替换 Cookie</button>
            <button class="btn danger small" data-delete-id="${account.id}">删除</button>
          </div>
        </div>
      `;
    }).join("");
  }

  function renderProxies() {
    if (!$("proxyList")) return;
    $("proxyCount").textContent = state.proxies.length;
    if (state.proxyError) {
      $("proxyList").innerHTML = `<div class="empty">代理接口异常：${escapeHtml(state.proxyError)}</div>`;
      return;
    }
    if (!state.proxies.length) {
      $("proxyList").innerHTML = `<div class="empty">暂无代理配置</div>`;
      return;
    }
    $("proxyList").innerHTML = state.proxies.map(proxy => {
      const status = proxy.status || "active";
      const cls = status === "active" ? "ready" : "paused";
      const error = proxy.last_error ? `<div class="small-text warn-text mt-xxs truncate">${escapeHtml(compact(proxy.last_error, 90))}</div>` : "";
      return `
        <div class="proxy-item">
          <div class="row-between">
            <div class="truncate"><b>${escapeHtml(proxy.name || `代理 ${proxy.id}`)}</b></div>
            <span class="pill ${cls}">${escapeHtml(status)}</span>
          </div>
          <div class="small-text muted mono truncate mt-xs">${escapeHtml(proxy.masked_url || proxy.server || "-")}</div>
          <div class="small-text muted mt-xs">ID ${proxy.id} · ${escapeHtml(proxy.proxy_type || "http")} · 检测 ${fmt(proxy.last_checked)}</div>
          ${error}
          <div class="row mt-sm">
            <button class="btn ghost small" data-proxy-check="${proxy.id}">检测代理</button>
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
            <div class="candidate-field"><div class="label">密码</div><div class="value mono">${escapeHtml(candidate.password || "-")}</div></div>
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
    const keyword = $("taskKeywordFilter").value.trim().toLowerCase();
    return state.tasks.filter(task => {
      if (status && task.status !== status) return false;
      if (!keyword) return true;
      return `${taskTitle(task)} ${providerLabel(taskProvider(task))} ${task.progress || ""} ${task.error || ""}`.toLowerCase().includes(keyword);
    });
  }

  function renderTasks() {
    const rows = filteredTasks();
    if (!rows.length) {
      $("taskRows").innerHTML = `<tr><td colspan="8"><div class="empty">没有匹配的任务</div></td></tr>`;
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
      const provider = taskProvider(task);
      return `
        <tr class="task-row${selected}" data-task-id="${task.id}">
          <td class="mono muted">#${task.id}</td>
          <td>
            <div class="truncate strong">${escapeHtml(taskTitle(task))}</div>
            <div class="small-text muted">${escapeHtml(task.task_type || "-")} · 创建 ${fmt(task.created_at)}</div>
          </td>
          <td><span class="provider-badge ${provider === "justoneapi" ? "api" : "local"}">${providerLabel(provider)}</span></td>
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
    renderCandidates();
    renderTasks();
    renderProviderPicker();
    refreshProxySelects();
  }

  async function refreshAll() {
    if (state.refreshing) return;
    state.refreshing = true;
    $("refreshBtn").disabled = true;
    try {
      const [status, tasks, accounts, candidates, proxiesResult] = await Promise.all([
        json("/api/status"),
        json("/api/tasks"),
        json("/api/accounts"),
        json("/api/accounts/candidates"),
        json("/api/proxies")
          .then(proxies => ({ proxies, error: "" }))
          .catch(error => ({ proxies: [], error: error.message || String(error) })),
      ]);
      state.status = status;
      state.tasks = tasks;
      state.accounts = accounts;
      state.candidates = candidates;
      state.proxies = Array.isArray(proxiesResult.proxies) ? proxiesResult.proxies : [];
      state.proxyError = proxiesResult.error;
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
    });
    document.querySelectorAll("[data-task-mode]").forEach(tab => {
      tab.classList.toggle("active", tab.dataset.taskMode === state.taskMode);
    });
    renderProviderPicker();
    document.querySelectorAll("[data-task-form]").forEach(form => {
      form.classList.toggle("hidden", form.dataset.taskForm !== activeKey);
    });
  }

  function refreshProxySelects() {
    if ($("cookieProxy")) $("cookieProxy").innerHTML = proxyOptions($("cookieProxy").value);
    if ($("qrProxy")) $("qrProxy").innerHTML = proxyOptions($("qrProxy").value);
  }

  function openModal(id) { $(id).classList.add("open"); }
  function closeModal(id) { $(id).classList.remove("open"); }

  async function copyText(text) {
    if (!text) return alert("没有可复制的内容");
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
    alert("已复制");
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
    document.querySelectorAll("[data-task-provider]").forEach(tab => {
      tab.addEventListener("click", () => {
        state.taskProvider = tab.dataset.taskProvider;
        renderTaskForm();
      });
    });
    $("justoneIncludeComments").addEventListener("change", event => {
      const enabled = event.target.checked;
      $("justoneIncludeReplies").disabled = !enabled;
      if (!enabled) $("justoneIncludeReplies").checked = false;
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
      const proxySaveBtn = event.target.closest("[data-proxy-save]");
      const proxyClearBtn = event.target.closest("[data-proxy-clear]");
      if (cookieBtn) {
        const account = state.accounts.find(a => Number(a.id) === Number(cookieBtn.dataset.cookieId));
        state.cookieAccountId = account.id;
        $("cookieModalTitle").textContent = `替换 Cookie：${account.name}`;
        $("accountName").value = account.name || "";
        $("accountName").disabled = true;
        $("accountCookie").value = "";
        $("cookieProxy").value = account.proxy_id || "";
        openModal("cookieModal");
      }
      if (proxySaveBtn) {
        const accountId = proxySaveBtn.dataset.proxySave;
        const select = document.querySelector(`[data-account-proxy-select="${accountId}"]`);
        const proxyId = select && select.value ? Number(select.value) : null;
        await json(`/api/accounts/${accountId}/proxy`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ proxy_id: proxyId, restart: true }),
        });
        await refreshAll();
      }
      if (proxyClearBtn && confirm(`确认解绑账号 #${proxyClearBtn.dataset.proxyClear} 的代理并重启？`)) {
        await json(`/api/accounts/${proxyClearBtn.dataset.proxyClear}/proxy`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ proxy_id: null, restart: true }),
        });
        await refreshAll();
      }
      if (deleteBtn && confirm(`确认删除账号 #${deleteBtn.dataset.deleteId}？`)) {
        await json(`/api/accounts/${deleteBtn.dataset.deleteId}`, { method: "DELETE" });
        await refreshAll();
      }
    });
    $("proxyConfigBtn").addEventListener("click", () => openModal("proxyModal"));
    $("addProxyBtn").addEventListener("click", () => openModal("proxyModal"));
    $("proxyList").addEventListener("click", async event => {
      const checkBtn = event.target.closest("[data-proxy-check]");
      if (!checkBtn) return;
      try {
        const result = await json(`/api/proxies/${checkBtn.dataset.proxyCheck}/check`, { method: "POST" });
        await refreshAll();
        alert(`${result.message || "检测完成"}${result.observed_ip ? `\n出口 IP：${result.observed_ip}` : ""}${result.error ? `\n${result.error}` : ""}`);
      } catch (error) {
        alert(`检测失败：${error.message || error}`);
      }
    });
    $("saveProxyBtn").addEventListener("click", async () => {
      const name = $("proxyName").value.trim();
      const server = $("proxyServer").value.trim();
      if (!name) return alert("请填写代理名称");
      if (!server) return alert("请填写代理服务器");
      try {
        await json("/api/proxies", {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({
            name,
            proxy_type: $("proxyType").value,
            server,
            username: $("proxyUsername").value.trim(),
            password: $("proxyPassword").value,
            status: $("proxyStatus").value,
          }),
        });
        $("proxyName").value = "";
        $("proxyServer").value = "";
        $("proxyUsername").value = "";
        $("proxyPassword").value = "";
        closeModal("proxyModal");
        await refreshAll();
      } catch (error) {
        alert(`保存代理失败：${error.message || error}`);
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
      $("cookieProxy").value = "";
      openModal("cookieModal");
    });
    $("saveCookieBtn").addEventListener("click", async () => {
      const cookie = $("accountCookie").value.trim();
      const name = $("accountName").value.trim();
      if (!cookie) return alert("请粘贴 Cookie");
      try {
        const proxy_id = $("cookieProxy").value ? Number($("cookieProxy").value) : null;
        if (state.cookieAccountId) {
          await json(`/api/accounts/${state.cookieAccountId}/cookie`, { method: "POST", headers: headers(), body: JSON.stringify({ cookie }) });
          await json(`/api/accounts/${state.cookieAccountId}/proxy`, { method: "POST", headers: headers(), body: JSON.stringify({ proxy_id, restart: true }) });
        } else {
          if (!name) return alert("请填写账号备注");
          await json("/api/accounts", { method: "POST", headers: headers(), body: JSON.stringify({ name, cookie, proxy_id }) });
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
        const proxy_id = $("qrProxy").value ? Number($("qrProxy").value) : null;
        const result = await json("/api/accounts/qrcode/start", { method: "POST", headers: headers(), body: JSON.stringify({ name, proxy_id }) });
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
      if (!keywords.length) return alert("请输入至少一个关键词");
      await submitJson("/api/tasks/batch_search", {
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
      await submitJson("/api/tasks/creator", {
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
      if (!creator_urls.length) return alert("请输入至少一个博主主页或用户 ID");
      await submitJson("/api/tasks/batch_creator", {
        ...providerPayload(),
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
      if (!notes.length) return alert("请输入至少一个笔记链接或 ID");
      await submitJson("/api/tasks/note", { ...providerPayload(), notes });
    });
  }

  bindEvents();
  renderTaskForm();
  refreshProxySelects();
  refreshAll();
  setInterval(refreshAll, 10000);
})();

