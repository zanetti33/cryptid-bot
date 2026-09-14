import { getBridgePost } from "./pyodideBridge";

const USE_PYODIDE = import.meta.env.VITE_USE_PYODIDE === "true";
const API_BASE = import.meta.env.VITE_SPA_API_BASE || "http://127.0.0.1:8000";

async function fetchPostEndpoint(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Request failed ${response.status}: ${text}`);
  }

  return response.json();
}

async function pyodidePostEndpoint(path, payload) {
  const bridgePost = await getBridgePost();
  let resultJson;
  try {
    resultJson = bridgePost(path, payload ? JSON.stringify(payload) : null);
  } catch (error) {
    throw new Error(`Request failed for ${path}: ${error?.message || error}`);
  }
  return JSON.parse(resultJson);
}

// Static builds (GitHub Pages) run the whole SpaRecognitionApi in-browser via
// Pyodide instead of hitting a real backend; Docker dev/prod keep using fetch.
export async function postEndpoint(path, payload) {
  return USE_PYODIDE ? pyodidePostEndpoint(path, payload) : fetchPostEndpoint(path, payload);
}
