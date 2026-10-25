/* ==========================================================================
   views.js — 数据列映射 与 运行留痕（回环时间线）
   依赖 app.js 中的全局：currentSessionId / currentProjectId / currentProjectName /
   openIdeTab / escapeHtml / appendAgentBubble
   设计遵循 Material Design 3：信息密度由 list 承载，card 仅用于结果摘要与阻断提示
   ========================================================================== */

/* --------------------------------------------------------------------------
   全局状态
   -------------------------------------------------------------------------- */
const dsState = {
  file_id: null,
  path: null,
  name: null,
  profile: null,   // { n_rows, n_cols, columns: [...] }
  mapping: {       // 列角色映射
    id_col: "",
    time_col: "",
    outcome_col: "",
    g_col: "",
    treatment_col: "",
    cluster_col: "",
    endogenous_col: "",
    instrument_cols: [],
    controls: [],
  },
};

// 角色定义：required 表示必填；either 表示组内至少选一个
const ROLE_DEFS = [
  { key: "id_col",       label: "个体 ID",     group: "core",  required: true,  tip: "面板单位标识，如企业代码、股票代码" },
  { key: "time_col",     label: "时间变量",     group: "core",  required: true,  tip: "年份 / 季度 / 月份" },
  { key: "outcome_col",  label: "被解释变量",   group: "core",  required: true,  tip: "结果变量 Y" },
  { key: "g_col",        label: "首次处理年份", group: "treat", tip: "每个单位首次受政策冲击的时期；从未受冲击的单位填 0 或留空" },
  { key: "treatment_col",label: "处理组标识",   group: "treat", tip: "0/1 处理变量；与「首次处理年份」二者至少指定一个" },
  { key: "cluster_col",  label: "聚类层级",     group: "opt",   tip: "标准误聚类维度，如行业、省份；留空则默认在个体层聚类" },
  { key: "endogenous_col", label: "内生解释变量", group: "iv",  tip: "仅 IV 需要：被认为内生的解释变量；留空时回退到「处理组标识」列" },
];

const KIND_LABEL = {
  numeric: "数值",
  binary: "二值",
  categorical: "类别",
  datetime: "时间",
  text: "文本",
};

/* --------------------------------------------------------------------------
   工具
   -------------------------------------------------------------------------- */
