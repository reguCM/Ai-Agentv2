const logEl = document.getElementById("log");
const form = document.getElementById("form");
const input = document.getElementById("input");
const send = document.getElementById("send");
const meta = document.getElementById("meta");
const currentModelEl = document.getElementById("currentModel");
const modelBtn = document.getElementById("modelBtn");
const modelMenu = document.getElementById("modelMenu");
const ollamaStatus = document.getElementById("ollamaStatus");
const capsEl = document.getElementById("caps");
const newChatBtn = document.getElementById("newChat");
const testMode = document.getElementById("testMode");
const testModeStatus = document.getElementById("testModeStatus");
const testProgress = document.getElementById("testProgress");
const testResults = document.getElementById("testResults");

let sessionId = localStorage.getItem("localAgentSessionId") || "";
let currentModel = "";
let availableModels = [];
let busy = false;
let historyLoaded = false;
let lastTurn = null;
let workspace = "chat";
let caseFilter = "all";
let selectedCaseId = "";
let skipPanelAutoload = false;
let lastCasePayload = null;
let testBatchJobId = "";
let testBatchTimer = null;

function escapeHtml(text) {
  return String(text == null ? "" : text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function roleLabel(role) {
  if (role === "user") return "ユーザー";
  if (role === "error") return "エラー";
  if (role === "notice") return "お知らせ";
  if (role === "processing") return "Local Agent";
  return "Local Agent";
}

function formatObservation(value, indent) {
  const pad = "  ".repeat(indent || 0);
  if (value == null) return pad + "null";
  if (typeof value !== "object") return pad + String(value);
  if (Array.isArray(value)) {
    if (!value.length) return pad + "[]";
    return value.map((item) => formatObservation(item, indent || 0)).join("\n");
  }
  return Object.keys(value)
    .map((key) => {
      const child = value[key];
      if (child && typeof child === "object" && !Array.isArray(child)) {
        return pad + key + ":\n" + formatObservation(child, (indent || 0) + 1);
      }
      if (Array.isArray(child)) {
        if (child.some((item) => item && typeof item === "object")) {
          return pad + key + ":\n" + child
            .map((item) => formatObservation(item, (indent || 0) + 1))
            .join("\n");
        }
        return pad + key + ": " + child.join(", ");
      }
      return pad + key + ": " + String(child);
    })
    .join("\n");
}

function renderPipeline(turn) {
  const steps = turn.pipeline || [];
  if (!steps.length) return "";
  const lines = [];
  steps.forEach((step, i) => {
    if (step.id === "search_capability") {
      const exec = step.executed ? "Search 実行 = あり" : "Search 実行 = なし";
      lines.push(`[能力] ${step.label} / ${exec}`);
      return;
    }
    const extra = step.model ? `（モデル: ${step.model}）` : "";
    lines.push(`${step.label}${extra}`);
    if (step.id === "compose") {
      const sections = (step.sections || []).join(", ") || "NOT_OBSERVED";
      lines.push(`sections: ${sections}`);
      lines.push("independent_tool_calls: false");
    }
    if (step.id === "search") {
      if (step.query) lines.push("query: " + step.query);
      if (step.hit_count != null) lines.push("hit_count: " + step.hit_count);
    }
    if (step.id === "tool" && step.name === "search_web") {
      if (step.query) lines.push("query: " + step.query);
      if (step.hit_count != null) lines.push("hit_count: " + step.hit_count);
    }
    if (step.id === "research_path") {
      lines.push("Chat → ResearchRecord: NOT CONNECTED");
    }
    if (step.id === "research_write") {
      lines.push(step.executed ? "Research Write: saved" : "Matrix Write: NOT OBSERVED");
    }
    if (step.id === "tool_result" && step.summary) {
      lines.push(typeof step.summary === "string" ? step.summary : formatObservation(step.summary, 1));
    }
    if (step.message) lines.push(step.message);
    if (i < steps.length - 1 && step.id !== "search_capability") lines.push(" ↓");
  });
  return `<pre class="pipeline">${escapeHtml(lines.join("\n"))}</pre>`;
}

function runtimeStatusLabel(status) {
  const value = String(status || "unknown");
  if (value === "complete") return "complete";
  if (value === "in_progress") return "in progress";
  return value.replace(/_/g, " ");
}

function renderRuntimeSummary(turn) {
  if (!turn) return "";
  const runtime = turn.task_runtime;
  const mission = turn.mission_memory;
  const judgment = turn.goal_completion_judgment;
  const gate = turn.answer_gate || {};
  const awaitingGoal =
    turn.awaiting_goal_completion_human ||
    (runtime && runtime.awaiting_goal_completion_human);
  if (!runtime && !mission && !judgment && !awaitingGoal && !gate.reason) return "";

  const lines = [];
  if (runtime && Array.isArray(runtime.tasks) && runtime.tasks.length) {
    lines.push("[Task / Goal Runtime]");
    runtime.tasks.forEach((task) => {
      const id = task.task_id || "?";
      const title = task.title || "";
      lines.push(`${id}: ${runtimeStatusLabel(task.status)} — ${title}`.trim());
      if (task.satisfied_conditions && task.satisfied_conditions.length) {
        lines.push(`  satisfied: ${task.satisfied_conditions.join(", ")}`);
      }
    });
    const goals = runtime.goals || [];
    const rootGoals = goals.filter((goal) => {
      const id = String(goal.goal_id || "");
      return id === "G1" || !id.includes(".");
    });
    (rootGoals.length ? rootGoals : goals).forEach((goal) => {
      const id = goal.goal_id || "?";
      const title = goal.title || "";
      lines.push(`${id}: ${runtimeStatusLabel(goal.status)} — ${title}`.trim());
    });
    const evidenceCount =
      runtime.evidence_count != null
        ? runtime.evidence_count
        : Array.isArray(runtime.evidence)
          ? runtime.evidence.length
          : null;
    if (evidenceCount != null) lines.push(`Evidence count: ${evidenceCount}`);
  }
  if (awaitingGoal) lines.push("Goal Completion: AWAITING_HUMAN");
  if (gate.reason) lines.push(`Answer gate: ${gate.reason}`);
  if (mission) {
    lines.push("[Mission Memory]");
    if (mission.mission_id) lines.push(`mission_id: ${mission.mission_id}`);
    if (mission.execution_id) lines.push(`execution_id: ${mission.execution_id}`);
    if (mission.execution_end_state_judgment) {
      lines.push(`judgment: ${mission.execution_end_state_judgment}`);
    }
    if (mission.execution_end_state) {
      lines.push(`execution_end_state: ${mission.execution_end_state}`);
    }
    if (mission.goal_achievement_result) {
      lines.push(`goal_achievement_result: ${mission.goal_achievement_result}`);
    }
    if (mission.stop_reason) lines.push(`stop_reason: ${mission.stop_reason}`);
  }
  if (judgment && judgment.status) {
    lines.push(`Goal Completion Judgment: ${judgment.status}`);
    if (judgment.execution_end_state) {
      lines.push(`Mission 状態: ${judgment.execution_end_state}`);
    }
  }
  if (!lines.length) return "";
  return `<pre class="runtime-summary">${escapeHtml(lines.join("\n"))}</pre>`;
}

function renderSteps(turn) {
  const tools = turn.tools || [];
  const memory = turn.memory || {};
  const session = turn.session_summary || {};
  const lines = turn.status_lines && turn.status_lines.length
    ? turn.status_lines.slice()
    : ["● ユーザー入力を受信しました"];
  if (tools.length) {
    tools.forEach((t) => {
      const summary = t.summary;
      if (t.name === "search_web") {
        lines.push("[TOOL_CALL] search_web");
        if (summary && summary.query) lines.push("query: " + summary.query);
        if (summary && summary.hit_count != null) lines.push("hit_count: " + summary.hit_count);
        if (summary && summary.composed_section_keys && summary.composed_section_keys.length) {
          lines.push("[COMPOSE] sections: " + summary.composed_section_keys.join(", "));
          lines.push("independent_tool_calls: false");
        }
        lines.push("[SEARCH_RESULT]");
        lines.push("status: " + (t.status || (summary && summary.status) || "NOT_OBSERVED"));
        if (summary && summary.web_status_overall) {
          lines.push("web_status: " + summary.web_status_overall);
        }
        if (summary && summary.hit_count != null) lines.push("hit_count: " + summary.hit_count);
        if (summary && summary.omitted && summary.omitted.length) {
          lines.push("omitted: " + summary.omitted.join(", "));
        }
      } else {
        lines.push("[Tool Call] " + (t.name || ""));
        if (summary && summary.composed_section_keys && summary.composed_section_keys.length) {
          lines.push("[COMPOSE] sections: " + summary.composed_section_keys.join(", "));
          lines.push("independent_tool_calls: false");
        }
        lines.push("[Tool Result]");
        if (summary && typeof summary === "object") {
          formatObservation(summary, 1).split("\n").forEach((row) => lines.push(row));
        } else if (summary) {
          lines.push(String(summary));
        }
      }
    });
  }
  lines.push("検索: " + (turn.web_search ? "実行した" : "していない"));
  lines.push("[RESEARCH] NOT CONNECTED");
  lines.push("[MATRIX_WRITE] NOT OBSERVED");
  lines.push("Session: " + (session.session_id || turn.session_id || ""));
  lines.push("Case: " + (turn.case_id || "（なし）"));
  lines.push("correlation_id: " + (turn.correlation_id || "（なし）"));
  lines.push("Research: " + (session.research || "未使用"));
  lines.push("Memory: " + (session.memory || "未使用"));
  lines.push("Cursor接続: " + (turn.cursor_connected ? "あり" : "なし"));
  if (turn.model) lines.push("モデル: " + turn.model);
  const extra = (turn.events || [])
    .filter((e) => e.type === "error")
    .map((e) => "エラー詳細: " + (e.message || ""));
  return [...lines, ...extra]
    .map((line) => `<li>${escapeHtml(line)}</li>`)
    .join("");
}

function addBubble(role, text, turn) {
  const div = document.createElement("div");
  const cls = role === "user" ? "user" : role === "error" ? "error" : role === "notice" ? "notice" : role === "processing" ? "processing" : "agent";
  div.className = "bubble " + cls;
  if (role === "processing") div.id = "processing";
  let extra = "";
  if (turn && role !== "processing") {
    extra =
      `${renderPipeline(turn)}${renderRuntimeSummary(turn)}` +
      `<details><summary>処理を見る</summary><ol class="steps">${renderSteps(turn)}</ol></details>`;
    lastTurn = turn;
    renderProcessing();
  }
  const bodyClass = role === "error" ? "body err" : "body";
  div.innerHTML = `<div class="role">${roleLabel(role)}</div><div class="${bodyClass}">${escapeHtml(text)}</div>${extra}`;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
  return div;
}

function removeProcessing() {
  const el = document.getElementById("processing");
  if (el) el.remove();
}

let activityHeartbeat = null;

function formatElapsed(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return String(minutes).padStart(2, "0") + ":" + String(remainder).padStart(2, "0");
}

async function refreshActivityBubble() {
  if (!sessionId) return;
  const res = await fetch("/api/dev/activity?session_id=" + encodeURIComponent(sessionId));
  if (!res.ok) return;
  const data = await res.json();
  const active = data.active_turn;
  const bubble = document.getElementById("processing");
  if (!active || !bubble) return;
  const lines = [
    active.message || "処理を続けています…",
    "Elapsed: " + formatElapsed(active.elapsed_seconds),
  ];
  if (active.current_goal) lines.push("Current Goal: " + active.current_goal);
  if (active.current_task) lines.push("Current Task: " + active.current_task);
  const body = bubble.querySelector(".body");
  if (body) body.textContent = lines.join("\n");
}

function startActivityHeartbeat() {
  stopActivityHeartbeat();
  refreshActivityBubble().catch(() => {});
  activityHeartbeat = setInterval(() => {
    refreshActivityBubble().catch(() => {});
  }, 1000);
}

function stopActivityHeartbeat() {
  if (activityHeartbeat !== null) {
    clearInterval(activityHeartbeat);
    activityHeartbeat = null;
  }
}

function setBusy(value) {
  busy = value;
  send.disabled = value;
  modelBtn.disabled = value;
  newChatBtn.disabled = value;
}

function setCurrentModel(name) {
  currentModel = name || "";
  currentModelEl.textContent = currentModel
    ? "使用モデル: " + currentModel
    : "使用モデル: （未選択）";
  modelBtn.textContent = currentModel || "モデル選択";
}

function setOllamaStatus(live) {
  ollamaStatus.classList.remove("bad");
  if (!live) {
    ollamaStatus.textContent = "";
    return;
  }
  if (!live.reachable) {
    ollamaStatus.classList.add("bad");
    ollamaStatus.textContent = live.user_error || live.user_message || "Ollamaに接続できません";
    return;
  }
  if (!(live.models || []).length) {
    ollamaStatus.classList.add("bad");
    ollamaStatus.textContent = live.user_error || live.user_message || "利用可能なLLMモデルがありません";
    return;
  }
  ollamaStatus.textContent = "Ollama 接続中　" + (live.models || []).length + " モデル";
}

function setCaps(caps) {
  if (!caps) {
    capsEl.textContent = "";
    return;
  }
  const tools = (caps.tools || []).join(", ");
  capsEl.textContent =
    "利用可能な Tool: " + tools + "　（存在 ≠ 実行。Search Tool available）";
}

function setMeta(session) {
  if (!session) {
    meta.textContent = "Session: 未開始";
    return;
  }
  meta.textContent =
    "Session " +
    session.session_id +
    "　開始 " +
    (session.started_at || "") +
    "　Cursor 未接続　ResearchRecord 自動保存なし";
}

function renderModelMenu(models, selected) {
  modelMenu.innerHTML = "";
  (models || []).forEach((name) => {
    const li = document.createElement("li");
    li.textContent = name;
    li.dataset.model = name;
    if (name === selected) li.classList.add("current");
    li.addEventListener("click", () => selectModel(name));
    modelMenu.appendChild(li);
  });
}

function closeMenu() {
  modelMenu.classList.add("hidden");
  modelBtn.setAttribute("aria-expanded", "false");
}

function openMenu() {
  modelMenu.classList.remove("hidden");
  modelBtn.setAttribute("aria-expanded", "true");
}

function replayMessages(session) {
  logEl.innerHTML = "";
  const turns = session.turns || [];
  let turnIndex = 0;
  (session.messages || []).forEach((item) => {
    const role = item.role;
    if (role === "user") {
      addBubble("user", item.content);
    } else if (role === "assistant") {
      addBubble("agent", item.content, turns[turnIndex++] || null);
    } else if (role === "error") {
      addBubble("error", item.content, turns[turnIndex++] || null);
    } else if (role === "notice") {
      addBubble("notice", item.content);
    }
  });
}

async function loadModels() {
  const res = await fetch("/api/models");
  const data = await res.json();
  availableModels = data.models || [];
  setOllamaStatus(data);
  setCaps(data.capabilities);
  renderModelMenu(availableModels, currentModel);
  return data;
}

async function ensureSession(options = {}) {
  const shouldReplay = Boolean(options.replay) || (!historyLoaded && options.replay !== false);
  if (sessionId) {
    const res = await fetch("/api/session/" + encodeURIComponent(sessionId));
    const data = await res.json();
    if (data.ok && data.session) {
      setMeta(data.session);
      setCurrentModel(data.session.model || "");
      if (data.models) {
        availableModels = data.models.models || availableModels;
        setOllamaStatus(data.models);
        renderModelMenu(availableModels, currentModel);
      }
      if (data.capabilities) setCaps(data.capabilities);
      if (shouldReplay) {
        replayMessages(data.session);
        historyLoaded = true;
      }
      return data.session;
    }
  }
  const res = await fetch("/api/session", { method: "POST", body: "{}" });
  const data = await res.json();
  sessionId = data.session.session_id;
  localStorage.setItem("localAgentSessionId", sessionId);
  setMeta(data.session);
  setCurrentModel(data.session.model || "");
  if (data.models) {
    availableModels = data.models.models || [];
    setOllamaStatus(data.models);
    renderModelMenu(availableModels, currentModel);
  }
  if (data.capabilities) setCaps(data.capabilities);
  if (shouldReplay) {
    logEl.innerHTML = "";
    historyLoaded = true;
  }
  return data.session;
}

async function selectModel(name) {
  closeMenu();
  if (!name || name === currentModel || busy) return;
  await ensureSession();
  const res = await fetch("/api/session/model", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, model: name }),
  });
  const data = await res.json();
  if (!data.ok) {
    addBubble("error", data.user_error || data.error || "モデルを変更できませんでした");
    setOllamaStatus(data.models || data);
    return;
  }
  setCurrentModel(data.model);
  setMeta(data.session);
  renderModelMenu(availableModels, currentModel);
  if (data.notice) addBubble("notice", data.notice);
}

