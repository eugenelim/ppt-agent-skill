/**
 * elk_runner.js — stdin → ELK layout → stdout
 *
 * Reads a JSON ELK graph from stdin, runs elk.layout(), writes the
 * positioned result JSON to stdout. Called by elk_adapter.py via subprocess.
 *
 * Usage: node elk_runner.js
 *   stdin:  ELK graph JSON
 *   stdout: positioned ELK result JSON
 *   exit 0 on success, exit 1 on error (error message on stderr)
 */

const path = require("path");

// Resolve elkjs from the same directory as this script.
const elkBundled = path.join(__dirname, "node_modules", "elkjs", "lib", "elk.bundled.js");
let ELK;
try {
  ELK = require(elkBundled);
} catch (e) {
  process.stderr.write(`elk_runner: could not load elkjs: ${e.message}\n`);
  process.exit(1);
}

const elk = new ELK();

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { raw += chunk; });
process.stdin.on("end", () => {
  let graph;
  try {
    graph = JSON.parse(raw);
  } catch (e) {
    process.stderr.write(`elk_runner: invalid JSON on stdin: ${e.message}\n`);
    process.exit(1);
  }

  elk.layout(graph)
    .then((result) => {
      process.stdout.write(JSON.stringify(result));
      process.exit(0);
    })
    .catch((err) => {
      process.stderr.write(`elk_runner: layout failed: ${err.message || err}\n`);
      process.exit(1);
    });
});
