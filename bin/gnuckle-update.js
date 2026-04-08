#!/usr/bin/env node

const { execSync } = require("child_process");
const path = require("path");

const BANANA = "\u{1F34C}";
const PKG_ROOT = path.resolve(__dirname, "..");
const IS_WIN = process.platform === "win32";

function log(msg) {
  console.log(`  ${BANANA} ${msg}`);
}

function tryExec(command, options = {}) {
  execSync(command, {
    cwd: PKG_ROOT,
    stdio: "inherit",
    ...options,
  });
}

function findPythonCommand() {
  const candidates = ["python", "python3"];
  if (IS_WIN) {
    candidates.push("py -3");
  }

  for (const cmd of candidates) {
    try {
      execSync(`${cmd} --version`, {
        cwd: PKG_ROOT,
        stdio: "ignore",
      });
      return cmd;
    } catch (_) {
      // try next candidate
    }
  }

  return null;
}

function main() {
  console.log();
  log("gnuckle update helper activated");
  log(`updating clone at ${PKG_ROOT}`);
  log("user profiles in .gnuckle stay untouched");
  console.log();

  const pythonCmd = findPythonCommand();
  if (!pythonCmd) {
    log("ape no find python. install python 3.10+ first.");
    process.exit(1);
  }

  try {
    log("git pull --ff-only");
    tryExec("git pull --ff-only");
  } catch (err) {
    log("git pull failed. ape stop here so merge weirdness stay visible.");
    process.exit(err.status || 1);
  }

  try {
    log("npm install");
    tryExec("npm install");
  } catch (err) {
    log("npm install failed. ape cannot finish update.");
    process.exit(err.status || 1);
  }

  try {
    log("python -m pip install -e .");
    tryExec(`${pythonCmd} -m pip install -e .`);
  } catch (err) {
    log("pip editable install failed. ape cannot finish update.");
    process.exit(err.status || 1);
  }

  console.log();
  log("update complete. latest banana acquired.");
  console.log();
}

main();
