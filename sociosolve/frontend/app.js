"use strict";

const API_BASE = "https://sih-srijan-sociosolve.onrender.com/api";
const TOKEN_KEY = "sociosolve_token";
const CATEGORIES = [
  "Water", "Health", "Agriculture", "Energy",
  "Education", "Environment", "Infrastructure", "Other",
];

const state = {
  user: null,
  loadingUser: false,
};

// ---------------------------------------------------------------- utils --

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function showToast(message, isError = false) {
  const el = document.getElementById("toast") || (() => {
    const t = document.createElement("div");
    t.id = "toast";
    t.className = "toast";
    document.body.appendChild(t);
    return t;
  })();
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.add("show");
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

function timeAgo(isoString) {
  const then = new Date(isoString + (isoString.endsWith("Z") ? "" : "Z"));
  const diffSec = Math.round((Date.now() - then.getTime()) / 1000);
  if (diffSec < 60) return "just now";
  const mins = Math.round(diffSec / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.round(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.round(months / 12)}y ago`;
}

async function api(path, { method = "GET", body, form = false, auth = false } = {}) {
  const headers = {};
  let payload = body;

  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(body).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });

  if (res.status === 204) return null;

  let data = null;
  try { data = await res.json(); } catch (_) { /* empty body */ }

  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  return data;
}

// ------------------------------------------------------------ auth flow --

async function loadCurrentUser() {
  if (!getToken()) { state.user = null; return; }
  state.loadingUser = true;
  try {
    state.user = await api("/auth/me", { auth: true });
  } catch (_) {
    setToken(null);
    state.user = null;
  } finally {
    state.loadingUser = false;
  }
}

function renderAuthArea() {
  const el = document.getElementById("auth-area");
  el.innerHTML = "";
  if (state.user) {
    const chip = document.createElement("span");
    chip.className = "user-chip";
    chip.textContent = `@${state.user.username}`;
    const logout = document.createElement("button");
    logout.className = "btn btn-secondary";
    logout.textContent = "Log out";
    logout.onclick = () => {
      setToken(null);
      state.user = null;
      renderAuthArea();
      route();
      showToast("Logged out.");
    };
    el.append(chip, logout);
  } else {
    const login = document.createElement("button");
    login.className = "btn btn-secondary";
    login.textContent = "Log in";
    login.onclick = () => openModal("login");

    const signup = document.createElement("button");
    signup.className = "btn btn-primary";
    signup.textContent = "Sign up";
    signup.onclick = () => openModal("signup");

    el.append(login, signup);
  }
}

function openModal(which) {
  document.getElementById("modal-backdrop").classList.add("open");
  switchAuthForm(which);
}
function closeModal() {
  document.getElementById("modal-backdrop").classList.remove("open");
  document.querySelectorAll(".auth-form .form-error").forEach((e) => (e.textContent = ""));
  document.querySelectorAll(".auth-form").forEach((f) => f.reset());
}
function switchAuthForm(which) {
  document.getElementById("login-form").classList.toggle("hidden", which !== "login");
  document.getElementById("signup-form").classList.toggle("hidden", which !== "signup");
}

function wireAuthModal() {
  document.getElementById("modal-close").onclick = closeModal;
  document.getElementById("modal-backdrop").addEventListener("click", (e) => {
    if (e.target.id === "modal-backdrop") closeModal();
  });
  document.querySelectorAll("[data-switch-to]").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      switchAuthForm(link.dataset.switchTo);
    });
  });

  document.getElementById("login-form").addEventListener("submit", async (e) => {
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
      state.user = data.user;
      closeModal();
      renderAuthArea();
      route();
      showToast(`Welcome back, ${data.user.username}.`);
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });

  document.getElementById("signup-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const errorEl = form.querySelector("[data-error]");
    errorEl.textContent = "";
    const fd = new FormData(form);
    try {
      const data = await api("/auth/signup", {
        method: "POST",
        body: {
          username: fd.get("username"),
          email: fd.get("email"),
          password: fd.get("password"),
        },
      });
      setToken(data.access_token);
      state.user = data.user;
      closeModal();
      renderAuthArea();
      route();
      showToast(`Account created. Welcome, ${data.user.username}.`);
    } catch (err) {
      errorEl.textContent = err.message;
    }
  });
}

// ----------------------------------------------------------- rendering --

function buildQuestionCard(q) {
  const tpl = document.getElementById("tpl-question-card");
  const node = tpl.content.cloneNode(true);
  const card = node.querySelector(".q-card");
  card.dataset.category = q.category;
  card.addEventListener("click", () => { location.hash = `#/q/${q.id}`; });

  const badge = node.querySelector(".badge-status");
  badge.textContent = q.status === "answered" ? "Answered" : "Open";
  badge.classList.add(q.status === "answered" ? "badge-answered" : "badge-open");

  node.querySelector(".q-title").textContent = q.title;
  node.querySelector(".q-meta").textContent =
    `${q.category} · ${q.answer_count} ${q.answer_count === 1 ? "answer" : "answers"} · ` +
    `by @${q.author_username} · ${timeAgo(q.created_at)}`;

  return node;
}

function renderHero(container, recentQuestions) {
  const hero = document.createElement("section");
  hero.className = "hero";

  const left = document.createElement("div");
  left.innerHTML = `
    <h1>Report a problem.<br>A student solves it.</h1>
    <p class="hero-sub">SocioSolve turns everyday civic problems — water, health, farming, energy,
      schooling — into projects universities, industry mentors, and an AI first-responder can
      actually act on.</p>
  `;
  const ctas = document.createElement("div");
  ctas.className = "hero-ctas";
  const askBtn = document.createElement("a");
  askBtn.className = "btn btn-primary";
  askBtn.href = "#/ask";
  askBtn.textContent = "Post a problem";
  const browseBtn = document.createElement("a");
  browseBtn.className = "btn btn-secondary";
  browseBtn.href = "#/";
  browseBtn.textContent = "See what's been solved";
  ctas.append(askBtn, browseBtn);
  left.appendChild(ctas);

  const right = document.createElement("div");
  right.className = "hero-stack";
  recentQuestions.slice(0, 3).forEach((q) => right.appendChild(buildQuestionCard(q)));

  hero.append(left, right);
  container.appendChild(hero);
}

async function renderBrowse(container, filters = {}) {
  container.innerHTML = `<div class="loading-line">Loading problems…</div>`;

  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.status) params.set("status", filters.status);
  if (filters.search) params.set("search", filters.search);

  let questions;
  try {
    questions = await api(`/questions?${params.toString()}`);
  } catch (err) {
    container.innerHTML = `<p class="form-error">Couldn't load problems: ${escapeText(err.message)}</p>`;
    return;
  }

  container.innerHTML = "";

  const isUnfiltered = !filters.category && !filters.status && !filters.search;
  if (isUnfiltered && questions.length > 0) {
    renderHero(container, questions);
  }

  const bar = document.createElement("div");
  bar.className = "filter-bar";
  bar.innerHTML = `
    <select id="f-category"><option value="">All categories</option></select>
    <select id="f-status">
      <option value="">All statuses</option>
      <option value="open">Open</option>
      <option value="answered">Answered</option>
    </select>
    <input type="search" id="f-search" placeholder="Search problems…" />
    <span class="filter-count"></span>
  `;
  CATEGORIES.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c; opt.textContent = c;
    bar.querySelector("#f-category").appendChild(opt);
  });
  bar.querySelector("#f-category").value = filters.category || "";
  bar.querySelector("#f-status").value = filters.status || "";
  bar.querySelector("#f-search").value = filters.search || "";
  bar.querySelector(".filter-count").textContent =
    `${questions.length} ${questions.length === 1 ? "problem" : "problems"}`;

  let debounceTimer;
  const applyFilters = () => {
    const next = {
      category: bar.querySelector("#f-category").value,
      status: bar.querySelector("#f-status").value,
      search: bar.querySelector("#f-search").value.trim(),
    };
    renderBrowse(container, next);
  };
  bar.querySelector("#f-category").addEventListener("change", applyFilters);
  bar.querySelector("#f-status").addEventListener("change", applyFilters);
  bar.querySelector("#f-search").addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(applyFilters, 350);
  });

  container.appendChild(bar);

  if (questions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No problems match yet. Be the first to post one.";
    container.appendChild(empty);
    return;
  }

  const grid = document.createElement("div");
  grid.className = "q-grid";
  questions.forEach((q) => grid.appendChild(buildQuestionCard(q)));
  container.appendChild(grid);
}

