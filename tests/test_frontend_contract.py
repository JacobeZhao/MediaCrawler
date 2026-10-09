import ast
from collections import Counter
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "service" / "static"
ROUTES_DIR = ROOT / "service" / "routes"

EXPECTED_JS_IDS = {
    "accountCookie", "accountList", "accountName",
    "accountHealthDetail", "accountHealthValue",
    "apiError", "candidateBtn",
    "candidateList", "closeQrBtn", "closeTaskDetailBtn", "cookieModalTitle",
    "creatorBatchForm", "creatorSingleForm", "deleteTasksBtn", "exportBtn",
    "healthBtn", "justoneApiOptions", "justoneIncludeComments",
    "justoneIncludeDetails", "justoneIncludeReplies", "justoneMaxPages",
    "justoneMaxRequests", "justoneNoteType", "justoneTimeFilter",
    "noteBatchForm", "noteSingleForm", "openCookieBtn", "openCreateBtn",
    "providerReadiness", "qrAccountName", "qrBtn", "qrImage", "qrMessage",
    "refreshBtn", "selectVisibleTasks", "selectionCount", "serviceStatus", "serviceStatusText",
    "taskCompletedValue", "taskCompletionValue", "taskTotalValue",
    "reloadCandidatesBtn", "saveCookieBtn", "searchBatchForm",
    "searchSingleForm", "startQrBtn", "taskDetailBody",
    "taskDetailDrawer", "taskDetailStatus", "taskDetailTitle",
    "taskRows", "taskStatusFilter", "toastRegion",
}

EXPECTED_FRONTEND_ENDPOINTS = {
    ("GET", "/api/status"),
    ("GET", "/api/tasks"),
    ("GET", "/api/accounts"),
    ("GET", "/api/accounts/candidates"),
    ("GET", "/api/accounts/qrcode/{param}/poll"),
    ("POST", "/api/export/tasks"),
    ("DELETE", "/api/tasks"),
    ("DELETE", "/api/accounts/qrcode/{param}"),
    ("DELETE", "/api/accounts/{param}"),
    ("DELETE", "/api/accounts/candidates/{param}"),
    ("POST", "/api/tasks/{param}/resume"),
    ("POST", "/api/tasks/{param}/recrawl"),
    ("POST", "/api/accounts/{param}/cookie"),
    ("POST", "/api/accounts"),
    ("POST", "/api/accounts/health_check"),
    ("POST", "/api/accounts/qrcode/start"),
    ("POST", "/api/tasks/search"),
    ("POST", "/api/tasks/batch_search"),
    ("POST", "/api/tasks/creator"),
    ("POST", "/api/tasks/batch_creator"),
    ("POST", "/api/tasks/note"),
}

EXPECTED_STATE_CLASSES = {
    "active", "captcha", "completed", "deleted", "error", "failed",
    "hidden", "invalid", "open", "paused", "pending", "ready", "running",
    "selected", "toast", "warn",
}

EXPECTED_FRONTEND_CALLS = {
    "api": {"delegation": 1, "endpoint": 1},
    "json": {"delegation": 1, "endpoint": 15},
    "submitJson": {"delegation": 1, "endpoint": 2},
    "submitTask": {"endpoint": 6},
}

ALLOWED_DELEGATIONS = {
    ("api", "api(path, options)"),
    (
        "json",
        'json(path, { method: "POST", headers: headers(), body: JSON.stringify(payload) })',
    ),
    ("submitJson", "submitJson(path, payload)"),
}


class _Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.classes = set()
        self.hrefs = []
        self.srcs = []
        self.references = []
        self.data_values = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if value := values.get("id"):
            self.ids.append(value)
        self.classes.update((values.get("class") or "").split())
        if value := values.get("href"):
            self.hrefs.append(value)
        if value := values.get("src"):
            self.srcs.append(value)
        if value := values.get("for"):
            self.references.append(value)
        for name in ("aria-labelledby", "aria-describedby", "aria-controls"):
            self.references.extend((values.get(name) or "").split())
        if value := values.get("data-close"):
            self.references.append(value)
        for name, value in attrs:
            if name.startswith("data-") and value is not None:
                self.data_values.setdefault(name, []).append(value)


