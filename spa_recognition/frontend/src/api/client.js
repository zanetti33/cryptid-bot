const API_BASE = import.meta.env.VITE_SPA_API_BASE || "http://127.0.0.1:8000";

export async function postEndpoint(path, payload) {
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