async function startNewChat() {
  if (busy) return;
  const res = await fetch("/api/session", { method: "POST", body: "{}" });
  const data = await res.json();
  sessionId = data.session.session_id;
  localStorage.setItem("localAgentSessionId", sessionId);
  logEl.innerHTML = "";
  historyLoaded = true;
  lastTurn = null;
  renderProcessing();
  setMeta(data.session);
  setCurrentModel(data.session.model || currentModel);
  if (data.models) {
    availableModels = data.models.models || availableModels;
    setOllamaStatus(data.models);
    renderModelMenu(availableModels, currentModel);
  }
  addBubble("notice", "新しいチャットを開始しました");
}

modelBtn.addEventListener("click", async (ev) => {
  ev.stopPropagation();
  if (modelMenu.classList.contains("hidden")) {
    await loadModels();
    renderModelMenu(availableModels, currentModel);
    openMenu();
  } else {
    closeMenu();
  }
});

document.addEventListener("click", (ev) => {
  if (!modelMenu.contains(ev.target) && ev.target !== modelBtn) closeMenu();
});

newChatBtn.addEventListener("click", () => {
  startNewChat().catch((err) => addBubble("error", "通信エラー: " + err));
});

let composing = false;
let suppressEnterOnce = false;

function isImeConfirmKey(ev) {
  return (
    composing ||
    ev.isComposing ||
    ev.keyCode === 229 ||
    ev.key === "Process" ||
    suppressEnterOnce
  );
}

input.addEventListener("compositionstart", () => {
  composing = true;
});
input.addEventListener("compositionend", () => {
  composing = false;
  suppressEnterOnce = true;
  setTimeout(() => {
    suppressEnterOnce = false;
  }, 0);
});

