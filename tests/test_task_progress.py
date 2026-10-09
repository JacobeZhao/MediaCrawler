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
const nodes = new Map();
for (const id of ["taskStatusFilter", "selectionCount", "exportBtn", "deleteTasksBtn", "selectVisibleTasks", "taskRows"]) {
  nodes.set(id, {value: "", innerHTML: "", textContent: "", disabled: false});
}
const context = {
  document: {getElementById: id => nodes.get(id)},
  window: {__XHS_CONFIG__: {}},
};
vm.createContext(context);
vm.runInContext(source.slice(0, startup) + "  globalThis.testApi = {state, renderTasks};\n})();", context);
context.testApi.state.tasks = [
  {id: 1, task_type: "note", status: "completed", params: {notes: Array(50).fill({})}, notes_count: 50},
  {id: 2, task_type: "note", status: "running", params: JSON.stringify({notes: Array(20).fill({})}), notes_count: 5},
  {id: 3, task_type: "search", status: "running", params: {keyword: "test", max_notes: 10}, notes_count: 5},
];
context.testApi.renderTasks();
const html = nodes.get("taskRows").innerHTML;
function card(id) {
  const match = html.match(new RegExp(`<article[^>]+data-task-id="${id}"[\\s\\S]*?<\\/article>`));
  assert(match, `missing card ${id}`);
  return match[0];
}
assert.match(card(1), /<strong>50 \/ 50<\/strong>/);
assert.match(card(1), /aria-valuenow="100"/);
assert.match(card(2), /<strong>5 \/ 20<\/strong>/);
assert.match(card(2), /aria-valuenow="25"/);
assert.match(card(3), /<strong>5 \/ 10<\/strong>/);
assert.match(card(3), /aria-valuenow="50"/);
'''


class TaskProgressTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for frontend rendering tests")
    def test_note_and_search_task_progress(self):
        completed = subprocess.run(
            ["node", "-e", SCRIPT, str(ROOT / "service" / "static" / "app.js")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