function renderAsk(container) {
  container.innerHTML = "";

  if (!state.user) {
    const prompt = document.createElement("div");
    prompt.className = "login-prompt";
    prompt.innerHTML = `You need an account to post a problem. `;
    const link = document.createElement("a");
    link.href = "#";
    link.textContent = "Log in or sign up";
    link.onclick = (e) => { e.preventDefault(); openModal("login"); };
    prompt.appendChild(link);
    container.appendChild(prompt);
    return;
  }

  const panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML = `
    <h2>Post a problem</h2>
    <p class="panel-sub">Be specific — a clear problem gets a better answer, human or AI.</p>
    <form id="ask-form">
      <label>Title
        <input type="text" name="title" minlength="5" maxlength="200" required
          placeholder="e.g. Open drainage flooding Sector 12 every monsoon" />
      </label>
      <label>Category
        <select name="category"></select>
      </label>
      <label>Description
        <textarea name="description" minlength="10" maxlength="5000" required
          placeholder="What's happening, where, how long, who's affected, what's been tried so far?"></textarea>
      </label>
      <p class="form-error" data-error></p>
      <button type="submit" class="btn btn-primary btn-block">Post problem</button>
    </form>
  `;
  const select = panel.querySelector("select[name=category]");
  CATEGORIES.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c; opt.textContent = c;
    select.appendChild(opt);
  });

  container.appendChild(panel);

  panel.querySelector("#ask-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const errorEl = form.querySelector("[data-error]");
    errorEl.textContent = "";
    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;
    const fd = new FormData(form);
    try {
      const question = await api("/questions", {
        method: "POST",
        auth: true,
        body: {
          title: fd.get("title"),
          description: fd.get("description"),
          category: fd.get("category"),
        },
      });
      showToast("Problem posted.");
      location.hash = `#/q/${question.id}`;
    } catch (err) {
      errorEl.textContent = err.message;
      submitBtn.disabled = false;
    }
  });
}