async function submitMessage() {
  const text = input.value.trim();
  if (!text || busy) return;
  input.value = "";
  addBubble("user", text);
  addBubble("processing", "処理中…");
  setBusy(true);
  try {
    await ensureSession({ replay: false });
    if (testMode.checked) {
      await startAgentTestBatch(text);
      removeProcessing();
      addBubble("notice", "Test Batchが完了しました。Test Resultを確認してください。");
      return;
    }
    startActivityHeartbeat();
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text }),
    });
    const data = await res.json();
    removeProcessing();
    if (data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem("localAgentSessionId", sessionId);
    }
    if (data.session) setMeta(data.session);
    if (data.model) setCurrentModel(data.model);
    if (data.is_error || !data.ok) {
      const statusReport = data.turn && data.turn.runtime_status_report;
      addBubble(
        "error",
        (statusReport && statusReport.markdown) || data.user_error || data.error || "エラーが発生しました",
        data.turn
      );
      return;
    }
    if (data.turn && data.turn.development_job) {
      const job = data.turn.development_job;
      addBubble(
        "notice",
        "開発依頼として記録しました（Job " + job.id + "）。Cursor には接続していません。"
      );
    }
    addBubble("agent", data.turn.answer || "（空の回答）", data.turn);
    if (workspace === "development") loadCases();
  } catch (err) {
    removeProcessing();
    addBubble("error", "通信エラー: " + err);
  } finally {
    stopActivityHeartbeat();
    setBusy(false);
    input.focus();
  }
}

input.addEventListener("keydown", (ev) => {
  if (ev.key !== "Enter") return;
  if (isImeConfirmKey(ev)) return;
  if (ev.shiftKey) return;
  ev.preventDefault();
  submitMessage();
});

function selectedTestRuns() {
  const selected = document.querySelector('input[name="testRuns"]:checked');
  return Number(selected ? selected.value : 1);
}

function renderTestBatchResult(result) {
  const aggregate = result.aggregate || {};
  const markdown = result.aggregate_markdown || "";
  const runs = result.runs || [];
  const runReports = runs.map((item, index) =>
    `<section class="test-run-result"><h4>Run ${index + 1}: ${escapeHtml(item.record.run_id)} — ${escapeHtml(item.record.status)}</h4>` +
    `<div class="test-run-human-summary"><h5>日本語要約</h5>` +
    `<button type="button" class="copy-report" data-copy="run-human-${index}">日本語要約をコピー</button>` +
    `<pre id="run-human-${index}">${escapeHtml(item.human_summary_markdown || "")}</pre></div>` +
    `<details class="test-run-report"><summary>詳細ログ</summary>` +
    `<button type="button" class="copy-report" data-copy="run-${index}">詳細ログをコピー</button>` +
    `<pre id="run-${index}">${escapeHtml(item.markdown || "")}</pre></details></section>`
  ).join("");
  testResults.innerHTML =
    `<h3>テスト完了</h3>` +
    `<p>Runs: ${escapeHtml(aggregate.total_runs)} / Completed: ${escapeHtml(aggregate.completed_runs)} / ` +
    `Tool Used: ${escapeHtml(aggregate.tool_used_runs)} / Empty Answer: ${escapeHtml(aggregate.empty_answer_count)} / ` +
    `Completion Consistency FAIL: ${escapeHtml(aggregate.completion_consistency_failures)}</p>` +
    `<p>Reports: ${escapeHtml(result.output_directory || "")}</p>` +
    `<button type="button" class="copy-report" data-copy="aggregateReport">Aggregate Markdownをコピー</button>` +
    `<pre id="aggregateReport">${escapeHtml(markdown)}</pre>` + runReports;
}

async function pollTestBatch() {
  if (!testBatchJobId) return;
  const res = await fetch("/api/test-batches/" + encodeURIComponent(testBatchJobId));
  const data = await res.json();
  const job = data.job;
  if (!data.ok || !job) throw new Error(data.error || "Batch状態を取得できませんでした");
  const activity = job.current_activity || {};
  const completed = (job.run_statuses || []).map((row) =>
    `Run ${row.index} / ${job.total} ${String(row.status).toUpperCase()}`
  );
  testProgress.textContent = [
    job.status === "running" ? "テスト実行中" : "テスト完了",
    `${job.current} / ${job.total}`,
    `現在のRun: ${job.current_run_id || "-"}`,
    `状態: ${activity.message || job.status}`,
    ...completed,
  ].join("\n");
  if (job.status === "running") return;
  if (job.status === "completed") renderTestBatchResult(job.result || {});
  else testResults.textContent = job.error || "Batch実行に失敗しました";
  return job.status;
}

async function startAgentTestBatch(prompt) {
  if (testBatchTimer !== null) return;
  testBatchTimer = "running";
  testModeStatus.textContent = `TEST MODE ON — 同じメッセージを${selectedTestRuns()}回実行中`;
  testResults.innerHTML = "";
  try {
    const res = await fetch("/api/test-batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: prompt,
        runs: selectedTestRuns(),
        model: currentModel || null,
      }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Batchを開始できませんでした");
    testBatchJobId = data.job.job_id;
    while (true) {
      const status = await pollTestBatch();
      if (status && status !== "running") break;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  } catch (err) {
    testProgress.textContent = "エラー: " + err;
    throw err;
  } finally {
    testBatchTimer = null;
    testModeStatus.textContent = testMode.checked
      ? `TEST MODE ON — 同じメッセージを${selectedTestRuns()}回実行します`
      : "TEST MODE OFF";
  }
}

testMode.addEventListener("change", () => {
  testModeStatus.textContent = testMode.checked
    ? `TEST MODE ON — 同じメッセージを${selectedTestRuns()}回実行します`
    : "TEST MODE OFF";
});
testResults.addEventListener("click", (event) => {
  const button = event.target.closest(".copy-report");
  if (!button) return;
  const source = document.getElementById(button.getAttribute("data-copy"));
  if (source) navigator.clipboard.writeText(source.textContent || "");
});

form.addEventListener("submit", (ev) => {
  ev.preventDefault();
  submitMessage();
});

Promise.all([loadModels(), ensureSession()]).catch((err) => {
  addBubble("error", "初期化に失敗しました: " + err);
});
input.focus();

const processingBody = document.getElementById("processingBody");
const cursorLiveEl = document.getElementById("cursorLive");
const timelineBody = document.getElementById("timelineBody");
const caseFilterEl = document.getElementById("caseFilter");
const caseBack = document.getElementById("caseBack");
const timelineReload = document.getElementById("timelineReload");
const wsTabs = document.getElementById("wsTabs");
const devPanel = document.getElementById("devPanel");

function setWorkspace(name) {
  workspace = name;
  ["chat", "processing", "development"].forEach((id) => {
    const el = document.getElementById("ws" + id.charAt(0).toUpperCase() + id.slice(1));
    if (el) el.classList.toggle("hidden", id !== name);
  });
  [...wsTabs.querySelectorAll("button")].forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.ws === name);
  });
  if (name === "processing") {
    renderProcessing();
    loadMatrixLast();
    loadMatrixVerify();
    loadMatrixTrace();
    loadMatrixAsk();
    loadSpecLast();
  }
  if (name === "development") loadCases();
}

function renderProcessing() {
  if (!processingBody) return;
  if (!lastTurn) {
    processingBody.innerHTML = "<p>まだ処理がありません。</p>";
    return;
  }
  processingBody.innerHTML =
    `<p class="dev-sep">Processing / Local Agent　intent: ${escapeHtml(lastTurn.intent || lastTurn.route || "")}　case: ${escapeHtml(lastTurn.case_id || "（なし）")}</p>` +
    renderPipeline(lastTurn) +
    renderRuntimeSummary(lastTurn) +
    `<ol class="steps">${renderSteps(lastTurn)}</ol>`;
}

function layerClass(layer) {
  if (layer === "real") return "tl-layer-real";
  if (layer === "cursor_report") return "tl-layer-cursor_report";
  if (layer === "summary") return "tl-layer-summary";
  return "tl-layer-ui";
}

function actorLine(ev) {
  const actor = (ev.actor || "").toUpperCase() || "UNKNOWN";
  const source = (ev.source || "").toUpperCase() || "UNKNOWN";
  return `[ACTOR: ${escapeHtml(actor)}] [SOURCE: ${escapeHtml(source)}]`;
}

function actorMeta(ev) {
  const actor = (ev.actor || "").toUpperCase() || "UNKNOWN";
  const source = (ev.source || "").toUpperCase() || "UNKNOWN";
  const req = (ev.requested_by || "").toUpperCase();
  const exe = (ev.executed_by || "").toUpperCase();
  const model = ev.model ? `　Model: ${escapeHtml(ev.model)}` : "";
  const who = req && exe ? `　requested_by: ${escapeHtml(req)}　executed_by: ${escapeHtml(exe)}` : "";
  return `[ACTOR: ${escapeHtml(actor)}] [SOURCE: ${escapeHtml(source)}]${who}${model}`;
}

function renderActivityEvents(events) {
  if (!events || !events.length) {
    return "<p>Local Agent Tool Call: NONE（この Session では未観測）</p>";
  }
  return events
    .map((ev) => {
      const extra = [];
      if (ev.query) extra.push("query: " + escapeHtml(ev.query));
      if (ev.hit_count != null) extra.push("hit_count: " + escapeHtml(ev.hit_count));
      if (ev.search_index != null) extra.push("search_index: " + escapeHtml(ev.search_index));
      if (ev.backends_tried && ev.backends_tried.length) extra.push("backends: " + escapeHtml(ev.backends_tried.join(", ")));
      if (ev.web_status_overall) extra.push("web_status: " + escapeHtml(ev.web_status_overall));
      if (ev.name) extra.push("tool: " + escapeHtml(ev.name));
      if (ev.status) extra.push("status: " + escapeHtml(ev.status));
      if (ev.sections && ev.sections.length) extra.push("sections: " + escapeHtml(ev.sections.join(", ")));
      if (ev.record_ids && ev.record_ids.length) extra.push("record_ids: " + escapeHtml(ev.record_ids.join(", ")));
      if (ev.draft_count != null) extra.push("draft_count: " + escapeHtml(ev.draft_count));
      if (ev.count != null && ev.type && String(ev.type).indexOf("matrix") === 0) extra.push("count: " + escapeHtml(ev.count));
      if (ev.summary && typeof ev.summary === "object") {
        extra.push("<pre class=\"obs\">" + escapeHtml(formatObservation(ev.summary, 0)) + "</pre>");
      }
      if (ev.body) extra.push(escapeHtml(ev.body));
      if (ev.proposal_id) extra.push("proposal_id: " + escapeHtml(ev.proposal_id));
      if (ev.request_id) extra.push("request_id: " + escapeHtml(ev.request_id));
      if (ev.development_job_id) extra.push("job: " + escapeHtml(ev.development_job_id));
      if (ev.case_id) extra.push("case: " + escapeHtml(ev.case_id));
      if (ev.correlation_id) extra.push("correlation: " + escapeHtml(ev.correlation_id));
      return (
        `<div class="tl-item ${layerClass(ev.layer || "real")}">` +
        `<div class="tl-meta">${escapeHtml(ev.timestamp || "")}　${actorMeta(ev)}</div>` +
        `<div class="tl-title">[${escapeHtml(ev.type || "")}] ${escapeHtml(ev.title || "")}</div>` +
        (extra.length ? `<div>${extra.join("　")}</div>` : "") +
        `</div>`
      );
    })
    .join("");
}