def _normalize_path(path):
    path = path.split("?", 1)[0]
    normalized = []
    for segment in path.split("/"):
        if re.fullmatch(r"(?:\$\{[^{}]+\}|\{[^{}]+\})", segment):
            normalized.append("{param}")
        else:
            if re.search(r"(?:\$\{[^{}]+\}|\{[^{}]+\})", segment):
                raise AssertionError(f"mixed placeholder segment: {segment!r}")
            normalized.append(segment)
    return re.sub(r"/{2,}", "/", "/".join(normalized))


def _call_source(source, open_paren):
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = []
    quote = None
    escaped = False
    for index in range(open_paren, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
            if not stack:
                return source[open_paren:index + 1]
    raise AssertionError("unterminated JavaScript call")


def _source_location(source, offset, filename):
    line = source.count("\n", 0, offset) + 1
    line_start = source.rfind("\n", 0, offset) + 1
    return f"{filename}:{line}:{offset - line_start + 1}"


def _javascript_endpoints(source, filename="JavaScript"):
    pattern = re.compile(r"(?<![\w.$])(?P<helper>api|json|submitJson|submitTask)\s*\(")
    endpoints = set()
    calls = []
    for match in pattern.finditer(source):
        if re.search(r"(?:async\s+)?function\s+$", source[max(0, match.start() - 24):match.start()]):
            continue
        helper = match.group("helper")
        call = _call_source(source, match.end() - 1)
        call_source = helper + call
        literal = re.match(
            r"\(\s*(?P<quote>[\"`])(?P<path>/.*?)(?P=quote)",
            call,
        )
        location = _source_location(source, match.start(), filename)
        if literal is None:
            if (helper, call_source) not in ALLOWED_DELEGATIONS:
                raise AssertionError(
                    f"unexpected dynamic {helper} call at {location}: {call_source}"
                )
            calls.append((helper, "delegation", call_source, location))
            continue
        if helper in {"submitJson", "submitTask"}:
            method = "POST"
        else:
            method_match = re.search(r"\bmethod\s*:\s*[\"'](GET|POST|DELETE|PATCH)[\"']", call)
            method = method_match.group(1) if method_match else "GET"
        endpoint = (method, _normalize_path(literal.group("path")))
        endpoints.add(endpoint)
        calls.append((helper, "endpoint", endpoint, location))
    return endpoints, calls


def _route_endpoints():
    endpoints = set()
    for path in ROUTES_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        prefix = ""
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
                continue
            if value.func.id != "APIRouter":
                continue
            for keyword in value.keywords:
                if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                    prefix = keyword.value.value
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not decorator.args:
                    continue
                func = decorator.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "router"
                    and func.attr in {"get", "post", "delete", "patch", "put"}
                    and isinstance(decorator.args[0], ast.Constant)
                ):
                    continue
                endpoints.add(
                    (func.attr.upper(), _normalize_path(prefix + decorator.args[0].value))
                )
    return endpoints


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        cls.javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        cls.css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
        cls.markup = _Markup()
        cls.markup.feed(cls.html)

    def test_javascript_dom_id_manifest_is_unique_and_resolved(self):
        html_ids = set(self.markup.ids)
        self.assertEqual(len(self.markup.ids), len(html_ids))
        js_ids = set(
            re.findall(r"\$\(\s*[\"']([A-Za-z][A-Za-z0-9_-]*)[\"']\s*\)", self.javascript)
        )
        self.assertEqual(js_ids, EXPECTED_JS_IDS)
        self.assertLessEqual(js_ids, html_ids)
        self.assertLessEqual(set(self.markup.references), html_ids)

    def test_static_assets_and_task_control_domains_are_stable(self):
        self.assertEqual(self.markup.hrefs, [
            "/static/crawler-logo.svg?v=20261009-4",
            "/static/styles.css?v=20261009-7",
        ])
        self.assertEqual(self.markup.srcs, [
            "/static/crawler-logo.svg?v=20261009-4",
            "/static/app.js?v=20261009-8",
        ])
        self.assertIn('rel="icon" type="image/svg+xml"', self.html)
        self.assertIn('class="brand-logo"', self.html)
        self.assertTrue((STATIC_DIR / "crawler-logo.svg").is_file())
        self.assertEqual(set(self.markup.data_values["data-task-type"]), {"search", "creator", "note"})
        self.assertEqual(set(self.markup.data_values["data-task-mode"]), {"single", "batch"})
        self.assertEqual(set(self.markup.data_values["data-task-provider"]), {"local", "justoneapi"})
        self.assertEqual(
            set(self.markup.data_values["data-task-form"]),
            {"search-single", "search-batch", "creator-single", "creator-batch", "note-single", "note-batch"},
        )

    def test_account_pool_is_first_and_proxy_configuration_is_not_exposed(self):
        self.assertLess(
            self.html.index('class="panel account-panel"'),
            self.html.index('class="workspace-panel"'),
        )
        self.assertIn('grid-template-areas:"resources workspace"', self.css)
        self.assertIn('grid-template-areas:"resources" "workspace"', self.css)
        self.assertNotIn("代理", self.html)
        self.assertNotIn("/api/proxies", self.javascript)
        self.assertNotIn("/proxy`", self.javascript)

    def test_account_actions_and_headings_are_compact(self):
        for text in (
            "账号状态会直接影响队列是否继续执行",
            "实时展示每个任务的笔记数、评论数、目标和最近状态",
            "选择爬取方式后，可提交单个或批量任务",
        ):
            self.assertNotIn(text, self.html)
        self.assertIn('class="row account-actions"', self.html)
        self.assertIn("grid-template-columns:repeat(4,minmax(0,1fr))", self.css)
        self.assertIn('id="createTaskModal" role="dialog"', self.html)
        self.assertIn('id="selectVisibleTasks"', self.html)
        self.assertNotIn('class="grid-overview"', self.html)
        self.assertIn('id="deleteTasksBtn" disabled', self.html)
        self.assertIn('id="exportBtn" disabled', self.html)

    def test_summary_and_task_cards(self):
        self.assertIn('class="summary-strip"', self.html)
        self.assertLess(self.html.index('class="summary-strip"'), self.html.index('class="layout"'))
        self.assertNotIn('<h2 class="panel-title">账号池</h2>', self.html)
        self.assertIn('class="task-list" id="taskRows" role="list"', self.html)
        self.assertIn('class="workspace-panel" aria-label=', self.html)
        self.assertNotIn('id="taskListTitle"', self.html)
        self.assertNotIn('<table', self.html)
        self.assertIn('<article class="task-card', self.javascript)
        self.assertIn('role="listitem" data-task-id=', self.javascript)
        self.assertIn('data-select-task-id=', self.javascript)
        self.assertIn('data-view-id=', self.javascript)
        self.assertIn('data-resume-id=', self.javascript)
        self.assertIn('data-recrawl-id=', self.javascript)
        self.assertIn('.summary-strip{gap:10px;background:transparent;border:0', self.css)
        self.assertIn('.workspace-panel{background:var(--panel);border:1px solid var(--line);border-radius:6px', self.css)
        self.assertIn('.workspace-panel .panel-head{padding:14px 16px;border-bottom:1px solid var(--line-soft)}', self.css)
        self.assertIn('.task-list{display:grid;align-content:start;gap:0;flex:1;min-height:0;overflow:auto', self.css)
        self.assertIn('.task-card{min-width:0;padding:14px 0;border-bottom:1px solid var(--line-soft);background:transparent', self.css)
        self.assertLess(self.javascript.index('class="task-card-primary"'), self.javascript.index('class="task-card-secondary"'))
        self.assertIn('class="task-message"', self.javascript)
        self.assertIn('class="task-card-progress"', self.javascript)
        self.assertIn('.task-card-progress{display:flex;align-items:center;gap:8px;min-width:0}', self.css)
        self.assertIn('state.status.task_counts', self.javascript)
        self.assertIn('"crawling"', self.javascript)
        self.assertNotIn('s === "active"', self.javascript)

    def test_service_status_uses_provider_readiness_and_connection_errors(self):
        self.assertIn('id="serviceStatus" role="status" aria-live="polite"', self.html)
        self.assertIn('Object.values(status.providers || {}).some(provider => provider.ready)', self.javascript)
        self.assertLess(
            self.javascript.index('if (running || status.status === "crawling")'),
            self.javascript.index('if (providerReady && queued)'),
        )
        self.assertIn('setServiceStatus("连接异常", "error")', self.javascript)
        self.assertIn('renderServiceStatus();', self.javascript)
        self.assertIn('.top-actions .btn{width:104px}', self.css)
        self.assertIn('.task-card-actions .btn{width:64px;min-width:64px}', self.css)

    def test_task_toolbar_keeps_selection_and_status_filter_without_search(self):
        self.assertNotIn("taskKeywordFilter", self.html)
        self.assertNotIn("taskKeywordFilter", self.javascript)
        self.assertLess(self.html.index('id="exportBtn"'), self.html.index('id="deleteTasksBtn"'))
        self.assertLess(self.html.index('id="deleteTasksBtn"'), self.html.index('id="taskStatusFilter"'))
        self.assertIn('id="taskStatusFilter" aria-label="筛选任务状态"', self.html)
        self.assertIn('grid-template-columns:auto auto minmax(0,1fr) repeat(3,minmax(104px,1fr))', self.css)
        self.assertIn('.task-bulk #exportBtn{grid-column:4}', self.css)
        self.assertIn('.task-bulk #deleteTasksBtn{grid-column:5}', self.css)
        self.assertIn('.task-bulk .task-status-filter{grid-column:6}', self.css)
        self.assertIn('.task-bulk .btn,.task-bulk .task-status-filter{width:100%;min-width:0}', self.css)
        self.assertIn('@media (max-width:600px){', self.css)
        self.assertIn('.task-bulk{width:100%;grid-template-columns:repeat(3,minmax(0,1fr))', self.css)
        self.assertIn('.task-bulk .task-status-filter{font-size:12px;padding-left:5px;padding-right:5px}', self.css)
        self.assertIn('return state.tasks.filter(task => !status || task.status === status)', self.javascript)

    def test_frontend_api_manifest_is_implemented_by_routes(self):
        frontend, calls = _javascript_endpoints(self.javascript, "service/static/app.js")
        self.assertEqual(frontend, EXPECTED_FRONTEND_ENDPOINTS)
        self.assertLessEqual(EXPECTED_FRONTEND_ENDPOINTS, _route_endpoints())
        classifications = {
            helper: dict(Counter(kind for call_helper, kind, _, _ in calls if call_helper == helper))
            for helper in EXPECTED_FRONTEND_CALLS
        }
        self.assertEqual(classifications, EXPECTED_FRONTEND_CALLS)
        self.assertEqual(len(calls), 27)

    def test_frontend_api_parser_rejects_unclassified_calls_and_mixed_segments(self):
        with self.assertRaisesRegex(
            AssertionError,
            r"unexpected dynamic api call at mutation\.js:2:10",
        ):
            _javascript_endpoints("function demo(path) {\n  return api(path);\n}", "mutation.js")
        with self.assertRaisesRegex(AssertionError, "mixed placeholder segment"):
            _normalize_path("/api/accounts/account-${accountId}/proxy")
        with self.assertRaisesRegex(AssertionError, "mixed placeholder segment"):
            _normalize_path("/api/accounts/{account_id}.json")

    def test_dynamic_state_classes_have_styles(self):
        css = re.sub(r"/\*.*?\*/", "", self.css, flags=re.DOTALL)
        selectors = " ".join(re.findall(r"([^{}]+)\{", css))
        css_classes = set(re.findall(r"\.([A-Za-z_][A-Za-z0-9_-]*)", selectors))
        self.assertLessEqual(EXPECTED_STATE_CLASSES, css_classes)


if __name__ == "__main__":
    unittest.main()
