#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { version } = require(path.resolve(__dirname, "..", "package.json"));

const PRESETS_PATH = path.resolve(__dirname, "..", "gnuckle", "llama_presets.json");
const CACHE_TYPES = ["f16", "q8_0", "q4_0", "turbo3"];

if (process.argv.includes("--version") || process.argv.includes("-v")) {
  console.log(`gnuckle-profile ${version}`);
  process.exit(0);
}

const { prompt } = require("enquirer");

function readPresets() {
  return JSON.parse(fs.readFileSync(PRESETS_PATH, "utf8"));
}

function findGgufs(baseDir) {
  const results = [];
  const roots = [baseDir, path.join(baseDir, "models"), path.join(baseDir, "gguf")];
  for (const root of roots) {
    if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) continue;
    for (const entry of fs.readdirSync(root)) {
      if (entry.toLowerCase().endsWith(".gguf")) {
        results.push(path.join(root, entry));
      }
    }
  }
  return [...new Set(results)];
}

function findServer(baseDir) {
  const candidates = [
    path.join(baseDir, "build", "bin", "llama-server.exe"),
    path.join(baseDir, "build", "bin", "llama-server"),
    path.join(baseDir, "build", "bin", "Release", "llama-server.exe"),
    path.join(baseDir, "build", "bin", "Release", "llama-server"),
    path.join(baseDir, "build", "bin", "Debug", "llama-server.exe"),
    path.join(baseDir, "build", "bin", "Debug", "llama-server"),
    path.join(baseDir, "bin", "llama-server.exe"),
    path.join(baseDir, "bin", "llama-server"),
    path.join(baseDir, "build", "llama-server.exe"),
    path.join(baseDir, "build", "llama-server"),
  ];
  return candidates.find((p) => fs.existsSync(p) && fs.statSync(p).isFile()) || null;
}

function detectPreset(presets, modelPath) {
  const modelName = path.basename(modelPath).toLowerCase();
  for (const preset of presets.presets || []) {
    if ((preset.match || []).some((token) => modelName.includes(token))) {
      return preset;
    }
  }
  return presets.default;
}