function renderCaseList(data) {
  const live = data.cursor_live || {};
  cursorLiveEl.textContent = live.label || "Cursor live status: NOT OBSERVED";
  caseBack.classList.add("hidden");
  selectedCaseId = "";
  const cases = data.cases || [];
  const jobs = data.chat_jobs || [];
  const activity = data.local_agent_activity || {};
  const cards = cases
    .map((c) => {
      const req = c.request_status === "missing" ? "依頼文：未取得" : "依頼あり";
      return (
        `<button type="button" class="case-card" data-case="${escapeHtml(c.id)}">` +
        `<div>${escapeHtml(c.title || c.id)}</div>` +
        `<div class="case-meta">actor: ${escapeHtml(c.actor || "")}　kind: ${escapeHtml(c.kind || "unknown")}　${escapeHtml(c.status || "")}　${req}</div>` +
        `</button>`
      );
    })
    .join("");
  const jobNotes = jobs
    .map((j) => {
      const pid = j.proposal_id || "";
      const rid = j.request_id || "";
      const idLine = pid
        ? `proposal_id: <button type="button" class="linkish" data-proposal="${escapeHtml(pid)}">${escapeHtml(pid)}</button>`
        : "proposal_id: （なし）";
      return (
        `<li>${escapeHtml(j.title || j.id)}　[ACTOR: LOCAL_AGENT] [SOURCE: SESSION]　Chat依頼（Cursor実行の証明ではない）` +
        `<div class="case-meta">job: ${escapeHtml(j.id || "")}　${idLine}　request_id: ${escapeHtml(rid || "（なし）")}</div>` +
        `<div class="proposal-ref"></div></li>`
      );
    })
    .join("");
  const bridge = `Cursor → Local Agent: ${escapeHtml(activity.cursor_to_local_agent || "NOT_CONNECTED")}`;
  const research = `Research: ${escapeHtml(activity.research_path || "NOT_CONNECTED")}`;
  const matrix = `Matrix Write: ${escapeHtml(activity.matrix_write || "NOT_OBSERVED")}`;
  timelineBody.innerHTML =
    `<p class="dev-sep">開発案件一覧</p>` +
    (cards || "<p>案件はありません。</p>") +
    (jobNotes ? `<p class="dev-sep">Chat UI で記録した依頼</p><ul class="dev-list">${jobNotes}</ul>` : "") +
    `<p class="dev-sep">Local Agent 処理（この Session）</p>` +
    `<p class="case-meta">${bridge}　${research}　${matrix}</p>` +
    `<p class="case-meta">${escapeHtml(activity.note || "")}</p>` +
    renderActivityEvents(activity.events || []);
  timelineBody.querySelectorAll("[data-case]").forEach((btn) => {
    btn.addEventListener("click", () => showCase(btn.getAttribute("data-case")));
  });
  timelineBody.querySelectorAll("[data-proposal]").forEach((btn) => {
    btn.addEventListener("click", () => openProposalRef(btn));
  });
}

async function openProposalRef(btn) {
  const pid = btn.getAttribute("data-proposal") || "";
  const slot = btn.closest("li") ? btn.closest("li").querySelector(".proposal-ref") : null;
  if (!pid || !slot) return;
  slot.textContent = "参照中…";
  try {
    const res = await fetch("/api/spec/proposal?proposal_id=" + encodeURIComponent(pid));
    const data = await res.json();
    if (!data.found || !data.proposal) {
      slot.textContent = "JSONL に該当 proposal_id が無い。レコードは作っていない。";
      return;
    }
    const p = data.proposal;
    slot.textContent =
      "参照: origin=" +
      (p.origin || "NOT_OBSERVED") +
      " request_id=" +
      (p.request_id || "") +
      " parent=" +
      (p.parent_proposal_id || "（なし）") +
      " version=" +
      String(p.version) +
      "（JSONL 読取。上書きしていない）";
  } catch (_err) {
    slot.textContent = "参照に失敗しました";
  }
}

function observedLines(it) {
  const observed = it.observed || {};
  const keys = Object.keys(observed).filter((k) => k !== "status" && k !== "judgment" && k !== "result");
  if (!keys.length) {
    return `<p>詳細: 未取得</p>`;
  }
  return keys
    .map((k) => {
      const val = observed[k];
      const text = typeof val === "string" || typeof val === "number" || typeof val === "boolean"
        ? String(val)
        : JSON.stringify(val);
      return `<p>${escapeHtml(k)}: ${escapeHtml(text)}</p>`;
    })
    .join("");
}

function renderTestItem(it) {
  const id = it.id || "";
  return (
    `<button type="button" class="test-item" data-open-test="${escapeHtml(id)}">` +
    `<div class="tl-title">${escapeHtml(id)}</div>` +
    `<div>${escapeHtml(it.status || "UNKNOWN")}</div>` +
    `<div class="case-meta">Source: Cursor Report　Actor: CURSOR</div>` +
    `</button>`
  );
}

function renderTestDetails(data, focusId) {
  const live = data.cursor_live || {};
  cursorLiveEl.textContent = live.label || "Cursor live status: NOT OBSERVED";
  caseBack.classList.remove("hidden");
  const c = data.case || {};
  const claim = c.cursor_report && c.cursor_report.text ? escapeHtml(c.cursor_report.text) : "未取得";
  const mech = c.mechanical_tests || {};
  const items = c.cursor_tests || [];
  const focus = focusId ? items.find((it) => it.id === focusId) : null;
  let focusHtml = "";
  if (focusId && !focus) {
    focusHtml = `<div class="detail-block"><h3>${escapeHtml(focusId)}</h3><p>詳細: 未取得</p><p class="case-meta">Source: Cursor Report　Actor: CURSOR</p></div>`;
  } else if (focus) {
    focusHtml =
      `<div class="detail-block">` +
      `<h3>${escapeHtml(focus.id)}</h3>` +
      `<p>${escapeHtml(focus.status || "UNKNOWN")}</p>` +
      `<p class="case-meta">Source: Cursor Report　Actor: CURSOR</p>` +
      observedLines(focus) +
      `</div>`;
  }
  const list = items.length
    ? items.map(renderTestItem).join("")
    : `<p>個別テスト項目: 未取得</p>`;
  timelineBody.innerHTML =
    `<div class="detail-block"><h3>Test Details</h3>` +
    `<p><button type="button" class="linkish" id="testBackToCase">案件へ戻る</button></p>` +
    `<p>[CURSOR REPORT] ${claim}</p>` +
    `<p class="case-meta">Source: Cursor Report　Actor: CURSOR　機械的 pytest 結果ではありません。</p>` +
    `</div>` +
    focusHtml +
    `<div class="detail-block"><h3>Cursor Report テスト一覧</h3>${list}</div>` +
    `<div class="detail-block"><h3>Machine Test</h3>` +
    `<p>[MACHINE TEST] ${escapeHtml(mech.status === "NOT_AVAILABLE" ? "NOT AVAILABLE" : (mech.status || "NOT AVAILABLE"))}</p>` +
    `<p class="case-meta">Source: ${escapeHtml(mech.source || "missing")}　Actor: MECHANICAL</p>` +
    `<p>${escapeHtml(mech.user_message || "機械的テスト結果：未取得")}</p>` +
    `<p>Cursor Report の PASS を機械結果として使いません。</p>` +
    `</div>`;
  const back = document.getElementById("testBackToCase");
  if (back) back.addEventListener("click", () => renderCaseDetail(data));
  bindTestDetailButtons(data);
}

function bindTestDetailButtons(data) {
  timelineBody.querySelectorAll("[data-open-tests]").forEach((btn) => {
    btn.addEventListener("click", () => renderTestDetails(data, null));
  });
  timelineBody.querySelectorAll("[data-open-test]").forEach((btn) => {
    btn.addEventListener("click", () => renderTestDetails(data, btn.getAttribute("data-open-test")));
  });
}

