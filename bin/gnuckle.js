#!/usr/bin/env node

/**
 * gnuckle — an npm package that runs a Python program.
 *
 * this file checks for python, installs the pip package
 * into a local venv, and forwards all args to the real CLI.
 * two ecosystems, one banana.
 */

const { execSync, spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");

const BANANA = "\u{1F34C}";
const PKG_ROOT = path.resolve(__dirname, "..");
const VENV_DIR = path.join(PKG_ROOT, ".gnuckle-venv");
const IS_WIN = os.platform() === "win32";
const PY_VENV_BIN = IS_WIN
  ? path.join(VENV_DIR, "Scripts")
  : path.join(VENV_DIR, "bin");
const PY_EXE = path.join(PY_VENV_BIN, IS_WIN ? "python.exe" : "python");
const PIP_EXE = path.join(PY_VENV_BIN, IS_WIN ? "pip.exe" : "pip");

const APE_PHRASES = [
  "ape boot javascript to run python. this is the way.",
  "node_modules -> python venv -> CUDA kernels. the full stack.",
  "Harambe did not die for us to question npm install gnuckle.",
  "monke bridge two ecosystems with one index.js.",
  "this is either genius or unhinged. probably both.",
  "npm install gnuckle. pip install gnuckle. ape install gnuckle.",
  "javascript is just the banana peel. python is the banana.",
  "somewhere, a software architect is crying. ape does not care.",
  "the real benchmark was the npm install we made along the way.",
  "ape use right tool for right job. node is the tool. python is the job.",
];

function apePhrase() {
  return APE_PHRASES[Math.floor(Math.random() * APE_PHRASES.length)];
}

function log(msg) {
  console.log(`  ${BANANA} ${msg}`);
}

function findPython() {
  const candidates = IS_WIN
    ? ["python", "python3", "py -3"]
    : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} --version 2>&1`, {
        encoding: "utf-8",
        stdio: ["pipe", "pipe", "pipe"],
      }).trim();
      if (version.includes("Python 3")) {
        return cmd.split(" ")[0] === "py" ? "py" : cmd;
      }
    } catch (_) {
      // ape try next
    }
  }
  return null;
}

function ensureVenv(pythonCmd) {
  if (fs.existsSync(PY_EXE)) return;

  log("first run. ape create python venv...");
  log(apePhrase());

  const venvCmd =
    pythonCmd === "py"
      ? `py -3 -m venv "${VENV_DIR}"`
      : `${pythonCmd} -m venv "${VENV_DIR}"`;

  execSync(venvCmd, { stdio: "inherit" });
  log("venv created. installing gnuckle python package...");

  execSync(`"${PIP_EXE}" install -e "${PKG_ROOT}"`, { stdio: "inherit" });
  log("python side ready. ape bridge complete.");
}

function main() {
  console.log();
  log("gnuckle npm wrapper activated");
  log(apePhrase());
  console.log();

  // find system python
  const pythonCmd = findPython();
  if (!pythonCmd) {
    log("ape no find python 3. install python 3.10+ and try again.");
    process.exit(1);
  }

  // ensure venv + pip install
  ensureVenv(pythonCmd);

  // forward all args to the real python CLI
  const args = process.argv.slice(2);
  const child = spawn(PY_EXE, ["-m", "gnuckle", ...args], {
    stdio: "inherit",
    cwd: process.cwd(),
  });

  child.on("close", (code) => {
    process.exit(code || 0);
  });

  child.on("error", (err) => {
    log(`ape encountered error: ${err.message}`);
    log("monke will try again later.");
    process.exit(1);
  });
}

main();