function toNumber(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

async function main() {
  const cwd = process.cwd();
  const defaultProfileDir = path.join(cwd, ".gnuckle", "profiles");
  const presets = readPresets();
  const ggufs = findGgufs(cwd);

  let modelPath;
  if (ggufs.length > 0) {
    const modelChoices = ggufs.map((file) => ({
      name: `${path.basename(file)}  (${(fs.statSync(file).size / (1024 ** 3)).toFixed(2)} GB)`,
      value: file,
    }));
    const answer = await prompt({
      type: "select",
      name: "modelPath",
      message: "select model profile",
      choices: modelChoices,
    });
    modelPath = answer.modelPath;
  } else {
    const answer = await prompt({
      type: "input",
      name: "modelPath",
      message: "model path",
      initial: "",
    });
    modelPath = answer.modelPath.trim();
  }

  const detectedPreset = detectPreset(presets, modelPath);
  const presetChoices = [
    ...(presets.presets || []).map((preset) => ({
      name: `${preset.name} - ${preset.description}`,
      value: preset.name,
    })),
    { name: "custom - edit all sampler values manually", value: "custom" },
  ];

  const presetAnswer = await prompt({
    type: "select",
    name: "samplerPreset",
    message: "sampler preset",
    choices: presetChoices,
    initial: Math.max(
      0,
      presetChoices.findIndex((choice) => choice.value === detectedPreset.name)
    ),
  });

  const selectedPreset =
    presetAnswer.samplerPreset === "custom"
      ? detectedPreset
      : (presets.presets || []).find((preset) => preset.name === presetAnswer.samplerPreset) || presets.default;

  const serverAuto = findServer(cwd);
  const cacheAnswer = await prompt({
    type: "multiselect",
    name: "cacheTypes",
    message: "select cache types",
    choices: CACHE_TYPES.map((label) => ({ name: label, value: label })),
    initial: CACHE_TYPES,
  });

  const profileBasics = await prompt([
    {
      type: "input",
      name: "profileName",
      message: "profile name",
      initial: path.basename(modelPath, ".gguf"),
    },
    {
      type: "input",
      name: "serverPath",
      message: "llama-server path",
      initial: serverAuto || "",
    },
    {
      type: "input",
      name: "scanDir",
      message: "scan dir",
      initial: cwd,
    },
    {
      type: "input",
      name: "outputDir",
      message: "output dir",
      initial: path.join(cwd, "benchmark_results"),
    },
    {
      type: "numeral",
      name: "numTurns",
      message: "turns",
      initial: 20,
      min: 1,
    },
    {
      type: "numeral",
      name: "port",
      message: "port",
      initial: 8080,
      min: 1,
      max: 65535,
    },
  ]);

  const samplerDefaults = selectedPreset.server_args || {};
  const sampler = await prompt([
    {
      type: "numeral",
      name: "temp",
      message: "temp",
      initial: samplerDefaults.temp ?? 0.6,
      min: 0,
      max: 2,
      float: true,
    },
    {
      type: "numeral",
      name: "top_p",
      message: "top-p",
      initial: samplerDefaults.top_p ?? 0.95,
      min: 0,
      max: 1,
      float: true,
    },
    {
      type: "numeral",
      name: "top_k",
      message: "top-k",
      initial: samplerDefaults.top_k ?? 20,
      min: 0,
    },
    {
      type: "numeral",
      name: "repeat_penalty",
      message: "repeat penalty",
      initial: samplerDefaults.repeat_penalty ?? 1.1,
      min: 0,
      max: 2,
      float: true,
    },
    {
      type: "numeral",
      name: "repeat_last_n",
      message: "repeat last n",
      initial: samplerDefaults.repeat_last_n ?? 64,
      min: 0,
    },
    {
      type: "numeral",
      name: "min_p",
      message: "min-p",
      initial: samplerDefaults.min_p ?? 0.0,
      min: 0,
      max: 1,
      float: true,
    },
  ]);

  const promptChoice = await prompt({
    type: "confirm",
    name: "useSystemPrompt",
    message: "add a custom system prompt?",
    initial: false,
  });

  let systemPrompt = "";
  if (promptChoice.useSystemPrompt) {
    const systemPromptAnswer = await prompt({
      type: "editor",
      name: "systemPrompt",
      message: "system prompt",
      initial: "You are a function-calling AI assistant.",
    });
    systemPrompt = systemPromptAnswer.systemPrompt.trim();
  }

  const outputPathAnswer = await prompt({
    type: "input",
    name: "outputPath",
    message: "save profile as",
    initial: path.join(defaultProfileDir, "gnuckle.profile.json"),
  });

  const profile = {
    profile_name: profileBasics.profileName,
    created_at: new Date().toISOString(),
    model_path: path.resolve(modelPath),
    server_path: profileBasics.serverPath ? path.resolve(profileBasics.serverPath) : "",
    scan_dir: path.resolve(profileBasics.scanDir),
    output_dir: path.resolve(profileBasics.outputDir),
    num_turns: toNumber(profileBasics.numTurns, 20),
    port: toNumber(profileBasics.port, 8080),
    cache_types: cacheAnswer.cacheTypes,
    sampler_preset: selectedPreset.name || "default",
    sampler: {
      temp: toNumber(sampler.temp, samplerDefaults.temp ?? 0.6),
      top_p: toNumber(sampler.top_p, samplerDefaults.top_p ?? 0.95),
      top_k: toNumber(sampler.top_k, samplerDefaults.top_k ?? 20),
      repeat_penalty: toNumber(sampler.repeat_penalty, samplerDefaults.repeat_penalty ?? 1.1),
      repeat_last_n: toNumber(sampler.repeat_last_n, samplerDefaults.repeat_last_n ?? 64),
      min_p: toNumber(sampler.min_p, samplerDefaults.min_p ?? 0.0),
    },
    system_prompt: systemPrompt,
    notes: "",
  };

  const outputPath = path.resolve(outputPathAnswer.outputPath);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(profile, null, 2));

  console.log();
  console.log(`  saved profile: ${outputPath}`);
  console.log(`  model: ${path.basename(profile.model_path)}`);
  console.log(`  preset: ${profile.sampler_preset}`);
  console.log(`  caches: ${profile.cache_types.join(", ")}`);
  if (profile.system_prompt) {
    console.log("  system prompt: custom");
  }
  console.log();
}

main().catch((err) => {
  console.error(`gnuckle-profile failed: ${err.message}`);
  process.exit(1);
});