function renderCaseDetail(data) {
  lastCasePayload = data;
  const live = data.cursor_live || {};
  cursorLiveEl.textContent = live.label || "Cursor live status: NOT OBSERVED";
  caseBack.classList.remove("hidden");
  const c = data.case || {};
  const repo = data.repository_status || {};
  const bridge = data.local_agent_bridge || {};
  const req = c.request
    ? escapeHtml(c.request)
    : "依頼文：未取得" + (c.title_source === "run_id_slug" ? `　（Run名から推定される案件名: ${escapeHtml(c.slug || "")}）` : "");
  const reports = (c.reports || [])
    .map((r) => `<li><button type="button" class="linkish" data-open-report="${escapeHtml(r.name)}">${escapeHtml(r.name)}</button>　[開く]</li>`)
    .join("");
  const files = ((c.related_git || {}).files || [])
    .map((f) => {
      const mark = f.state === "added" ? "+" : f.state === "modified" ? "M" : (f.state || "?");
      return `<li>${escapeHtml(mark)} ${escapeHtml(f.path || "")}</li>`;
    })
    .join("");
  const tests = (c.cursor_tests || [])
    .map((it) => `<li><button type="button" class="linkish" data-open-test="${escapeHtml(it.id)}">${escapeHtml(it.id)}　${escapeHtml(it.status)}</button></li>`)
    .join("");
  const claim = c.cursor_report && c.cursor_report.text ? escapeHtml(c.cursor_report.text) : "未取得";
  const hasTests = Boolean((c.cursor_tests || []).length || (c.cursor_report && c.cursor_report.text));
  const mech = c.mechanical_tests || {};
  const events = (c.events || [])
    .map((ev) => {
      const items = (ev.items || [])
        .map((it) => `<li><button type="button" class="linkish" data-open-test="${escapeHtml(it.id)}">${escapeHtml(it.id)}　${escapeHtml(it.status)}</button></li>`)
        .join("");
      const openTests = ev.type === "CURSOR_REPORT" || ev.type === "TEST";
      const title = openTests
        ? `<button type="button" class="linkish" data-open-tests="1">[${escapeHtml(ev.type || "")}] ${escapeHtml(ev.title || "")}</button>`
        : `[${escapeHtml(ev.type || "")}] ${escapeHtml(ev.title || "")}`;
      const body = ev.body
        ? (openTests
          ? `<div><button type="button" class="linkish" data-open-tests="1">${escapeHtml(ev.body)}</button></div>`
          : `<div>${escapeHtml(ev.body)}</div>`)
        : "";
      return (
        `<div class="tl-item ${layerClass(ev.layer)}">` +
        `<div class="tl-meta">${escapeHtml(ev.timestamp || "")}　${actorLine(ev)}</div>` +
        `<div class="tl-title">${title}</div>` +
        body +
        (items ? `<ul class="tl-items">${items}</ul>` : "") +
        `</div>`
      );
    })
    .join("");
  timelineBody.innerHTML =
    `<div class="detail-block"><h3>案件</h3><p>${escapeHtml(c.title || "")}</p></div>` +
    `<div class="detail-block"><h3>実行主体</h3><p>${escapeHtml((c.actor || "").toUpperCase())}　confidence: ${escapeHtml(c.confidence || "observed")}</p></div>` +
    `<div class="detail-block"><h3>Cursor → Local Agent</h3><p>${escapeHtml(bridge.cursor_to_local_agent || "NOT_CONNECTED")}</p>` +
    `<p>Local Agent Tool Call: ${escapeHtml(bridge.local_agent_tool_call || "NONE")}</p>` +
    `<p>Research: ${escapeHtml(bridge.research_path || "NOT_CONNECTED")}</p>` +
    `<p>Matrix Write: ${escapeHtml(bridge.matrix_write || "NOT_OBSERVED")}</p>` +
    `<p class="case-meta">${escapeHtml(bridge.note || "")}</p></div>` +
    `<div class="detail-block"><h3>状態</h3><p>${escapeHtml(c.status || "UNKNOWN")}` +
    (hasTests ? `　<button type="button" class="linkish" data-open-tests="1">[Test詳細]</button>` : "") +
    `</p><p>${escapeHtml(c.judgment_ja || "")}</p></div>` +
    `<div class="detail-block"><h3>開発依頼</h3><p>${req}</p></div>` +
    `<div class="detail-block"><h3>Development Timeline</h3>${events || "<p>確認できた成果物はありません。</p>"}</div>` +
    `<div class="detail-block"><h3>変更ファイル（この案件）</h3>` +
    (files ? `<ul class="dev-list">${files}</ul>` : `<p>${escapeHtml((c.related_git || {}).note || "未取得")}</p>`) +
    `</div>` +
    `<div class="detail-block"><h3>Repository Status</h3><p>modified: ${repo.modified ?? "—"}　added: ${repo.added ?? "—"}　deleted: ${repo.deleted ?? "—"}　untracked: ${repo.untracked ?? "—"}</p><p class="dev-sep">${escapeHtml(repo.note || "")}</p></div>` +
    `<div class="detail-block"><h3>Run</h3><p><button type="button" class="linkish" data-open-run="${escapeHtml(c.run_id || "")}">${escapeHtml(c.run_id || "未取得")}</button>　[詳細]</p></div>` +
    `<div class="detail-block"><h3>Report</h3>${reports ? `<ul class="dev-list">${reports}</ul>` : "<p>未取得</p>"}</div>` +
    `<div class="detail-block"><h3>Git</h3><p>変更ファイル ${((c.related_git || {}).files || []).length}　<button type="button" class="linkish" data-open-tab="git">[詳細]</button></p></div>` +
    `<div class="detail-block"><h3>Test</h3>` +
    `<p>テスト結果　<button type="button" class="linkish" data-open-tests="1">[CURSOR REPORT] ${claim}</button>　[詳細を見る]</p>` +
    `<p>[MACHINE TEST] ${escapeHtml(mech.status === "NOT_AVAILABLE" ? "NOT AVAILABLE" : (mech.status || "NOT AVAILABLE"))}</p>` +
    (tests ? `<p class="dev-sep">Cursor Report テスト一覧</p><ul class="dev-list">${tests}</ul>` : "") +
    `<p><button type="button" class="linkish" data-open-tab="test">機械Testパネル</button></p>` +
    `</div>` +
    `<p class="dev-sep">${escapeHtml(c.note || "")}</p>`;
  timelineBody.querySelectorAll("[data-open-run]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-open-run");
      if (!id) return;
      openDevPanelThen(() => showRun(id));
    });
  });
  timelineBody.querySelectorAll("[data-open-report]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openDevPanelThen(() => showReport(btn.getAttribute("data-open-report")));
    });
  });
  timelineBody.querySelectorAll("[data-open-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openDevPanelThen(() => loadDevTab(btn.getAttribute("data-open-tab")));
    });
  });
  bindTestDetailButtons(data);
}

function openDevPanelThen(fn) {
  skipPanelAutoload = true;
  document.getElementById("devPanel").open = true;
  const result = fn();
  Promise.resolve(result).finally(() => {
    window.setTimeout(() => {
      skipPanelAutoload = false;
    }, 400);
  });
  return result;
}

async function loadCases() {
  if (!timelineBody) return;
  timelineBody.textContent = "読み込み中…";
  const params = new URLSearchParams();
  params.set("filter", caseFilter || "all");
  if (sessionId) params.set("session_id", sessionId);
  const res = await fetch("/api/dev/cases?" + params.toString());
  const data = await res.json();
  renderCaseList(data);
}

async function showCase(caseId) {
  selectedCaseId = caseId;
  timelineBody.textContent = "読み込み中…";
  const res = await fetch("/api/dev/cases/" + encodeURIComponent(caseId));
  const data = await res.json();
  if (!data.ok) {
    timelineBody.innerHTML = `<p class="err">${escapeHtml(data.error || "案件を読めません")}</p>`;
    return;
  }
  renderCaseDetail(data);
}

function loadTimeline() {
  if (selectedCaseId) return showCase(selectedCaseId);
  return loadCases();
}

wsTabs.addEventListener("click", (ev) => {
  const btn = ev.target.closest("button[data-ws]");
  if (!btn) return;
  setWorkspace(btn.dataset.ws);
});

caseFilterEl.addEventListener("change", () => {
  caseFilter = caseFilterEl.value || "all";
  selectedCaseId = "";
  loadCases().catch((err) => {
    timelineBody.innerHTML = `<p class="err">${escapeHtml(err)}</p>`;
  });
});

caseBack.addEventListener("click", () => {
  selectedCaseId = "";
  loadCases().catch((err) => {
    timelineBody.innerHTML = `<p class="err">${escapeHtml(err)}</p>`;
  });
});

timelineReload.addEventListener("click", () => {
  loadTimeline().catch((err) => {
    timelineBody.innerHTML = `<p class="err">${escapeHtml(err)}</p>`;
  });
});
const devBody = document.getElementById("devBody");
const devTabs = document.getElementById("devTabs");
let devTab = "run";
let devLoaded = false;

function setDevHtml(html) {
  devBody.innerHTML = html;
}

async function loadDevTab(tab) {
  devTab = tab;
  [...devTabs.querySelectorAll("button")].forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  setDevHtml("読み込み中…");
  try {
    if (tab === "run") await renderRuns();
    else if (tab === "report") await renderReports();
    else if (tab === "git") await renderGit();
    else await renderTests();
  } catch (err) {
    setDevHtml(`<p class="err">読み取りに失敗しました: ${escapeHtml(err)}</p>`);
  }
}

async function renderRuns() {
  const res = await fetch("/api/dev/runs");
  const data = await res.json();
  const runs = data.runs || [];
  if (!runs.length) {
    setDevHtml("<p>Run はありません。</p>");
    return;
  }
  const items = runs
    .map((r) => {
      const label = escapeHtml(r.run_id);
      const judge = escapeHtml(r.judgment || "（判定なし）");
      const ja = r.judgment_ja ? `<div class="dev-sep">${escapeHtml(r.judgment_ja)}</div>` : "";
      return `<li><button type="button" class="linkish" data-run="${label}">${label}</button>　${judge}${ja}</li>`;
    })
    .join("");
  setDevHtml(
    `<p class="dev-sep">Development / Run　source: ${escapeHtml(data.source || "")}</p>` +
      `<ul class="dev-list">${items}</ul>`
  );
  devBody.querySelectorAll("[data-run]").forEach((btn) => {
    btn.addEventListener("click", () => showRun(btn.getAttribute("data-run")));
  });
}