function buildAnswerNode(a) {
  const tpl = document.getElementById("tpl-answer");
  const node = tpl.content.cloneNode(true);
  const authorEl = node.querySelector(".answer-author");
  if (a.is_ai_generated) {
    authorEl.textContent = "AI Insight";
    authorEl.classList.add("ai");
  } else {
    authorEl.textContent = `@${a.author_username || "unknown"}`;
  }
  node.querySelector(".answer-time").textContent = timeAgo(a.created_at);
  node.querySelector(".answer-body").textContent = a.body;
  return node;
}

async function renderDetail(container, id) {
  container.innerHTML = `<div class="loading-line">Loading problem…</div>`;
  let q;
  try {
    q = await api(`/questions/${id}`);
  } catch (err) {
    container.innerHTML = `<p class="form-error">Couldn't load that problem: ${escapeText(err.message)}</p>`;
    return;
  }

  container.innerHTML = "";

  const head = document.createElement("div");
  head.className = "q-detail-head";
  const badge = document.createElement("span");
  badge.className = `badge ${q.status === "answered" ? "badge-answered" : "badge-open"}`;
  badge.textContent = q.status === "answered" ? "Answered" : "Open";
  const h1 = document.createElement("h1");
  h1.textContent = q.title;
  const meta = document.createElement("p");
  meta.className = "q-meta";
  meta.textContent = `${q.category} · asked by @${q.author_username} · ${timeAgo(q.created_at)}`;
  head.append(badge, h1, meta);

  const desc = document.createElement("p");
  desc.className = "q-description";
  desc.textContent = q.description;

  container.append(head, desc);

  const actions = document.createElement("div");
  actions.className = "detail-actions";
  if (state.user) {
    const aiBtn = document.createElement("button");
    aiBtn.className = "btn btn-secondary";
    aiBtn.textContent = "Get AI Insight";
    aiBtn.onclick = async () => {
      aiBtn.disabled = true;
      aiBtn.textContent = "Thinking…";
      try {
        await api(`/questions/${id}/ai-answer`, { method: "POST", auth: true });
        showToast("AI insight added.");
        renderDetail(container, id);
      } catch (err) {
        showToast(err.message, true);
        aiBtn.disabled = false;
        aiBtn.textContent = "Get AI Insight";
      }
    };
    actions.appendChild(aiBtn);
  }
  container.appendChild(actions);

  const answersSection = document.createElement("div");
  answersSection.className = "answers-section";
  const h2 = document.createElement("h2");
  h2.textContent = `${q.answers.length} ${q.answers.length === 1 ? "answer" : "answers"}`;
  answersSection.appendChild(h2);
  if (q.answers.length === 0) {
    const empty = document.createElement("p");
    empty.className = "loading-line";
    empty.textContent = "No answers yet — be the first, or ask for an AI insight above.";
    answersSection.appendChild(empty);
  } else {
    q.answers.forEach((a) => answersSection.appendChild(buildAnswerNode(a)));
  }
  container.appendChild(answersSection);

  if (state.user) {
    const answerPanel = document.createElement("div");
    answerPanel.className = "answer-form";
    answerPanel.innerHTML = `
      <h3>Add your answer</h3>
      <form id="answer-form">
        <label>
          <textarea name="body" minlength="2" maxlength="5000" required
            placeholder="Share a concrete suggestion, resource, or next step…"></textarea>
        </label>
        <p class="form-error" data-error></p>
        <button type="submit" class="btn btn-primary">Post answer</button>
      </form>
    `;
    container.appendChild(answerPanel);
    answerPanel.querySelector("#answer-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = e.target;
      const errorEl = form.querySelector("[data-error]");
      errorEl.textContent = "";
      const fd = new FormData(form);
      try {
        await api(`/questions/${id}/answers`, {
          method: "POST",
          auth: true,
          body: { body: fd.get("body") },
        });
        renderDetail(container, id);
      } catch (err) {
        errorEl.textContent = err.message;
      }
    });
  } else {
    const prompt = document.createElement("div");
    prompt.className = "login-prompt";
    prompt.textContent = "Log in to add an answer.";
    container.appendChild(prompt);
  }
}

