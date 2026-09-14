#!/usr/bin/env node
// Bundles the pure-Python source that the Pyodide-in-browser build needs
// (game_model/, ai/, data/, spa_recognition backend) into a zip served as a
// static asset at runtime. Regenerated on every dev/build via npm pre-hooks
// so it never drifts from the actual Python source.

import { readFileSync, readdirSync, statSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import JSZip from "jszip";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(SCRIPT_DIR, "..", "..", "..");
const OUTPUT_PATH = join(SCRIPT_DIR, "..", "public", "pyodide-src.zip");

const DIR_SOURCES = ["game_model", "ai", "data"];
const FILE_SOURCES = [
  "spa_recognition/__init__.py",
  "spa_recognition/backend/__init__.py",
  "spa_recognition/backend/api.py",
  "spa_recognition/backend/models.py",
  "spa_recognition/backend/session_store.py",
  "spa_recognition/backend/demo_runner.py",
];

function shouldSkip(name) {
  return name === "__pycache__" || name.endsWith(".pyc");
}

function addDirToZip(zip, absDir, relBase) {
  let fileCount = 0;
  for (const entry of readdirSync(absDir)) {
    if (shouldSkip(entry)) continue;
    const absPath = join(absDir, entry);
    const relPath = join(relBase, entry).split("\\").join("/");
    const stats = statSync(absPath);
    if (stats.isDirectory()) {
      fileCount += addDirToZip(zip, absPath, relPath);
    } else {
      zip.file(relPath, readFileSync(absPath));
      fileCount += 1;
    }
  }
  return fileCount;
}

async function main() {
  const zip = new JSZip();
  let totalFiles = 0;

  for (const dir of DIR_SOURCES) {
    const absDir = join(REPO_ROOT, dir);
    totalFiles += addDirToZip(zip, absDir, dir);
  }

  for (const file of FILE_SOURCES) {
    const absPath = join(REPO_ROOT, file);
    zip.file(file, readFileSync(absPath));
    totalFiles += 1;
  }

  mkdirSync(dirname(OUTPUT_PATH), { recursive: true });
  const buffer = await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
  writeFileSync(OUTPUT_PATH, buffer);

  console.log(
    `[build-pyodide-bundle] wrote ${relative(REPO_ROOT, OUTPUT_PATH)} ` +
      `(${totalFiles} files, ${(buffer.length / 1024).toFixed(1)} KB)`,
  );
}

main().catch((error) => {
  console.error("[build-pyodide-bundle] failed:", error);
  process.exit(1);
});