async function showRun(runId) {
  devTab = "run";
  [...devTabs.querySelectorAll("button")].forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === "run");
  });
  setDevHtml("読み込み中…");
  const res = await fetch("/api/dev/runs/" + encodeURIComponent(runId));
  const data = await res.json();
  if (!data.ok) {
    setDevHtml(`<p class="err">${escapeHtml(data.error || "Run を読めません")}</p><p><button type="button" class="linkish" id="devBack">一覧へ戻る</button></p>`);
    document.getElementById("devBack").addEventListener("click", () => renderRuns());
    return;
  }
  const summary = data.summary || {};
  const mech = data.mechanical_tests || {};
  const claim = data.cursor_test_report;
  const tests = summary.tests ? `<pre class="dev-pre">${escapeHtml(JSON.stringify(summary.tests, null, 2))}</pre>` : "";
  const claimHtml = claim
    ? `<p>Cursor報告：${escapeHtml(claim.text)}</p><p class="dev-sep">${escapeHtml(claim.note || "")}</p>`
    : `<p>Cursor報告：この Run には unit_tests がありません</p>`;
  setDevHtml(
    `<p><button type="button" class="linkish" id="devBack">一覧へ戻る</button></p>` +
      `<p class="dev-sep">Development / Run</p>` +
      `<p>Run ID: ${escapeHtml(data.run_id)}</p>` +
      `<p>ファイル更新: ${escapeHtml(data.summary_mtime || "（なし）")}</p>` +
      `<p>判定: ${escapeHtml(summary.judgment || "（なし）")}</p>` +
      `<p>概要: ${escapeHtml(summary.judgment_ja || "（なし）")}</p>` +
      `<p>関連 Session: ${escapeHtml(summary.session_id || "（なし）")}</p>` +
      `<p>ファイル: ${escapeHtml((data.files || []).join(", "))}</p>` +
      tests +
      `<p class="dev-sep">Test</p>` +
      claimHtml +
      `<p>機械的テスト結果：${escapeHtml(mech.user_message || "未取得")}</p>`
  );
  document.getElementById("devBack").addEventListener("click", () => renderRuns());
}

async function renderReports() {
  const res = await fetch("/api/dev/reports");
  const data = await res.json();
  const reports = data.reports || [];
  if (!reports.length) {
    setDevHtml("<p>報告書はありません。</p>");
    return;
  }
  const items = reports
    .map((r) => `<li><button type="button" class="linkish" data-report="${escapeHtml(r.name)}">${escapeHtml(r.name)}</button></li>`)
    .join("");
  setDevHtml(`<p class="dev-sep">Development / Report</p><ul class="dev-list">${items}</ul>`);
  devBody.querySelectorAll("[data-report]").forEach((btn) => {
    btn.addEventListener("click", () => showReport(btn.getAttribute("data-report")));
  });
}

async function showReport(name) {
  devTab = "report";
  [...devTabs.querySelectorAll("button")].forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === "report");
  });
  setDevHtml("読み込み中…");
  const res = await fetch("/api/dev/reports/" + encodeURIComponent(name));
  const data = await res.json();
  if (!data.ok) {
    setDevHtml(`<p class="err">${escapeHtml(data.error || "報告書を読めません")}</p><p><button type="button" class="linkish" id="devBack">一覧へ戻る</button></p>`);
    document.getElementById("devBack").addEventListener("click", () => renderReports());
    return;
  }
  setDevHtml(
    `<p><button type="button" class="linkish" id="devBack">一覧へ戻る</button></p>` +
      `<p class="dev-sep">Development / Report　${escapeHtml(data.name)}</p>` +
      `<p class="dev-sep">${escapeHtml(data.note || "")}</p>` +
      `<pre class="dev-pre">${escapeHtml(data.text || "")}</pre>`
  );
  document.getElementById("devBack").addEventListener("click", () => renderReports());
}

async function renderGit() {
  const res = await fetch("/api/dev/git");
  const data = await res.json();
  if (!data.ok) {
    setDevHtml(`<p class="err">${escapeHtml(data.error || "git を読めません")}</p>`);
    return;
  }
  const counts = data.counts || {};
  const files = (data.files || [])
    .map((f) => `<li>${escapeHtml(f.state)}: ${escapeHtml(f.path)}</li>`)
    .join("");
  const trunc = data.files_truncated ? `<p class="dev-sep">ファイル一覧は一部省略しています</p>` : "";
  const commits = (data.commits || [])
    .slice(0, 10)
    .map((c) => `<li>${escapeHtml((c.hash || "").slice(0, 8))}　${escapeHtml(c.subject || "")}</li>`)
    .join("");
  setDevHtml(
    `<p class="dev-sep">Development / Git　読み取り専用</p>` +
      `<p>branch: ${escapeHtml(data.branch || "（不明）")}　HEAD: ${escapeHtml((data.head || "").slice(0, 12))}</p>` +
      `<p>modified: ${counts.modified || 0}　added: ${counts.added || 0}　deleted: ${counts.deleted || 0}　untracked: ${counts.untracked || 0}</p>` +
      `<p class="dev-sep">変更ファイル</p>` +
      trunc +
      `<ul class="dev-list">${files || "<li>（なし）</li>"}</ul>` +
      `<p class="dev-sep">最近の commit</p>` +
      `<ul class="dev-list">${commits || "<li>（なし）</li>"}</ul>` +
      `<p class="dev-sep">git diff --stat</p>` +
      `<pre class="dev-pre">${escapeHtml(data.diff_stat || "（差分なし）")}</pre>` +
      `<p class="dev-sep">git diff</p>` +
      `<pre class="dev-pre">${escapeHtml(data.diff || "（差分なし）")}</pre>`
  );
}

async function renderTests() {
  const res = await fetch("/api/dev/tests");
  const data = await res.json();
  const mech = data.mechanical_tests || {};
  const live = data.cursor_live || {};
  setDevHtml(
    `<p class="dev-sep">Development / Test</p>` +
      `<p>${escapeHtml(live.label || "Cursor live status: NOT OBSERVED")}</p>` +
      `<p>Cursor Report：Run 詳細の unit_tests があるときだけ別表示</p>` +
      `<p>Machine Test：${escapeHtml(mech.user_message || "NOT AVAILABLE")}</p>` +
      `<p>source: ${escapeHtml(mech.source || "missing")}</p>` +
      `<p class="dev-sep">${escapeHtml(data.note || "")}</p>`
  );
}

devTabs.addEventListener("click", (ev) => {
  const btn = ev.target.closest("button[data-tab]");
  if (!btn) return;
  loadDevTab(btn.dataset.tab);
});

devPanel.addEventListener("toggle", () => {
  if (devPanel.open && !skipPanelAutoload) {
    loadDevTab(devTab);
    devLoaded = true;
  }
});

const matrixPipeline = document.getElementById("matrixPipeline");
const matrixSearchResult = document.getElementById("matrixSearchResult");
const matrixVerify = document.getElementById("matrixVerify");
const matrixTrace = document.getElementById("matrixTrace");
const matrixAskResult = document.getElementById("matrixAskResult");
const matrixIngestBtn = document.getElementById("matrixIngest");
const matrixSearchBtn = document.getElementById("matrixSearch");
const matrixAttrSearchBtn = document.getElementById("matrixAttrSearch");
const matrixAskBtn = document.getElementById("matrixAsk");
const matrixQueryEl = document.getElementById("matrixQuery");
const matrixSearchQEl = document.getElementById("matrixSearchQ");
const matrixEntityEl = document.getElementById("matrixEntity");
const matrixAttributeEl = document.getElementById("matrixAttribute");
const matrixAskQEl = document.getElementById("matrixAskQ");
const matrixAskFallbackEl = document.getElementById("matrixAskFallback");
const matrixAskLlmEl = document.getElementById("matrixAskLlm");
const specBody = document.getElementById("specBody");
const specRequestEl = document.getElementById("specRequest");
const specProposeBtn = document.getElementById("specPropose");
const specParentIdEl = document.getElementById("specParentId");
const specRevisionReasonEl = document.getElementById("specRevisionReason");
const specReviseBtn = document.getElementById("specRevise");
const specProblemEl = document.getElementById("specProblem");
const specProblemBtn = document.getElementById("specProblemBtn");

function matrixEventLabel(type) {
  if (type === "question") return "USER";
  if (type === "matrix_search") return "MATRIX_SEARCH";
  if (type === "sufficient") return "SUFFICIENT";
  if (type === "insufficient") return "INSUFFICIENT";
  if (type === "ingest_skip") return "INGEST_SKIP";
  if (type === "llm") return "LLM";
  if (type === "answer") return "FINAL_ANSWER";
  if (type === "search") return "SEARCH";
  if (type === "fetch") return "FETCH";
  if (type === "extract") return "EXTRACT";
  if (type === "normalize") return "NORMALIZE";
  if (type === "entity_source_check") return "ENTITY/SOURCE VALIDATION";
  if (type === "matrix_write") return "MATRIX_WRITE";
  if (type === "matrix_result") return "MATRIX_RESULT";
  if (type === "matrix_record") return "MATRIX_RECORD";
  if (type === "matrix_verify") return "MATRIX_VERIFY";
  if (type === "verify_result") return "VERIFY";
  return String(type || "").toUpperCase();
}

