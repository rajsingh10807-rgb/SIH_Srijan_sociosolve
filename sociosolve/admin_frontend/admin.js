"use strict";

// Note: the API lives at /api regardless of which path served this page,
// since the backend mounts the API routers before any static file mount.
const API_BASE = "/api";
// Deliberately a *different* localStorage key than the public site's
// token, so an admin's console session never gets mixed up with (or
// overwritten by) a regular logged-in session in the same browser.
const TOKEN_KEY = "sociosolve_admin_token";

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); }

async function api(path, { method = "GET", body, form = false } = {}) {
  const headers = {};
  let payload = body;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(body).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  return data;
}

function showScreen(which) {
  document.getElementById("login-screen").classList.toggle("hidden", which !== "login");
  document.getElementById("dashboard-screen").classList.toggle("hidden", which !== "dashboard");
}

// ------------------------------------------------------------- stats --

function statCard(value, label, tone) {
  const div = document.createElement("div");
  div.className = "stat-card";
  div.innerHTML = `<div class="stat-value ${tone || ""}"></div><div class="stat-label"></div>`;
  div.querySelector(".stat-value").textContent = value;
  div.querySelector(".stat-label").textContent = label;
  return div;
}

async function loadStats() {
  const grid = document.getElementById("stats-grid");
  grid.innerHTML = "";
  const s = await api("/admin/stats");
  grid.append(
    statCard(s.total_questions, "problems posted"),
    statCard(s.open_questions, "still open"),
    statCard(s.total_answers, "total answers"),
    statCard(s.ai_answers, "AI insights"),
    statCard(s.total_users, "users"),
    statCard(s.active_key_present ? "present" : "missing", "active Groq key",
      s.active_key_present ? "ok" : "warn"),
  );
  document.querySelector('input[name="active_model"]').value = s.active_model;
}

// -------------------------------------------------------------- keys --

function relTime(iso) {
  if (!iso) return "never";
  const then = new Date(iso.endsWith("Z") ? iso : iso + "Z");
  const diffMin = Math.round((Date.now() - then.getTime()) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const hrs = Math.round(diffMin / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

async function loadKeys() {
  const container = document.getElementById("keys-table");
  container.innerHTML = `<p class="empty-line">Loading keys…</p>`;
  const keys = await api("/admin/keys");

  if (keys.length === 0) {
    container.innerHTML = `<p class="empty-line">No Groq keys on file yet — add one below.</p>`;
    return;
  }

  container.innerHTML = "";
  keys.forEach((k) => {
    const row = document.createElement("div");
    row.className = "key-row";

    const main = document.createElement("div");
    main.className = "key-main";
    const valueLine = document.createElement("span");
    valueLine.className = "key-value";
    valueLine.textContent = k.label ? `${k.masked_key}  —  ${k.label}` : k.masked_key;
    const metaLine = document.createElement("span");
    metaLine.className = "key-meta" + (k.last_error ? " error" : "");
    metaLine.textContent = k.last_error
      ? `last used ${relTime(k.last_used_at)} · error: ${k.last_error.slice(0, 80)}`
      : `added ${relTime(k.added_at)} · last used ${relTime(k.last_used_at)}`;
    main.append(valueLine, metaLine);

    const badge = document.createElement("span");
    badge.className = `badge ${k.is_active ? "badge-active" : "badge-inactive"}`;
    badge.textContent = k.is_active ? "ACTIVE" : "idle";

    const testBtn = document.createElement("button");
    testBtn.className = "btn btn-ghost btn-small";
    testBtn.textContent = "Test";
    testBtn.onclick = async () => {
      testBtn.disabled = true;
      testBtn.textContent = "Testing…";
      try {
        const result = await api(`/admin/keys/${k.id}/test`, { method: "POST" });
        testBtn.textContent = result.ok ? "✓ OK" : "✗ Failed";
      } catch (err) {
        testBtn.textContent = "✗ Error";
      }
      setTimeout(() => { testBtn.disabled = false; testBtn.textContent = "Test"; }, 2500);
    };

    const actions = document.createElement("div");
    actions.className = "key-actions";
    actions.appendChild(testBtn);
    if (!k.is_active) {
      const activateBtn = document.createElement("button");
      activateBtn.className = "btn btn-ghost btn-small";
      activateBtn.textContent = "Activate";
      activateBtn.onclick = async () => {
        await api(`/admin/keys/${k.id}/activate`, { method: "POST" });
        loadKeys();
        loadStats();
      };
      actions.appendChild(activateBtn);
    }
    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-danger btn-small";
    deleteBtn.textContent = "Delete";
    deleteBtn.onclick = async () => {
      if (!confirm("Remove this key? This can't be undone.")) return;
      await api(`/admin/keys/${k.id}`, { method: "DELETE" });
      loadKeys();
      loadStats();
    };
    actions.appendChild(deleteBtn);

    row.append(main, badge, actions);
    container.appendChild(row);
  });
}

// ---------------------------------------------------------------- init --

async function loadDashboard() {
  await Promise.all([loadStats(), loadKeys()]);
}

async function tryResumeSession() {
  if (!getToken()) return false;
  try {
    await api("/admin/whoami");
    return true;
  } catch (_) {
    setToken(null);
    return false;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("admin-login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const errorEl = form.querySelector("[data-error]");
    errorEl.textContent = "";
    const fd = new FormData(form);
    try {
      const data = await api("/auth/login", {
        method: "POST",
        form: true,
        body: { username: fd.get("username"), password: fd.get("password") },
      });
      setToken(data.access_token);
      await api("/admin/whoami"); // throws 403 if this account isn't an admin
      showScreen("dashboard");
      loadDashboard();
    } catch (err) {
      setToken(null);
      errorEl.textContent = err.status === 403
        ? "That account exists but isn't an admin."
        : err.message;
    }
  });

  document.getElementById("logout-btn").addEventListener("click", () => {
    setToken(null);
    showScreen("login");
  });

  document.getElementById("add-key-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const errorEl = document.querySelector('[data-error="add-key"]');
    errorEl.textContent = "";
    const fd = new FormData(form);
    try {
      await api("/admin/keys", {
        method: "POST",
        body: {
          key_value: fd.get("key_value"),
          label: fd.get("label") || null,
          make_active: fd.get("make_active") === "on",
        },
      });
      form.reset();
      form.querySelector('input[name="make_active"]').checked = true;
      loadKeys();
      loadStats();
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });

  document.getElementById("model-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const errorEl = document.querySelector('[data-error="model"]');
    errorEl.textContent = "";
    const fd = new FormData(form);
    try {
      await api("/admin/settings", {
        method: "PUT",
        body: { active_model: fd.get("active_model") },
      });
      errorEl.textContent = "";
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });

  if (await tryResumeSession()) {
    showScreen("dashboard");
    loadDashboard();
  } else {
    showScreen("login");
  }
});
