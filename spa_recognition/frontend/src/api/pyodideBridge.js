// Runs the existing pure-Python SpaRecognitionApi in-browser via Pyodide,
// so the SPA can work with no backend at all (used for the static GitHub
// Pages build, gated by VITE_USE_PYODIDE in client.js).
//
// Bump this deliberately, not incidentally - it pins the WASM runtime the
// static site depends on.
const PYODIDE_VERSION = "0.26.4";
const PYODIDE_CDN_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

let bridgePromise = null;

function loadPyodideRuntime() {
  return new Promise((resolve, reject) => {
    if (window.loadPyodide) {
      resolve(window.loadPyodide);
      return;
    }
    const script = document.createElement("script");
    script.src = `${PYODIDE_CDN_BASE}pyodide.js`;
    script.onload = () => resolve(window.loadPyodide);
    script.onerror = () => reject(new Error("Failed to load the Pyodide runtime from the CDN"));
    document.head.appendChild(script);
  });
}

async function initBridge() {
  const loadPyodide = await loadPyodideRuntime();
  const pyodide = await loadPyodide({ indexURL: PYODIDE_CDN_BASE });

  const zipUrl = `${import.meta.env.BASE_URL}pyodide-src.zip`;
  const response = await fetch(zipUrl);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${zipUrl}: HTTP ${response.status}`);
  }
  const archiveBuffer = await response.arrayBuffer();
  pyodide.unpackArchive(archiveBuffer, "zip", { extractDir: "/cryptid_src" });

  pyodide.runPython(`
import sys
if "/cryptid_src" not in sys.path:
    sys.path.insert(0, "/cryptid_src")

import json as _bridge_json
from spa_recognition.backend.api import SpaRecognitionApi

_bridge_api = SpaRecognitionApi()

def _bridge_post(path, payload_json):
    payload = _bridge_json.loads(payload_json) if payload_json else None
    result = _bridge_api.post(path, payload)
    return _bridge_json.dumps(result.to_dict())
`);

  return pyodide.globals.get("_bridge_post");
}

// Singleton: the interpreter + source bundle only need to load once per page.
export function getBridgePost() {
  if (!bridgePromise) {
    bridgePromise = initBridge();
  }
  return bridgePromise;
}