function renderMatrixRecord(row) {
  if (!row) return "";
  const lines = [
    "record_id: " + (row.record_id || ""),
    "entity: " + (row.entity || ""),
    "attribute: " + (row.attribute || ""),
    "value: " + (row.value || ""),
    "source: " + (row.source_title || ""),
    "source_url: " + (row.source_url || ""),
    "observed_at: " + (row.observed_at || ""),
    "provenance: " + (row.provenance || ""),
  ];
  const openSrc = row.source_url
    ? `<a href="${escapeHtml(row.source_url)}" target="_blank" rel="noopener noreferrer">出典ページを開く</a>`
    : "<span>出典ページ: NOT_AVAILABLE</span>";
  const verifyBtn = row.record_id
    ? `<button type="button" data-verify="${escapeHtml(row.record_id)}">照合する</button>` +
      `<button type="button" data-trace="${escapeHtml(row.record_id)}">経路を追跡</button>`
    : "";
  return (
    `<pre class="matrix-record">${escapeHtml(lines.join("\n"))}</pre>` +
    `<div class="matrix-record-actions">${openSrc}${verifyBtn}</div>`
  );
}

function matrixEventExtras(ev) {
  const extra = [];
  if (ev.query) extra.push("query: " + escapeHtml(ev.query));
  if (ev.entity && ev.attribute) extra.push(escapeHtml(ev.entity) + " / " + escapeHtml(ev.attribute) + " / " + escapeHtml(ev.value || ""));
  if (ev.url) extra.push("url: " + escapeHtml(ev.url));
  if (ev.source_url) extra.push("source_url: " + escapeHtml(ev.source_url));
  if (ev.fetch_kind) extra.push("fetch_kind: " + escapeHtml(ev.fetch_kind));
  if (ev.hit_count != null) extra.push("hit_count: " + escapeHtml(ev.hit_count));
  if (ev.omitted && ev.omitted.length) extra.push("omitted: " + escapeHtml(ev.omitted.join(", ")));
  if (ev.draft_count != null) extra.push("draft_count: " + escapeHtml(ev.draft_count));
  if (ev.count != null) extra.push("count: " + escapeHtml(ev.count));
  if (ev.question) extra.push("question: " + escapeHtml(ev.question));
  if (ev.via) extra.push("via: " + escapeHtml(ev.via));
  if (ev.reason) extra.push("reason: " + escapeHtml(ev.reason));
  if (ev.accepted_count != null) extra.push("accepted: " + escapeHtml(ev.accepted_count));
  if (ev.rejected_count != null) extra.push("rejected: " + escapeHtml(ev.rejected_count));
  if (ev.entity_source_mismatch_count != null) extra.push("mismatch: " + escapeHtml(ev.entity_source_mismatch_count));
  if (ev.value_not_supported_count != null) extra.push("unsupported: " + escapeHtml(ev.value_not_supported_count));
  if (ev.result) extra.push("result: " + escapeHtml(ev.result));
  if (ev.cause) extra.push("cause: " + escapeHtml(ev.cause));
  if (ev.entity_source_mismatch != null) extra.push("entity_mismatch: " + escapeHtml(ev.entity_source_mismatch));
  if (ev.source_title_entity) extra.push("source_title_entity: " + escapeHtml(ev.source_title_entity));
  if (ev.entity_from_query) extra.push("entity_from_query: " + escapeHtml(ev.entity_from_query));
  if (ev.excerpt_contains_value != null) extra.push("excerpt_contains_value: " + escapeHtml(ev.excerpt_contains_value));
  if (ev.titles && ev.titles.length) extra.push("titles: " + escapeHtml(ev.titles.join(", ")));
  if (ev.note) extra.push("note: " + escapeHtml(ev.note));
  if (ev.status) extra.push("status: " + escapeHtml(ev.status));
  if (ev.correlation_id) extra.push("correlation: " + escapeHtml(ev.correlation_id));
  extra.push(actorMeta(ev));
  return extra;
}

function renderMatrixPipelineFromIngest(ing) {
  if (!matrixPipeline) return;
  if (!ing) {
    matrixPipeline.innerHTML = "<p>Matrix ingest: 未実行</p>";
    return;
  }
  const events = ing.events || [];
  const parts = events
    .filter((ev) => ev && ev.type !== "research")
    .map((ev) => {
      return (
        `<div class="tl-item tl-layer-real">` +
        `<div class="tl-title">[${escapeHtml(matrixEventLabel(ev.type))}]</div>` +
        `<div>${matrixEventExtras(ev).join("　")}</div>` +
        `</div>`
      );
    });
  const writes = events.filter((ev) => ev.type === "matrix_write");
  const records = ing.records || [];
  const skipped = writes.find((ev) => ev.status === "skipped");
  let recHtml;
  if (records.length) {
    recHtml = records.map(renderMatrixRecord).join("");
  } else if (skipped) {
    recHtml =
      `<p>MATRIX_WRITE SKIPPED　reason: ${escapeHtml(skipped.reason || "NOT DETERMINED")}</p>`;
  } else if (!writes.length) {
    recHtml = "<p>MATRIX_WRITE: 未実行（表示しない）</p>";
  } else {
    recHtml = "";
  }
  matrixPipeline.innerHTML =
    `<p class="dev-sep">llm_used: ${escapeHtml(String(ing.llm_used === false ? "false" : ing.llm_used || "NOT OBSERVED"))}　Research: ${escapeHtml(ing.research || "NOT CONNECTED")}</p>` +
    parts.join("") +
    recHtml;
}

function renderMatrixVerify(data) {
  if (!matrixVerify) return;
  if (!data) {
    matrixVerify.innerHTML = "<p>Matrix verify: 未実行</p>";
    return;
  }
  const events = data.events || [];
  const parts = events
    .filter((ev) => ev && ev.type !== "research")
    .map((ev) => {
      return (
        `<div class="tl-item tl-layer-real">` +
        `<div class="tl-title">[${escapeHtml(matrixEventLabel(ev.type))}]</div>` +
        `<div>${matrixEventExtras(ev).join("　")}</div>` +
        `</div>`
      );
    });
  const rec = data.record || {};
  matrixVerify.innerHTML =
    `<p class="dev-sep">照合結果: ${escapeHtml(data.result || "NOT OBSERVED")}　cause: ${escapeHtml(data.cause || "NOT_OBSERVED")}　llm_used: false　${escapeHtml(data.note || "")}</p>` +
    `<p class="dev-note">verified_at: ${escapeHtml(data.verified_at || "")}　records_unchanged: ${escapeHtml(String(data.records_unchanged))}</p>` +
    parts.join("") +
    (rec.record_id ? renderMatrixRecord(rec) : "");
}

async function loadMatrixLast() {
  if (!matrixPipeline) return;
  try {
    const res = await fetch("/api/matrix/last");
    const data = await res.json();
    renderMatrixPipelineFromIngest(data.ingest);
  } catch (_err) {
    matrixPipeline.innerHTML = "<p>Matrix ingest: 未実行</p>";
  }
}

async function ingestMatrix() {
  if (!matrixIngestBtn) return;
  matrixIngestBtn.disabled = true;
  try {
    const query = (matrixQueryEl && matrixQueryEl.value) || "RTX 3060";
    const res = await fetch("/api/matrix/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    renderMatrixPipelineFromIngest(data);
  } catch (_err) {
    if (matrixPipeline) matrixPipeline.innerHTML = "<p>Matrix ingest: 失敗</p>";
  }
  matrixIngestBtn.disabled = false;
}

async function searchMatrix() {
  if (!matrixSearchResult) return;
  const q = (matrixSearchQEl && matrixSearchQEl.value) || "RTX 3060";
  const res = await fetch("/api/matrix/search?q=" + encodeURIComponent(q));
  const data = await res.json();
  const rows = data.records || [];
  matrixSearchResult.innerHTML =
    `<p class="dev-sep">機械検索 q=${escapeHtml(q)}　件数: ${escapeHtml(data.count)}　llm_used: false</p>` +
    (rows.length ? rows.map(renderMatrixRecord).join("") : "<p>該当なし</p>");
}

async function searchMatrixAttr() {
  if (!matrixSearchResult) return;
  const entity = (matrixEntityEl && matrixEntityEl.value) || "RTX 3060";
  const attribute = (matrixAttributeEl && matrixAttributeEl.value) || "VRAM capacity";
  const res = await fetch(
    "/api/matrix/search?entity=" + encodeURIComponent(entity) + "&attribute=" + encodeURIComponent(attribute)
  );
  const data = await res.json();
  const rows = data.records || [];
  matrixSearchResult.innerHTML =
    `<p class="dev-sep">属性検索 entity=${escapeHtml(entity)} attribute=${escapeHtml(attribute)}　件数: ${escapeHtml(data.count)}　llm_used: false</p>` +
    (rows.length ? rows.map(renderMatrixRecord).join("") : "<p>該当なし</p>");
}

async function loadMatrixVerify() {
  if (!matrixVerify) return;
  try {
    const res = await fetch("/api/matrix/last_verify");
    const data = await res.json();
    renderMatrixVerify(data.verify);
  } catch (_err) {
    matrixVerify.innerHTML = "<p>Matrix verify: 未実行</p>";
  }
}

async function verifyMatrixById(recordId) {
  if (!matrixVerify || !recordId) return;
  matrixVerify.innerHTML = "<p>Matrix verify: 実行中…</p>";
  try {
    const res = await fetch("/api/matrix/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ record_id: recordId }),
    });
    const data = await res.json();
    renderMatrixVerify(data);
  } catch (_err) {
    matrixVerify.innerHTML = "<p>Matrix verify: 失敗</p>";
  }
}

