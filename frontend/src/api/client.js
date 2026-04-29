/**
 * API client for the RiskLens backend.
 *
 * All calls go through the Vite dev proxy (/api → localhost:8000/api)
 * so there are no CORS issues during development.
 */

const BASE = "/api/v1";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/** GET /health */
export function fetchHealth() {
  return request("/health");
}

/** POST /score/batch — JSON array of transactions */
export function scoreBatch(transactions) {
  return request("/score/batch", {
    method: "POST",
    body: JSON.stringify({ transactions }),
  });
}

/** POST /score/upload — FormData with a CSV file */
export async function scoreUpload(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/score/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/** POST /score/single — one transaction */
export function scoreSingle(transaction) {
  return request("/score/single", {
    method: "POST",
    body: JSON.stringify(transaction),
  });
}

/** POST /score/detect — get columns from CSV without scoring */
export async function detectColumns(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/score/detect`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/** POST /score/upload — score CSV with explicit column mapping */
export async function scoreUploadMapped(file, colUser, colAmount, colTime) {
  const form = new FormData();
  form.append("file", file);
  form.append("col_user", colUser);
  form.append("col_amount", colAmount);
  form.append("col_time", colTime);
  const res = await fetch(`${BASE}/score/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