function esc(s) {
  return (typeof escapeHtml === "function") ? escapeHtml(String(s ?? "")) : String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function showSnack(message, actionLabel, onAction) {
  let bar = document.getElementById("md-snackbar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "md-snackbar";
    document.body.appendChild(bar);
  }
  bar.innerHTML = `<span>${esc(message)}</span>${actionLabel ? `<button class="md-snack-action">${esc(actionLabel)}</button>` : ""}`;
  const btn = bar.querySelector(".md-snack-action");
  if (btn && onAction) btn.onclick = () => { bar.classList.remove("show"); onAction(); };
  bar.classList.add("show");
  clearTimeout(bar._t);
  bar._t = setTimeout(() => bar.classList.remove("show"), actionLabel ? 6000 : 3600);
}

/* --------------------------------------------------------------------------
   标签页路由：扩展 openIdeTab，新增 datamap / runtrace
   -------------------------------------------------------------------------- */
/* 视图切换已统一由 app.js 的 IDE_VIEW_MAP 处理，这里不再包装 openIdeTab */

/* --------------------------------------------------------------------------
   数据上传与列画像
   -------------------------------------------------------------------------- */
async function onDatasetFileChosen(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  await uploadDatasetFile(file);
  event.target.value = "";
}

async function uploadDatasetFile(file) {
  const zone = document.getElementById("dataDropzone");
  if (zone) zone.textContent = "正在读取并解析列结构...";

  const fd = new FormData();
  fd.append("file", file);
  fd.append("project_id", (typeof currentProjectId !== "undefined" && currentProjectId) || "proj-default-001");

  try {
    const res = await fetch("/api/data/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok || data.status !== "success") {
      showSnack("数据解析失败：" + (data.detail || "未知错误"));
      resetDropzone();
      return;
    }
    dsState.file_id = data.file_id;
    dsState.path = data.path;
    dsState.name = data.original_name;
    dsState.profile = data.profile;
    autoAssignRoles();
    renderDatasetState();
    renderRoleMap();
    renderColumnProfile();
    await previewDatasetRows();
    showSnack(`已载入《${data.original_name}》 ${data.profile.n_rows} 行 × ${data.profile.n_cols} 列`, "查看映射", () => openIdeTab("datamap"));
  } catch (e) {
    showSnack("上传失败：" + e.message);
    resetDropzone();
  }
}

function resetDropzone() {
  const zone = document.getElementById("dataDropzone");
  if (!zone) return;
  zone.innerHTML = `<span class="dz-icon"></span>
    <div>点击或拖入数据文件</div>
    <div class="dz-hint">支持 CSV / TSV / Excel / Parquet / Stata(.dta) / JSON</div>`;
}

/** 依据列名启发式与列画像自动填一次角色，用户可随后改 */
function autoAssignRoles() {
  const cols = (dsState.profile && dsState.profile.columns) || [];
  const pick = (role) => {
    const exact = cols.find(c => (c.suggested_roles || []).includes(role));
    if (exact) return exact.name;
    return "";
  };
  dsState.mapping.id_col = pick("id_col");
  dsState.mapping.time_col = pick("time_col");
  dsState.mapping.outcome_col = pick("outcome_col");
  dsState.mapping.g_col = pick("g_col");
  dsState.mapping.treatment_col = pick("treatment_col");
  dsState.mapping.cluster_col = pick("cluster_col");
  dsState.mapping.controls = [];
}

function renderDatasetState() {
  const row = document.getElementById("dataFileRow");
  const zone = document.getElementById("dataDropzone");
  if (!row) return;
  if (!dsState.file_id) {
    row.style.display = "none";
    if (zone) zone.style.display = "";
    return;
  }
  if (zone) zone.style.display = "none";
  row.style.display = "flex";
  const p = dsState.profile || {};
  row.innerHTML = `
    <span style="font-size:1rem;"></span>
    <div style="min-width:0;flex:1;">
      <div class="df-name">${esc(dsState.name)}</div>
      <div class="df-meta">${p.n_rows ?? 0} 行 × ${p.n_cols ?? 0} 列</div>
    </div>
    <button class="df-remove" title="移除数据集" onclick="clearDataset()"></button>
  `;
  updateDataSourceSummary();
}

function updateDataSourceSummary() {
  const el = document.getElementById("dataSourceSummary");
  if (!el) return;
  if (dsState.file_id) {
    const m = dsState.mapping;
    const filled = ["id_col", "time_col", "outcome_col"].filter(k => m[k]).length;
    el.textContent = `${dsState.name} · 已映射 ${filled}/3 项必需角色`;
  } else {
    el.textContent = "未选择数据集（将使用内置演示数据）";
  }
}

function clearDataset() {
  dsState.file_id = null;
  dsState.path = null;
  dsState.name = null;
  dsState.profile = null;
  dsState.mapping = { id_col: "", time_col: "", outcome_col: "", g_col: "", treatment_col: "", cluster_col: "", controls: [] };
  resetDropzone();
  renderDatasetState();
  renderRoleMap();
  renderColumnProfile();
  const box = document.getElementById("dataPreviewBox");
  if (box) box.innerHTML = `<div class="empty-hint">暂无预览数据。</div>`;
  refreshMappingChip();
}

async function loadDatasetList() {
  try {
    const res = await fetch("/api/data/list");
    const data = await res.json();
    const list = (data.datasets || []).slice().reverse();
    let host = document.getElementById("dataHistoryList");
    if (!host) {
      host = document.createElement("div");
      host.id = "dataHistoryList";
      const anchor = document.getElementById("dataFileRow");
      anchor.parentNode.insertBefore(host, anchor.nextSibling);
    }
    if (!list.length) {
      host.innerHTML = `<div class="empty-hint" style="padding:8px 0;">尚无历史数据集。</div>`;
      return;
    }
    host.innerHTML = `<div class="md-section-label" style="padding-left:0;"><span>历史数据集（${list.length}）</span></div>` +
      list.map(d => `
        <div class="data-file-row">
          <span class="df-icon">${fileIconSvg(d.original_name)}</span>
          <div style="min-width:0;flex:1;">
            <div class="df-name">${esc(d.original_name)}</div>
            <div class="df-meta">${d.n_rows} 行 × ${d.n_cols} 列 · ${esc(d.uploaded_at)}${d.source ? " · " + esc(d.source) : ""}</div>
          </div>
          <button class="btn-header" style="font-size:0.68rem;padding:2px 10px;" onclick="useExistingDataset('${d.file_id}')">选用</button>
          <button class="icon-btn danger" title="删除该数据集" onclick="deleteDataset('${d.file_id}', '${esc(d.original_name)}')">
            <svg class="ic" aria-hidden="true"><use href="#i-trash"></use></svg>
          </button>
        </div>
      `).join("");
  } catch (e) {
    showSnack("读取历史数据集失败：" + e.message);
  }
}

async function deleteDataset(fileId, name) {
  if (!confirm("删除数据集「" + name + "」？文件会一并删除，不可恢复。")) return;
  try {
    const res = await fetch("/api/data/dataset/" + fileId, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "删除失败");
    showSnack("已删除数据集");
    loadDatasetList();
  } catch (e) {
    showSnack("删除失败：" + e.message);
  }
}

async function useExistingDataset(fileId) {
  try {
    const res = await fetch(`/api/data/profile/${fileId}`);
    const data = await res.json();
    if (!res.ok || data.status !== "success") { showSnack("读取失败：" + (data.detail || "")); return; }
    dsState.file_id = fileId;
    dsState.path = data.meta.path;
    dsState.name = data.meta.original_name;
    dsState.profile = data.profile;
    autoAssignRoles();
    renderDatasetState();
    renderRoleMap();
    renderColumnProfile();
    await previewDatasetRows();
    showSnack(`已载入《${data.meta.original_name}》`);
  } catch (e) {
    showSnack("读取失败：" + e.message);
  }
}

/* --------------------------------------------------------------------------
   列角色映射渲染
   -------------------------------------------------------------------------- */
function renderRoleMap() {
  const host = document.getElementById("roleMapList");
  if (!host) return;
  const cols = (dsState.profile && dsState.profile.columns) || [];
  if (!cols.length) {
    host.innerHTML = `<div class="empty-hint">请先上传数据集，系统将读取真实列名供映射。</div>`;
    refreshMappingChip();
    return;
  }

  const opts = (selected, withEmpty = true) =>
    (withEmpty ? `<option value="">— 未指定 —</option>` : "") +
    cols.map(c => `<option value="${esc(c.name)}"${c.name === selected ? " selected" : ""}>${esc(c.name)}</option>`).join("");

  let html = ROLE_DEFS.map(d => {
    const sel = dsState.mapping[d.key] || "";
    const suggested = cols.find(c => (c.suggested_roles || []).includes(d.key));
    const missing = d.required && !sel;
    return `
      <div class="role-map-row">
        <label>${esc(d.label)}${d.required ? `<span class="role-req">*</span>` : ""}
          ${suggested ? `<span class="role-suggest" title="按列名自动识别">建议</span>` : ""}
        </label>
        <select class="${missing ? "missing" : ""}" onchange="onRoleChange('${d.key}', this.value)">
          ${opts(sel)}
        </select>
        <div class="role-tip">${esc(d.tip)}</div>
      </div>`;
  }).join("");

  // 控制变量：多选
  const sel = dsState.mapping.controls || [];
  html += `
    <div class="role-map-row">
      <label>控制变量<br><span style="font-weight:400;">(可多选)</span></label>
      <select multiple size="5" onchange="onControlsChange(this)">
        ${cols.map(c => `<option value="${esc(c.name)}"${sel.includes(c.name) ? " selected" : ""}>${esc(c.name)}</option>`).join("")}
      </select>
      <div class="role-tip">已选 ${sel.length} 项。注意避免与核心变量存在完全共线性。</div>
    </div>`;

  // 工具变量：多选（IV 策略必需）
  const ivSel = dsState.mapping.instrument_cols || [];
  const ivNeeded = currentStrategyIs("iv");
  html += `
    <div class="role-map-row">
      <label>工具变量<br><span style="font-weight:400;">(可多选${ivNeeded ? "，IV 必填" : ""})</span></label>
      <select multiple size="4" onchange="onInstrumentChange(this)">
        ${cols.map(c => `<option value="${esc(c.name)}"${ivSel.includes(c.name) ? " selected" : ""}>${esc(c.name)}</option>`).join("")}
      </select>
      <div class="role-tip">已选 ${ivSel.length} 项。选多个工具时会额外给出过度识别检验（Hansen J）。</div>
    </div>`;

  host.innerHTML = html;
  refreshMappingChip();
}

function currentStrategyIs(name) {
  const el = document.getElementById("cfgStrategy");
  return !!el && el.value === name;
}

function onInstrumentChange(selectEl) {
  dsState.mapping.instrument_cols = Array.from(selectEl.selectedOptions).map(o => o.value);
  renderRoleMap();
  updateDataSourceSummary();
}

function onRoleChange(key, value) {
  dsState.mapping[key] = value || "";
  renderRoleMap();
  updateDataSourceSummary();
}

function onControlsChange(selectEl) {
  dsState.mapping.controls = Array.from(selectEl.selectedOptions).map(o => o.value);
  renderRoleMap();
}

function validateMapping() {
  const m = dsState.mapping;
  const missing = ROLE_DEFS.filter(d => d.required && !m[d.key]).map(d => d.label);
  if (!m.g_col && !m.treatment_col) missing.push("首次处理年份 或 处理组标识");
  if (currentStrategyIs("iv")) {
    if (!(m.instrument_cols || []).length) missing.push("工具变量（IV 策略必需）");
    if (!m.endogenous_col && !m.treatment_col) missing.push("内生解释变量（或处理组标识）");
  }
  return missing;
}

function refreshMappingChip() {
  const chip = document.getElementById("mappingStateChip");
  if (!chip) return;
  if (!dsState.file_id) {
    chip.className = "verdict-chip verdict-grey";
    chip.textContent = "未配置";
    return;
  }
  const missing = validateMapping();
  if (!missing.length) {
    chip.className = "verdict-chip verdict-green";
    chip.textContent = "映射完整";
  } else {
    chip.className = "verdict-chip verdict-yellow";
    chip.textContent = `缺 ${missing.length} 项`;
  }
}

function applyMappingAndClose() {
  if (!dsState.file_id) { showSnack("请先上传数据集。"); return; }
  const missing = validateMapping();
  if (missing.length) {
    showSnack(`尚缺：${missing.join("、")}`);
    return;
  }
  updateDataSourceSummary();
  showSnack("列角色映射已应用，将随本次任务提交。");
  openIdeTab("chat");
}

function clearMapping() {
  dsState.mapping = {
    id_col: "", time_col: "", outcome_col: "", g_col: "", treatment_col: "",
    cluster_col: "", endogenous_col: "", instrument_cols: [], controls: [],
  };
  renderRoleMap();
  updateDataSourceSummary();
  showSnack("已清空列角色映射。");
}

function onDemoModeToggle() {
  const checked = document.getElementById("checkDemoMode")?.checked;
  if (checked) showSnack("演示模式：将使用内置合成数据，结果仅供流程演示，不可用于论文。");
}

/** 提交前校验：勾选实证但既无数据也未确认演示模式 */
function validateDataSource() {
  const demo = document.getElementById("checkDemoMode")?.checked;
  if (dsState.file_id) {
    const missing = validateMapping();
    if (missing.length) return `数据集已选择，但列角色映射不完整，尚缺：${missing.join("、")}。请在「数据列映射」中补全后再运行。`;
    return null;
  }
  if (demo) return null;
  return "未选择数据集。请上传数据并在「数据列映射」中指定列角色；或勾选「使用内置演示数据」以仅做流程演示（演示结果不可用于论文）。";
}

/* --------------------------------------------------------------------------
   列画像与预览
   -------------------------------------------------------------------------- */
function renderColumnProfile() {
  const host = document.getElementById("colProfileList");
  const cnt = document.getElementById("colProfileCount");
  const cols = (dsState.profile && dsState.profile.columns) || [];
  if (cnt) cnt.textContent = cols.length ? `（${cols.length} 列）` : "";
  if (!host) return;
  if (!cols.length) { host.innerHTML = `<div class="empty-hint">暂无列信息。</div>`; return; }
  host.innerHTML = cols.map(c => {
    const missPct = (c.missing_rate * 100).toFixed(1);
    const warn = c.missing_rate > 0.2;
    return `
      <div class="col-profile-row">
        <span class="cp-name" title="${esc(c.sample.join(" / "))}">${esc(c.name)}</span>
        <span class="cp-kind">${KIND_LABEL[c.kind] || c.kind}</span>
        <span class="cp-stat">${c.n_unique} 唯一</span>
        <span class="cp-stat ${warn ? "cp-warn" : ""}">缺失 ${missPct}%</span>
      </div>`;
  }).join("");
}

async function previewDatasetRows() {
  const box = document.getElementById("dataPreviewBox");
  if (!box) return;
  if (!dsState.file_id) { box.innerHTML = `<div class="empty-hint">暂无预览数据。</div>`; return; }
  try {
    const res = await fetch(`/api/data/preview/${dsState.file_id}?rows=12`);
    const data = await res.json();
    if (!res.ok || data.status !== "success") { box.innerHTML = `<div class="empty-hint">预览失败。</div>`; return; }
    box.innerHTML = `
      <table class="econlit-table">
        <thead><tr>${data.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
        <tbody>${data.rows.map(r => `<tr>${r.map(v => `<td>${esc(v === null ? "—" : v)}</td>`).join("")}</tr>`).join("")}</tbody>
      </table>`;
  } catch (e) {
    box.innerHTML = `<div class="empty-hint">预览失败：${esc(e.message)}</div>`;
  }
}

/* --------------------------------------------------------------------------
   提交载荷：由 UI 真实状态组装（不再写死课题/策略/控制变量）
   -------------------------------------------------------------------------- */
function buildWorkflowPayload(flags) {
  const topicEl = document.getElementById("cfgResearchTopic");
  const topic = (topicEl && topicEl.value.trim()) ||
    (typeof currentProjectName !== "undefined" ? currentProjectName : "");
  const journal = document.getElementById("cfgTargetJournal")?.value || "经济研究";
  const strategy = document.getElementById("cfgStrategy")?.value || "auto";
  const demo = !!document.getElementById("checkDemoMode")?.checked;
  const m = dsState.mapping;

  return {
    research_topic: topic,
    methodology: strategy,
    control_variables: m.controls || [],
    derived_mappings: null,
    session_id: (typeof currentSessionId !== "undefined" ? currentSessionId : null),
    project_id: (typeof currentProjectId !== "undefined" ? currentProjectId : "proj-default-001"),
    enable_search: !!flags.enable_search,
    enable_empirical: !!flags.enable_empirical,
    enable_writing: !!flags.enable_writing,
    data_path: dsState.path,
    id_col: m.id_col || null,
    time_col: m.time_col || null,
    outcome_col: m.outcome_col || null,
    treatment_col: m.treatment_col || null,
    g_col: m.g_col || null,
    cluster_col: m.cluster_col || null,
    endogenous_col: m.endogenous_col || null,
    instrument_cols: m.instrument_cols || [],
    mediators: [],
    moderators: [],
    demo_mode: demo,
    target_journal: journal,
    max_strategy_attempts: 3,
  };
}

/* --------------------------------------------------------------------------
   运行留痕：回环时间线
   -------------------------------------------------------------------------- */
let runTraceCache = { runs: [], selected: null };

async function loadRunTrace() {
  const host = document.getElementById("runTraceBody");
  if (!host) return;
  try {
    const res = await fetch("/api/runs/list?limit=20");
    const data = await res.json();
    const runs = data.runs || [];
    runTraceCache.runs = runs;
    if (!runs.length) {
      host.innerHTML = `<div class="empty-hint">尚无运行记录。启动一次实证分析后，这里会显示每次策略尝试与审稿判定。</div>`;
      return;
    }
    const sel = runTraceCache.selected || runs[0].run_id;
    renderRunList(runs, sel);
    await renderRunDetail(sel);
  } catch (e) {
    host.innerHTML = `<div class="empty-hint">读取运行记录失败：${esc(e.message)}</div>`;
  }
}

function fmtRunTime(ts) {
  if (!ts) return "";
  const d = new Date(typeof ts === "number" && ts > 1e12 ? ts : ts * 1000);
  return isNaN(d.getTime()) ? "" : d.toLocaleTimeString();
}

function renderRunList(runs, selected) {
  const host = document.getElementById("runTraceBody");
  const items = runs.map(r => {
    const v = r.verdict || "";
    const cls = v === "green" ? "verdict-green" : v === "yellow" ? "verdict-yellow" : v === "red" ? "verdict-red" : "verdict-grey";
    const active = r.run_id === selected;
    return `
      <div class="artifact-row" style="cursor:pointer;${active ? "background:var(--md-secondary-container);" : ""}"
           onclick="selectRun('${r.run_id}')">
        <span class="artifact-kind">${esc(r.strategy_used || "—")}</span>
        <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(r.research_topic || "未命名课题")}</span>
        <span class="verdict-chip ${cls}">${esc(v || r.status)}</span>
        <span style="font-size:0.68rem;color:var(--md-outline);">${esc(fmtRunTime(r.created_at))}</span>
      </div>`;
  }).join("");

  let detailHost = document.getElementById("runDetailHost");
  if (!detailHost) {
    host.innerHTML = `
      <div class="md-section-label" style="padding-left:0;"><span>历史运行（${runs.length}）</span></div>
      <div id="runListHost">${items}</div>
      <div id="runDetailHost"></div>`;
  } else {
    const lh = document.getElementById("runListHost");
    if (lh) lh.innerHTML = items;
  }
}

async function selectRun(runId) {
  runTraceCache.selected = runId;
  renderRunList(runTraceCache.runs, runId);
  await renderRunDetail(runId);
}

async function renderRunDetail(runId) {
  const host = document.getElementById("runDetailHost");
  if (!host) return;
  host.innerHTML = `<div class="empty-hint">正在加载运行留痕...</div>`;
  try {
    const res = await fetch(`/api/runs/${runId}`);
    const data = await res.json();
    if (!res.ok || data.status !== "success") { host.innerHTML = `<div class="empty-hint">读取失败。</div>`; return; }
    host.innerHTML = renderRunSummary(data.run) + renderTimeline(data.steps || []) +
      renderArtifacts(data.artifacts || []) + renderSkillTrace(data.run);
  } catch (e) {
    host.innerHTML = `<div class="empty-hint">读取失败：${esc(e.message)}</div>`;
  }
}

function renderRunSummary(run) {
  const v = run.verdict || run.status || "";
  const cls = v === "green" ? "verdict-green" : v === "yellow" ? "verdict-yellow" : v === "red" ? "verdict-red" : "verdict-grey";
  const att = run.att_coef ?? run.att ?? null;
  const chain = Array.isArray(run.strategy_chain) ? run.strategy_chain.join(" → ") : (run.strategy_chain || "—");
  const concerns = Array.isArray(run.carried_concerns) ? run.carried_concerns : [];
  const reasons = Array.isArray(run.review_reasons) ? run.review_reasons : [];
  const concernBlock = (concerns.length || (v === "yellow" && reasons.length)) ? `
    <div style="margin-top:12px;padding:12px 14px;border-radius:var(--md-shape-sm);
                background:var(--md-warning-container);color:var(--md-on-warning-container);font-size:0.78rem;">
      <div style="font-weight:700;margin-bottom:4px;">沿链路保留的疑虑（判定因此降级为黄灯）</div>
      <ul style="margin:0;padding-left:18px;">
        ${concerns.map(c => `<li>${esc(c)}</li>`).join("") || reasons.map(c => `<li>${esc(c)}</li>`).join("")}
      </ul>
    </div>` : "";

  return `
    <div class="run-summary-card">
      <div class="run-summary-title">${esc(run.research_topic || "未命名课题")}</div>
      <div class="run-summary-sub">
        <span class="verdict-chip ${cls}">${esc(v)}</span>
        &nbsp;策略链：${esc(chain)} &nbsp;·&nbsp; ${esc(run.run_id)}
      </div>
      <div class="run-kv-strip">
        <div class="run-kv"><div class="kv-label">核心估计量</div><div class="kv-value">${att === null || att === undefined ? "—" : Number(att).toFixed(4)}</div></div>
        <div class="run-kv"><div class="kv-label">标准误</div><div class="kv-value">${run.att_se == null ? "—" : Number(run.att_se).toFixed(4)}</div></div>
        <div class="run-kv"><div class="kv-label">p 值</div><div class="kv-value">${run.att_p == null ? "—" : Number(run.att_p).toFixed(4)}</div></div>
        <div class="run-kv"><div class="kv-label">尝试次数</div><div class="kv-value">${run.attempts ?? "—"}</div></div>
      </div>
      ${concernBlock}
    </div>`;
}

function renderTimeline(steps) {
  if (!steps.length) return `<div class="empty-hint">该运行没有留痕步骤。</div>`;
  const items = steps.map((s, i) => {
    const v = s.verdict || "";
    const cls = v === "green" ? "ok" : v === "yellow" ? "warn" : v === "red" ? "fail" : "";
    const vcls = v === "green" ? "verdict-green" : v === "yellow" ? "verdict-yellow" : v === "red" ? "verdict-red" : "verdict-grey";
    const reasons = Array.isArray(s.reasons) ? s.reasons : (s.reasons ? [s.reasons] : []);
    const isLast = i === steps.length - 1;
    // 判红即触发回环：非末次尝试 → 已切换下一策略；末次尝试 → 策略链用尽
    const loopback = v === "red" ? (isLast ? "exhausted" : "switch") : "";
    return `
      <div class="tl-item ${cls}">
        <div class="tl-head">
          <span class="tl-seq">#${s.seq ?? i + 1}</span>
          <span class="tl-title">策略：${esc(s.strategy || "—")}</span>
          ${v ? `<span class="verdict-chip ${vcls}">${esc(v)}</span>` : ""}
          <span style="font-size:0.7rem;color:var(--md-outline);">${esc(s.status || "")}</span>
        </div>
        <div class="tl-meta">${esc(s.step_type || s.stage || "")}${s.duration_ms ? ` · ${s.duration_ms} ms` : ""}</div>
        ${reasons.length ? `<ul class="tl-reasons">${reasons.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
        ${loopback === "switch" ? `<div class="tl-loopback">↻ 审稿未通过，回环切换下一策略</div>` : ""}
        ${loopback === "exhausted" ? `<div class="tl-loopback">↻ 已用尽策略链，疑虑沿链路保留</div>` : ""}
      </div>`;
  }).join("");
  return `<div class="md-section-label" style="padding-left:0;"><span>回环时间线（${steps.length} 次尝试）</span></div>
          <div class="timeline">${items}</div>`;
}

function renderArtifacts(artifacts) {
  if (!artifacts.length) return "";
  return `<div class="md-section-label" style="padding-left:0;"><span>产出物（${artifacts.length}）</span></div>
    <div class="artifact-list">
      ${artifacts.map(a => `
        <div class="artifact-row">
          <span class="artifact-kind">${esc(a.kind)}</span>
          <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;">${esc(a.name)}</span>
          ${a.web_url ? `<a href="${esc(a.web_url)}" target="_blank">打开</a>` : ""}
        </div>`).join("")}
    </div>`;
}

function renderSkillTrace(run) {
  let trace = run.skill_trace;
  if (typeof trace === "string") { try { trace = JSON.parse(trace); } catch { trace = null; } }
  if (!Array.isArray(trace) || !trace.length) return "";
  return `<div class="md-section-label" style="padding-left:0;"><span>本轮生效技能（${trace.length}）</span></div>
    <div class="skill-trace-list">
      ${trace.map(t => `<span class="skill-trace-chip">${esc(t.name_zh || t.skill_id)}<span class="st-hash">${esc((t.hash || "").slice(0, 8))}</span></span>`).join("")}
    </div>`;
}

/* ==========================================================================
   Part 1 文献检索工作台（原 :8765，已并入 :8088）
   结果用 list 呈现，勾选后导出 / 写入 Zotero / 存入资料库
   ========================================================================== */
const litState = {
  protocol: null,
  result: null,       // 最近一次检索结果
  selected: new Set(),// 勾选的记录下标
  zotero_online: false,
};

/* --------------------------------------------------------------------------
   Zotero 接线：状态指引 + 分类库选择 + API key 配置
   -------------------------------------------------------------------------- */
async function refreshZoteroStatus() {
  const guide = document.getElementById("zoteroSetupGuide");
  const chip = document.getElementById("zoteroModeChip");
  const hint = document.getElementById("zoteroConfigHint");
  try {
    const res = await fetch("/api/lit/zotero/status");
    const d = await res.json();
    const conn = d.connector || {};
    const api = d.local_api || {};
    const cfg = d.config || {};
    litState.zotero_online = !!conn.available;

    if (chip) {
      const ok = conn.available || api.available;
      chip.className = "verdict-chip " + (ok ? "verdict-green" : "verdict-grey");
      chip.textContent = api.available ? "API 通道在线（可指定分类）"
        : (conn.available ? "Connector 在线（写入当前选中分类）" : "未接通");
    }
    if (guide) {
      if (api.available) {
        guide.textContent = "Zotero 已接通，可勾选文献后直接写入下方选中的分类库。";
      } else if (conn.available) {
        guide.textContent = "Zotero 已运行，但未配置 API key，写入会落到 Zotero 当前选中的分类。"
          + "要写进指定分类库（如「成本绩效」「零基预算下的城市维运」），请在 Zotero 设置 → 高级 → 本地 API 生成 key 并填入下方。";
      } else {
        guide.innerHTML = "未检测到 Zotero。请按下列步骤开启：<br>"
          + (d.enable_steps || []).map((s, i) => `${i + 1}. ${esc(s)}`).join("<br>");
      }
    }
    if (hint && cfg.api_key_set) hint.textContent = `已保存 key：${esc(cfg.api_key_masked)}（存于 ${esc(cfg.secrets_path)}）`;
  } catch (e) {
    if (chip) { chip.className = "verdict-chip verdict-grey"; chip.textContent = "状态未知"; }
  }
}

async function loadZoteroCollections() {
  const sel = document.getElementById("zoteroCollection");
  const hint = document.getElementById("zoteroConfigHint");
  if (!sel) return;
  try {
    const res = await fetch("/api/lit/zotero/collections");
    const d = await res.json();
    const cols = d.collections || [];
    sel.innerHTML = `<option value="">写入库根（或 Zotero 当前选中分类）</option>`
      + cols.map(c => `<option value="${esc(c.key || "")}">${esc(c.name || "(未命名)")}${c.n_items != null ? ` · ${c.n_items} 条` : ""}</option>`).join("");
    if (d.error && hint) hint.textContent = d.error;
    else if (hint) hint.textContent = cols.length ? `已列出 ${cols.length} 个分类库` : "没有读到分类库";
  } catch (e) {
    if (hint) hint.textContent = "读取分类库失败：" + e;
  }
}

async function saveZoteroConfig() {
  const key = document.getElementById("zoteroApiKey")?.value || "";
  const hint = document.getElementById("zoteroConfigHint");
  try {
    const res = await fetch("/api/lit/zotero/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key }),
    });
    const d = await res.json();
    if (!res.ok) { if (hint) hint.textContent = "保存失败：" + (d.detail || res.status); return; }
    showSnack(d.api_key_set ? "Zotero API key 已保存" : "已清除 Zotero API key");
    await refreshZoteroStatus();
    await loadZoteroCollections();
  } catch (e) {
    if (hint) hint.textContent = "保存失败：" + e;
  }
}

async function refreshLitStatus() {
  const chip = document.getElementById("litZoteroChip");
  try {
    const res = await fetch("/api/lit/status");
    const data = await res.json();
    const live = (data.zotero_live || {});
    litState.zotero_online = !!live.available;
    if (chip) {
      chip.className = "verdict-chip " + (live.available ? "verdict-green" : "verdict-grey");
      chip.textContent = live.available
        ? `Zotero 在线${live.version ? " · v" + live.version : ""}`
        : "Zotero 未启动";
      chip.title = live.available
        ? "可勾选记录后写入本机 Zotero"
        : "本机 Zotero 未运行或未开启「允许本机其他应用与 Zotero 通信」";
    }
    if (!data.available) {
      showSnack("Part 1 检索能力不可用：" + esc(data.error || "未知原因"));
    }
  } catch (e) {
    if (chip) { chip.className = "verdict-chip verdict-grey"; chip.textContent = "状态未知"; }
  }
  await refreshZoteroStatus();
  await loadZoteroCollections();
}

async function generateLitProtocol() {
  const q = document.getElementById("litQuestion")?.value.trim();
  if (!q) { showSnack("请先填写研究问题。"); return; }
  const box = document.getElementById("litProtocolBox");
  if (box) box.textContent = "正在生成检索方案（含中英文概念块与纳入/排除标准）...";
  try {
    const res = await fetch("/api/lit/protocol", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ research_question: q }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "生成失败");
    litState.protocol = data;
    renderLitProtocol(data);
  } catch (e) {
    if (box) box.textContent = "生成失败：" + e.message;
  }
}

function renderLitProtocol(p) {
  const box = document.getElementById("litProtocolBox");
  if (!box || !p) return;
  const blocks = (p.concept_blocks || []).map(b =>
    `<div class="lit-concept-row"><span class="lc-name">${esc(b.concept)}</span><span class="lc-terms">${(b.terms || []).map(esc).join(" · ")}</span></div>`
  ).join("");
  box.className = "";
  box.innerHTML = `
    <div class="lit-protocol">
      <div class="lp-row"><span class="lp-k">工作检索式</span><span class="lp-v">${esc(p.working_query || "")}</span></div>
      <div class="lp-row"><span class="lp-k">翻译来源</span><span class="lp-v">${esc(p.translation_source || "")}</span></div>
      ${blocks ? `<div class="md-section-label" style="padding-left:0;"><span>概念块</span></div>${blocks}` : ""}
      <div class="md-section-label" style="padding-left:0;"><span>纳入 / 排除标准</span></div>
      <ul class="lp-list">${(p.inclusion_criteria || []).map(x => `<li>纳入：${esc(x)}</li>`).join("")}</ul>
      <ul class="lp-list">${(p.exclusion_criteria || []).map(x => `<li>排除：${esc(x)}</li>`).join("")}</ul>
      ${(p.requested_methods || []).length ? `<div class="lp-row"><span class="lp-k">方法词</span><span class="lp-v">${p.requested_methods.map(esc).join(" / ")}</span></div>` : ""}
    </div>`;
}

async function runLitSearch() {
  const q = document.getElementById("litQuestion")?.value.trim();
  if (!q) { showSnack("请先填写研究问题。"); return; }
  const host = document.getElementById("litResultList");
  if (host) host.innerHTML = `<div class="empty-hint">正在多源检索，请稍候...</div>`;

  const payload = {
    research_question: q,
    query: (litState.protocol && litState.protocol.working_query) || q,
    sources: ["crossref", "openalex", "arxiv", "nber", "core"],
    limit: 25,
    ranking: "relevance",
    mode: "balanced",
  };
  if (litState.protocol) {
    payload.concept_blocks = litState.protocol.concept_blocks;
    payload.inclusion_criteria = litState.protocol.inclusion_criteria;
    payload.exclusion_criteria = litState.protocol.exclusion_criteria;
    payload.requested_methods = litState.protocol.requested_methods;
  }
  try {
    const res = await fetch("/api/lit/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "检索失败");
    litState.result = data;
    litState.selected = new Set();
    renderLitResults(data);
  } catch (e) {
    if (host) host.innerHTML = `<div class="empty-hint">检索失败：${esc(e.message)}</div>`;
  }
}

function litRecords() {
  const r = litState.result || {};
  return r.records || r.results || [];
}

function renderLitResults(data) {
  const host = document.getElementById("litResultList");
  const cnt = document.getElementById("litResultCount");
  const recs = litRecords();
  if (cnt) cnt.textContent = recs.length ? `（${recs.length} 条）` : "";
  if (!host) return;
  if (!recs.length) {
    host.innerHTML = `<div class="empty-hint">本次检索没有返回结果。可尝试更换检索式或扩大来源。</div>`;
    return;
  }
  host.innerHTML = recs.map((r, i) => {
    const authors = Array.isArray(r.authors)
      ? r.authors.slice(0, 3).map(a => (typeof a === "string" ? a : `${a.family || ""} ${a.given || ""}`.trim())).join(", ")
      : (r.authors || "");
    const tier = (r.journal_ranking || {}).tier || r.venue || "";
    return `
      <label class="lit-row">
        <input type="checkbox" onchange="onLitSelect(${i}, this.checked)">
        <span class="lr-title">${esc(r.title || "无标题")}</span>
        <span class="lr-meta">${esc(authors)}${r.year ? " · " + esc(r.year) : ""}</span>
        <span class="lr-venue">${esc(tier)}</span>
      </label>`;
  }).join("");

  const logs = (data.search_logs || []).map(l =>
    `<div class="lit-log-row"><span class="ll-src">${esc(l.source_id)}</span><span class="ll-status">${esc(l.status || "")}</span><span class="ll-n">${esc(l.count ?? l.n ?? "")}</span></div>`
  ).join("");
  if (logs) {
    host.insertAdjacentHTML("afterend",
      `<div class="md-section-label" style="padding-left:0;"><span>检索日志</span></div><div class="lit-log-list">${logs}</div>`);
  }
}

function onLitSelect(index, checked) {
  if (checked) litState.selected.add(index); else litState.selected.delete(index);
}

function selectedLitRecords() {
  const recs = litRecords();
  return Array.from(litState.selected).sort((a, b) => a - b).map(i => recs[i]).filter(Boolean);
}

async function exportLitRecords(fmt) {
  const recs = selectedLitRecords();
  if (!recs.length) { showSnack("请先勾选要导出的文献。"); return; }
  try {
    const res = await fetch("/api/lit/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records: recs, format: fmt }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "导出失败");
    const blob = new Blob([data.content], { type: data.content_type || "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `literature-${Date.now()}.${data.extension || fmt}`;
    a.click();
    URL.revokeObjectURL(a.href);
    showSnack(`已导出 ${data.n_records} 条记录（${fmt.toUpperCase()}）。`);
  } catch (e) {
    showSnack("导出失败：" + e.message);
  }
}

async function saveLitRecordsToZotero() {
  const recs = selectedLitRecords();
  if (!recs.length) { showSnack("请先勾选要写入的文献。"); return; }
  // 有 API key 时不必依赖 Connector 在线；没有 key 才需要 Zotero 跑着
  const hasKey = !!(document.getElementById("zoteroApiKey")?.value)
    || (document.getElementById("zoteroConfigHint")?.textContent || "").includes("已保存 key");
  if (!litState.zotero_online && !hasKey) {
    showSnack("本机 Zotero 未运行，且未配置 API key。请启动 Zotero 并开启「允许本机其他应用与 Zotero 通信」，或在下方填入 API key。");
    return;
  }
  try {
    const collection = document.getElementById("zoteroCollection")?.value || "";
    const res = await fetch("/api/lit/zotero/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records: recs, collection_key: collection }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "写入失败");
    const n = data.n_created ?? data.saved ?? recs.length;
    showSnack(`已写入 Zotero：${n} 条${data.collection && data.collection !== "（未指定分类）" ? ` → ${data.collection}` : ""}`);
  } catch (e) {
    showSnack("写入 Zotero 失败：" + e.message);
  }
}

async function saveLitRecordsToLibrary() {
  const recs = selectedLitRecords();
  if (!recs.length) { showSnack("请先勾选要保存的文献。"); return; }
  let ok = 0, fail = 0;
  for (const r of recs) {
    try {
      const res = await fetch("/api/library/save_item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: r.title || "无标题",
          authors: r.authors || [],
          year: r.year,
          abstract: r.abstract || "",
          source: "part1-literature-search",
          url: r.url || "",
          journal: r.venue || "",
        }),
      });
      if (res.ok) ok++; else fail++;
    } catch { fail++; }
  }
  showSnack(`已存入资料库 ${ok} 条${fail ? `，失败 ${fail} 条` : ""}。`);
  if (typeof loadLibraryItems === "function") loadLibraryItems();
}

/* ==========================================================================
   期刊下拉：由后端 /api/journals 驱动，新增格式包无需改前端
   ========================================================================== */
async function loadJournalOptions() {
  const sel = document.getElementById("cfgTargetJournal");
  if (!sel) return;
  try {
    const res = await fetch("/api/journals");
    const data = await res.json();
    const list = data.journals || [];
    if (!list.length) return;
    const current = sel.value;
    sel.innerHTML = list.map(j =>
      `<option value="${esc(j.journal)}"${j.journal === current ? " selected" : ""}>${esc(j.label)} · ${esc(j.field)}</option>`
    ).join("");
    if (!list.some(j => j.journal === current)) sel.value = list[0].journal;
    sel.title = list.map(j => `${j.label}：${j.note}（${j.n_skills} 个章节技能）`).join("\n");
  } catch (e) {
    // 拉取失败时保留 HTML 中的静态选项，不影响使用
  }
}

/* ==========================================================================
   对话框通用行为：遮罩点击关闭 / ESC 关闭 / 打开时锁滚动并聚焦首个输入
   只做"锦上添花"的通用部分，不改动各弹窗自身的打开关闭逻辑
   ========================================================================== */
const modalCtl = { lastFocus: null };

function activeModals() {
  return Array.from(document.querySelectorAll(".modal-overlay.active"));
}

function closeTopModal(target) {
  const list = activeModals();
  const el = target && target.classList && target.classList.contains("modal-overlay") ? target : list[list.length - 1];
  if (!el) return;
  el.classList.remove("active");
}

function syncModalScrollLock() {
  document.body.classList.toggle("modal-open", activeModals().length > 0);
}

function onModalOpened(el) {
  modalCtl.lastFocus = document.activeElement;
  syncModalScrollLock();
  // 聚焦第一个可编辑控件，键盘用户不必先点一下
  const focusable = el.querySelector(
    "input:not([type=hidden]):not([disabled]), textarea, select, .modal-close-btn"
  );
  if (focusable) {
    // 等一帧，避免与过渡同时触发导致滚动跳动
    requestAnimationFrame(() => focusable.focus({ preventScroll: true }));
  }
}

function onModalClosed() {
  syncModalScrollLock();
  if (modalCtl.lastFocus && typeof modalCtl.lastFocus.focus === "function") {
    modalCtl.lastFocus.focus({ preventScroll: true });
  }
  modalCtl.lastFocus = null;
}

(function wireModalBehavior() {
  // 点击遮罩（而非卡片内部）关闭
  document.addEventListener("mousedown", e => {
    if (e.target.classList && e.target.classList.contains("modal-overlay")) {
      closeTopModal(e.target);
    }
  });
  // ESC 关闭最上层
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && activeModals().length) {
      closeTopModal();
    }
  });
  // 监听 class 变化，统一处理滚动锁与焦点
  const observer = new MutationObserver(mutations => {
    for (const m of mutations) {
      const el = m.target;
      if (!el.classList || !el.classList.contains("modal-overlay")) continue;
      if (el.classList.contains("active")) onModalOpened(el);
      else if (!activeModals().length) onModalClosed();
      else syncModalScrollLock();
    }
  });
  const attach = () => {
    document.querySelectorAll(".modal-overlay").forEach(el => {
      if (el.dataset.modalWired) return;
      el.dataset.modalWired = "1";
      el.setAttribute("role", el.getAttribute("role") || "dialog");
      el.setAttribute("aria-modal", "true");
      observer.observe(el, { attributes: true, attributeFilter: ["class"] });
    });
  };
  attach();
  document.addEventListener("DOMContentLoaded", attach);
})();

/* --------------------------------------------------------------------------
   中文文献通道：联网检索 + 中文库直达 + 题录回导
   -------------------------------------------------------------------------- */
async function runCnLitSearch() {
  const q = (document.getElementById("cnLitQuery")?.value || "").trim();
  if (!q) { showSnack("请先填写中文检索式。"); return; }
  const host = document.getElementById("cnLibList");
  try {
    const res = await fetch("/api/lit/cn/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q, limit: 20 }),
    });
    const data = await res.json();
    if (!res.ok) { showSnack("中文检索失败：" + (data.detail || res.status)); return; }

    // 合并进现有结果列表（回导与联网检索共用一套勾选/导出逻辑）
    const prev = litState.result || {};
    const merged = (prev.records || []).concat(data.records || []);
    litState.result = Object.assign({}, prev, { records: merged });
    litState.selected = new Set();
    renderLitResults(litState.result);
    showSnack(`中文检索返回 ${data.records.length} 条（已合并进结果列表）`);

    if (host) {
      host.innerHTML = (data.manual_links || []).map(l => `
        <li class="cn-lib-row">
          <a class="cn-lib-name" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.name)} ↗</a>
          <span class="cn-lib-note">${esc(l.note)}</span>
          <span class="cn-lib-hint">导出方式：${esc(l.export_hint)}</span>
        </li>`).join("");
    }
  } catch (e) {
    showSnack("中文检索失败：" + e);
  }
}

async function importCnLitFile(input) {
  const f = input.files && input.files[0];
  if (!f) return;
  const hint = document.getElementById("cnLitImportHint");
  try {
    const text = await f.text();
    const res = await fetch("/api/lit/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: text, format: "auto" }),
    });
    const data = await res.json();
    if (!res.ok) { if (hint) hint.textContent = "回导失败：" + (data.detail || res.status); return; }
    const prev = litState.result || {};
    const merged = (prev.records || []).concat(data.records || []);
    litState.result = Object.assign({}, prev, { records: merged });
    litState.selected = new Set();
    renderLitResults(litState.result);
    if (hint) hint.textContent = `已回导 ${data.n_records} 条题录（来自 ${f.name}）`;
    showSnack(`已回导 ${data.n_records} 条中文题录`);
  } catch (e) {
    if (hint) hint.textContent = "回导失败：" + e;
  } finally {
    input.value = "";
  }
}

/* --------------------------------------------------------------------------
   Word 导出：把当前会话的论文分节 + 文献 + 实证表格导出为 CSSCI 取向的 docx
   -------------------------------------------------------------------------- */
async function exportPaperDocx() {
  const sid = (typeof currentSessionId !== "undefined" && currentSessionId) ? currentSessionId : null;
  if (!sid) {
    showSnack("还没有可导出的会话，请先跑一次写作。");
    return;
  }
  const btn = document.getElementById("btnExportDocx");
  const old = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; btn.textContent = "⏳ 生成中…"; }
  try {
    const res = await fetch("/api/export/docx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sid }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showSnack("导出失败：" + (data.detail || res.status));
      return;
    }
    const a = document.createElement("a");
    a.href = data.url;
    a.download = data.file_name || "paper.docx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    showSnack(`已导出 Word：${data.n_sections} 个章节、${data.n_references} 条参考文献`);
  } catch (e) {
    showSnack("导出失败：" + e);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = old; }
  }
}

/* --------------------------------------------------------------------------
   初始化：拖放上传、右栏课题默认值
   -------------------------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  const zone = document.getElementById("dataDropzone");
  if (zone) {
    zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("dragover"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", e => {
      e.preventDefault();
      zone.classList.remove("dragover");
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) uploadDatasetFile(f);
    });
  }
  const topicEl = document.getElementById("cfgResearchTopic");
  if (topicEl && !topicEl.value && typeof currentProjectName !== "undefined") {
    topicEl.value = currentProjectName || "";
  }
  refreshMappingChip();
  updateDataSourceSummary();
  loadJournalOptions();

  // 支持 ?tab=datamap|runtrace|litsearch|library 直接定位
  const params = new URLSearchParams(location.search);
  const tab = params.get("tab");
  if (tab && tab !== "chat") openIdeTab(tab);
  // 支持 ?modal=projects|llm|skill|asset 直接打开对话框（便于分享与自检）
  const modal = params.get("modal");
  if (modal) {
    const openers = {
      projects: "openProjectsModal",
      llm: "openLLMConfigModal",
      asset: "openUploadAssetModal",
      skill: "openUploadSkillModal",
    };
    const fn = openers[modal];
    if (fn && typeof window[fn] === "function") window[fn]();
  }
});