function renderMatrixTrace(data) {
  if (!matrixTrace) return;
  if (!data) {
    matrixTrace.innerHTML = "<p>Matrix trace: 未実行</p>";
    return;
  }
  const events = data.events || [];
  const parts = events
    .filter((ev) => ev && ev.type !== "research")
    .map((ev) => {
      return (
        `<div class="tl-item tl-layer-real">` +
        `<div class="tl-title">[${escapeHtml(matrixEventLabel(ev.type))}]</div>` +
        `<div>${matrixEventExtras(ev).join("　")}</div>` +
        `</div>`
      );
    });
  matrixTrace.innerHTML =
    `<p class="dev-sep">CAUSE: ${escapeHtml(data.cause || "NOT DETERMINED")}　actual_source: ${escapeHtml(data.actual_source_target || "NOT DETERMINED")}　llm_used: false</p>` +
    `<p class="dev-note">${escapeHtml(data.llm_note || "")}　records_unchanged: ${escapeHtml(String(data.records_unchanged))}</p>` +
    parts.join("");
}

async function loadMatrixAsk() {
  if (!matrixAskResult) return;
  try {
    const res = await fetch("/api/matrix/last_ask");
    const data = await res.json();
    renderMatrixAsk(data.ask);
  } catch (_err) {
    matrixAskResult.innerHTML = "<p>Matrix ask: 未実行</p>";
  }
}

function renderMatrixAsk(data) {
  if (!matrixAskResult) return;
  if (!data) {
    matrixAskResult.innerHTML = "<p>Matrix ask: 未実行</p>";
    return;
  }
  const events = data.events || [];
  const parts = events
    .filter((ev) => ev && ev.type !== "research")
    .map((ev) => {
      return (
        `<div class="tl-item tl-layer-real">` +
        `<div class="tl-title">[${escapeHtml(matrixEventLabel(ev.type))}]</div>` +
        `<div>${matrixEventExtras(ev).join("　")}</div>` +
        `</div>`
      );
    });
  const recs = data.records || [];
  matrixAskResult.innerHTML =
    `<p class="dev-sep">decision: ${escapeHtml(data.decision || "NOT OBSERVED")}　web_search_count: ${escapeHtml(String(data.web_search_count))}　matrix_search_count: ${escapeHtml(String(data.matrix_search_count))}　llm_used: ${escapeHtml(String(data.llm_used))}　model: ${escapeHtml(data.llm_model || "NOT CONNECTED")}　chat_path: ${escapeHtml(data.chat_path || "NOT_CONNECTED")}</p>` +
    `<pre class="matrix-record">${escapeHtml(data.answer || "")}</pre>` +
    parts.join("") +
    recs.map(renderMatrixRecord).join("");
}

async function askMatrix() {
  if (!matrixAskResult) return;
  matrixAskResult.innerHTML = "<p>Matrix ask: 実行中…</p>";
  try {
    const res = await fetch("/api/matrix/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: (matrixAskQEl && matrixAskQEl.value) || "",
        fallback: !!(matrixAskFallbackEl && matrixAskFallbackEl.checked),
        use_llm: !!(matrixAskLlmEl && matrixAskLlmEl.checked),
        model: currentModel || "",
      }),
    });
    const data = await res.json();
    renderMatrixAsk(data);
  } catch (_err) {
    matrixAskResult.innerHTML = "<p>Matrix ask: 失敗</p>";
  }
}

async function loadMatrixTrace() {
  if (!matrixTrace) return;
  try {
    const res = await fetch("/api/matrix/last_trace");
    const data = await res.json();
    renderMatrixTrace(data.trace);
  } catch (_err) {
    matrixTrace.innerHTML = "<p>Matrix trace: 未実行</p>";
  }
}

async function traceMatrixById(recordId) {
  if (!matrixTrace || !recordId) return;
  matrixTrace.innerHTML = "<p>Matrix trace: 実行中…</p>";
  try {
    const res = await fetch("/api/matrix/trace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ record_id: recordId }),
    });
    const data = await res.json();
    renderMatrixTrace(data);
  } catch (_err) {
    matrixTrace.innerHTML = "<p>Matrix trace: 失敗</p>";
  }
}

function onMatrixPanelClick(ev) {
  const traceBtn = ev.target.closest("button[data-trace]");
  if (traceBtn) {
    traceMatrixById(traceBtn.getAttribute("data-trace"));
    return;
  }
  const btn = ev.target.closest("button[data-verify]");
  if (!btn) return;
  verifyMatrixById(btn.getAttribute("data-verify"));
}

if (matrixIngestBtn) matrixIngestBtn.addEventListener("click", ingestMatrix);
if (matrixSearchBtn) matrixSearchBtn.addEventListener("click", searchMatrix);
if (matrixAttrSearchBtn) matrixAttrSearchBtn.addEventListener("click", searchMatrixAttr);
if (matrixAskBtn) matrixAskBtn.addEventListener("click", askMatrix);
if (matrixSearchResult) matrixSearchResult.addEventListener("click", onMatrixPanelClick);
if (matrixPipeline) matrixPipeline.addEventListener("click", onMatrixPanelClick);
if (matrixVerify) matrixVerify.addEventListener("click", onMatrixPanelClick);
if (matrixTrace) matrixTrace.addEventListener("click", onMatrixPanelClick);
if (matrixAskResult) matrixAskResult.addEventListener("click", onMatrixPanelClick);

function claimLines(title, rows) {
  if (!rows || !rows.length) return `<p class="dev-note">${escapeHtml(title)}: （なし）</p>`;
  const items = rows
    .map((row) => {
      const text = row && typeof row === "object" ? row.text || "" : String(row || "");
      return `<li>${escapeHtml(text)}</li>`;
    })
    .join("");
  return `<p class="dev-sep">${escapeHtml(title)}</p><ul>${items}</ul>`;
}

function renderSpecProposal(data) {
  if (!specBody) return;
  if (!data) {
    specBody.innerHTML = "<p>仕様候補: 未実行</p>";
    return;
  }
  const policy = data.policy_eval || {};
  specBody.innerHTML =
    `<p class="dev-sep">origin: ${escapeHtml(data.origin || "NOT_OBSERVED")}　proposal_id: ${escapeHtml(data.proposal_id || "")}　parent: ${escapeHtml(data.parent_proposal_id || "")}　case_id: ${escapeHtml(data.case_id || "（なし）")}　version: ${escapeHtml(String(data.version))}　parse_status: ${escapeHtml(data.parse_status || "NOT OBSERVED")}　llm_used: ${escapeHtml(String(data.llm_used))}　chat_path: ${escapeHtml(data.chat_path || "NOT_CONNECTED")}</p>` +
    `<p class="dev-note">specification_status: ${escapeHtml(policy.specification_status || "NOT OBSERVED")}　may_claim_specification_complete: ${escapeHtml(String(policy.may_claim_specification_complete))}　confidence: ${escapeHtml(data.confidence || "UNCONFIRMED")}　llm_judgment: ${escapeHtml(data.llm_judgment || "NOT_IMPLEMENTED")}　learning_method: ${escapeHtml(data.learning_method || "NOT_DETERMINED")}</p>` +
    `<pre class="matrix-record">${escapeHtml(data.proposed_specification || data.answer || "")}</pre>` +
    claimLines("CONFIRMED", data.confirmed) +
    claimLines("PROPOSED", data.proposed) +
    claimLines("ASSUMED", data.assumptions) +
    claimLines("UNKNOWN", data.unknowns) +
    claimLines("HUMAN_CONFIRMATION_REQUIRED", data.human_confirmation_required);
}

async function loadSpecLast() {
  if (!specBody) return;
  try {
    const res = await fetch("/api/spec/last");
    const data = await res.json();
    renderSpecProposal(data.proposal);
  } catch (_err) {
    specBody.innerHTML = "<p>仕様候補: 未実行</p>";
  }
}

async function proposeSpec() {
  if (!specBody) return;
  specBody.innerHTML = "<p>仕様候補: 実行中…</p>";
  try {
    const res = await fetch("/api/spec/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request: (specRequestEl && specRequestEl.value) || "",
        model: currentModel || "",
        source: "api",
        session_id: sessionId || "",
      }),
    });
    const data = await res.json();
    renderSpecProposal(data);
  } catch (_err) {
    specBody.innerHTML = "<p>仕様候補: 失敗</p>";
  }
}

if (specProposeBtn) specProposeBtn.addEventListener("click", proposeSpec);

async function reviseSpec() {
  if (!specBody) return;
  specBody.innerHTML = "<p>人間修正: 実行中…</p>";
  try {
    const res = await fetch("/api/spec/revise", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        parent_proposal_id: (specParentIdEl && specParentIdEl.value) || "",
        revision_reason: (specRevisionReasonEl && specRevisionReasonEl.value) || "",
        request: (specRequestEl && specRequestEl.value) || "",
      }),
    });
    const data = await res.json();
    renderSpecProposal(data);
  } catch (_err) {
    specBody.innerHTML = "<p>人間修正: 失敗</p>";
  }
}

async function recordSpecProblem() {
  if (!specBody) return;
  specBody.innerHTML = "<p>問題記録: 実行中…</p>";
  try {
    const res = await fetch("/api/spec/problem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        parent_proposal_id: (specParentIdEl && specParentIdEl.value) || "",
        problem: (specProblemEl && specProblemEl.value) || "",
      }),
    });
    const data = await res.json();
    renderSpecProposal(data);
  } catch (_err) {
    specBody.innerHTML = "<p>問題記録: 失敗</p>";
  }
}

if (specReviseBtn) specReviseBtn.addEventListener("click", reviseSpec);
if (specProblemBtn) specProblemBtn.addEventListener("click", recordSpecProblem);

