import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const startup = source.lastIndexOf("  bindEvents();");
assert(startup > 0);

function node() {
  const classes = new Set();
  const attributes = new Map();
  return {
    classList: {add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name)},
    listeners: {},
    addEventListener(name, callback) { this.listeners[name] = callback; },
    removeAttribute: name => attributes.delete(name),
    getAttribute: name => attributes.get(name),
    set src(value) { attributes.set("src", value); },
    get src() { return attributes.get("src"); },
    textContent: "", disabled: false,
  };
}

const nodes = new Map();
function getNode(id) {
  if (!nodes.has(id)) nodes.set(id, node());
  return nodes.get(id);
}
const responses = [];
const calls = [];
const context = {
  document: {getElementById: getNode, querySelectorAll: () => [], addEventListener: () => {}},
  window: {__XHS_CONFIG__: {}},
  fetch: async (url, options) => {
    calls.push({url, method: options?.method || "GET"});
    const response = responses.shift();
    assert(response, `unexpected request ${url}`);
    return response;
  },
  setTimeout: () => 1,
  clearTimeout: () => {},
};
vm.createContext(context);
vm.runInContext(source.slice(0, startup) + "  globalThis.testApi = {state, pollQr, closeQr, bindEvents};\n})();", context);
const {state, pollQr, closeQr, bindEvents} = context.testApi;
const qr = getNode("qrImage");
const message = getNode("qrMessage");
const start = getNode("startQrBtn");
function response(body, status = 200) {
  return {ok: status < 400, status, statusText: "failure", json: async () => body};
}

(async () => {
  state.qrSessionId = "first";
  qr.src = "data:image/png;base64,old";
  responses.push(response({status: "pending", message: "Verifying QR login."}));
  await pollQr();
  assert.equal(state.qrSessionId, "first");
  assert.equal(qr.src, "data:image/png;base64,old");
  assert.equal(message.textContent, "Verifying QR login.");

  responses.push(response({detail: "QR login verification timed out."}, 400), response({message: "cancelled"}));
  await pollQr();
  assert.equal(state.qrSessionId, "");
  assert.equal(start.disabled, false);
  assert.equal(qr.src, undefined, "terminal error must clear stale code");
  assert.equal(qr.classList.contains("hidden"), true);
  assert.match(message.textContent, /登录检查失败/);
  assert.deepEqual(calls.at(-1), {url: "/api/accounts/qrcode/first", method: "DELETE"});

  state.qrSessionId = "second";
  qr.src = "data:image/png;base64,new";
  responses.push(response({message: "cancelled"}));
  await closeQr();
  assert.equal(qr.src, undefined);
  assert.equal(state.qrSessionId, "");

  state.qrSessionId = "late";
  let resolveLate;
  responses.push(new Promise(resolve => { resolveLate = resolve; }));
  const latePoll = pollQr();
  responses.push(response({message: "cancelled"}));
  await closeQr();
  resolveLate(response({status: "success", message: "stale success"}));
  await latePoll;
  assert.equal(state.qrSessionId, "");
  assert.equal(qr.src, undefined);
  assert.equal(message.textContent, "生成后请扫码确认登录");

  state.qrSessionId = "third";
  qr.src = "data:image/png;base64,last";
  responses.push(response({detail: "expired"}, 404), response({message: "cancelled"}));
  await pollQr();
  assert.equal(qr.src, undefined);
  assert.equal(qr.classList.contains("hidden"), true);

  state.qrSessionId = "fourth";
  responses.push(response({status: "success", message: "added"}));
  await pollQr();
  assert.equal(state.qrSessionId, "");
  assert.equal(message.textContent, "added");

  bindEvents();
  qr.src = "data:image/png;base64,stale";
  getNode("qrAccountName").value = "new-account";
  responses.push(response({detail: "startup failed"}, 400));
  await start.listeners.click();
  assert.equal(qr.src, undefined, "new generation must clear stale code");
  assert.equal(qr.classList.contains("hidden"), true);
  assert.equal(start.disabled, false);
  assert.match(message.textContent, /二维码启动失败/);
})().catch(error => { console.error(error); process.exitCode = 1; });
'''


class QrLoginFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend tests")
    def test_qr_pending_terminal_error_and_cancel(self):
        result = subprocess.run(
            ["node", "-e", SCRIPT, str(ROOT / "service" / "static" / "app.js")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