function escapeText(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

// --------------------------------------------------------------- router --

function setActiveNav(hash) {
  document.querySelectorAll(".main-nav a[data-nav]").forEach((a) => {
    a.classList.toggle("active", a.getAttribute("href") === hash || (hash === "" && a.getAttribute("href") === "#/"));
  });
}

function route() {
  const app = document.getElementById("app");
  const hash = location.hash || "#/";
  setActiveNav(hash.startsWith("#/q/") ? "#/" : hash);

  document.getElementById("nav-toggle").parentElement
    .querySelector(".main-nav")?.classList.remove("mobile-open");

  if (hash === "#/" || hash === "") {
    renderBrowse(app, {});
  } else if (hash === "#/ask") {
    renderAsk(app);
  } else if (hash.startsWith("#/q/")) {
    const id = hash.split("/")[2];
    renderDetail(app, id);
  } else {
    app.innerHTML = `<div class="empty-state">Page not found. <a href="#/">Go home</a></div>`;
  }
}

// --------------------------------------------------------------- init --

document.addEventListener("DOMContentLoaded", async () => {
  wireAuthModal();
  document.getElementById("nav-toggle").addEventListener("click", () => {
    document.querySelector(".main-nav").classList.toggle("mobile-open");
  });

  renderAuthArea();
  await loadCurrentUser();
  renderAuthArea();

  window.addEventListener("hashchange", route);
  route();
});
