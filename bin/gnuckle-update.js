#!/usr/bin/env node

const { spawn } = require("child_process");
const path = require("path");
const { version } = require(path.resolve(__dirname, "..", "package.json"));

const PKG_ROOT = path.resolve(__dirname, "..");

function main() {
  if (process.argv.includes("--version") || process.argv.includes("-v")) {
    console.log(`gnuckle-update ${version}`);
    return;
  }

  const child = spawn("python", ["-m", "gnuckle", "--update"], {
    stdio: "inherit",
    cwd: PKG_ROOT,
  });

  child.on("close", (code) => {
    process.exit(code || 0);
  });

  child.on("error", (err) => {
    console.error(`gnuckle-update failed: ${err.message}`);
    process.exit(1);
  });
}

main();
