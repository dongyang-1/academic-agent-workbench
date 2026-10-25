const state = {
  config: null,
  data: null,
  activeTab: "results",
  currentRecordId: null,
  translations: {},
  selectedRecordIds: new Set(),
  toastTimer: null,
  translationTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function safeUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch { return ""; }
}

function icon(name, size = 14) {
  return `<i data-lucide="${name}" style="width:${size}px;height:${size}px"></i>`;
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

function setStatus(label, kind = "ready") {
  $("#run-status").textContent = label;
  $("#status-dot").className = kind === "ready" ? "" : kind;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove("show"), 3600);
}

function setLoading(open, message = "不同来源响应时间可能不同，请稍候。") {
  $("#loading-message").textContent = message;
  $("#loading-overlay").classList.toggle("open", open);
  $("#loading-overlay").setAttribute("aria-hidden", String(!open));
  $("#search-button").disabled = open;
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `请求失败 (${response.status})`);
  return data;
}

function sourceLabel(id) {
  if (id === "user-corpus") return "已有语料";
  return state.config?.sources.find((source) => source.id === id)?.label || id || "未知";
}

function splitValues(value) {
  return String(value || "").split(/[,;，；\n]/).map((item) => item.trim()).filter(Boolean);
}

function splitLines(value) {
  return String(value || "").split(/\n+/).map((item) => item.trim()).filter(Boolean);
}

function currentSearchContext() {
  const policy = splitValues($("#concept-policy").value);
  const outcome = splitValues($("#concept-outcome").value);
  return {
    research_question: $("#research-question").value,
    working_query: $("#working-query").value,
    start_year: $("#start-year").value,
    end_year: $("#end-year").value,
    limit: $("#result-limit").value,
    sources: $$('input[name="source"]:checked').map((input) => input.value),
    mode: $("#search-mode").value,
    ranking: $("#ranking-mode").value,
    concept_blocks: [
      ...(policy.length ? [{ concept: "policy_or_treatment", terms: policy }] : []),
      ...(outcome.length ? [{ concept: "outcome_or_mechanism", terms: outcome }] : []),
    ],
    requested_methods: splitValues($("#requested-methods").value),
    inclusion_criteria: splitLines($("#inclusion-criteria").value),
    exclusion_criteria: splitLines($("#exclusion-criteria").value),
    protocol_confirmed: $("#protocol-confirmed").checked,
  };
}

function populateConfig(config) {
  state.config = config;
  const defaults = config.defaults;
  $("#research-question").value = defaults.research_question;
  $("#working-query").value = defaults.working_query;
  $("#start-year").value = defaults.start_year;
  $("#end-year").value = defaults.end_year;
  $("#result-limit").value = defaults.limit;
  $("#search-mode").value = defaults.mode || "exploratory";
  $("#ranking-mode").value = defaults.ranking || "combined";
  $("#concept-policy").value = (defaults.concept_blocks?.[0]?.terms || []).join(", ");
  $("#concept-outcome").value = (defaults.concept_blocks?.[1]?.terms || []).join(", ");
  $("#requested-methods").value = (defaults.requested_methods || []).join(", ");
  $("#inclusion-criteria").value = (defaults.inclusion_criteria || []).join("\n");
  $("#exclusion-criteria").value = (defaults.exclusion_criteria || []).join("\n");

  const groups = [
    ["自动检索 / API", config.sources.filter((source) => source.mode === "automated")],
    ["网页辅助 / 人工核验", config.sources.filter((source) => source.mode !== "automated")],
  ];
  $("#source-list").innerHTML = groups.map(([title, sources]) => `
    <div class="source-group">
      <div class="source-group-title">${escapeHtml(title)}</div>
      ${sources.map((source) => `<label class="source-option" title="${source.configured ? source.mode : "尚未配置 API Key"}">
        <input type="checkbox" name="source" value="${escapeHtml(source.id)}" ${defaults.sources.includes(source.id) ? "checked" : ""}>
        <span>${escapeHtml(source.label)}</span>
        <i class="${source.configured ? (source.mode === "manual-web" ? "manual" : "") : "unconfigured"}"></i>
      </label>`).join("")}
    </div>`).join("");
  const zoteroButton = $("#save-zotero");
  zoteroButton.dataset.configured = String(Boolean(config.zotero?.configured));
  zoteroButton.title = config.zotero?.configured
    ? `保存到本机 Zotero ${config.zotero.version || ""} 当前选中的收藏夹`
    : "未检测到本机 Zotero，请先启动 Zotero";
  const levels = config.journal_ranking?.levels || ["TOP", "一级A", "一级B", "二级A", "二级B", "三级", "待核验"];
  $("#filter-journal-level").innerHTML = '<option value="">全部期刊等级</option>' + levels.map((level) => `<option value="${escapeHtml(level)}">${escapeHtml(level)}</option>`).join("");
  refreshIcons();
}

function currentRecords() {
  if (!state.data?.records) return [];
  const text = $("#filter-text").value.trim().toLowerCase();
  const source = $("#filter-source").value;
  const journalLevel = $("#filter-journal-level").value;
  const screening = $("#filter-screening").value;
  const oaOnly = $("#filter-oa").checked;
  const records = state.data.records.filter((record) => {
    const ranking = record.journal_ranking || {};
    const haystack = [record.title, ...(record.authors || []), record.venue, ranking.level, ranking.category, ...(record.retrieval_sources || []), ...(record.methods || [])].join(" ").toLowerCase();
    return (!text || haystack.includes(text)) &&
      (!source || (record.retrieval_sources || []).includes(source)) &&
      (!journalLevel || (ranking.level || "待核验") === journalLevel) &&
      (!screening || (record.screening_status || "unscreened") === screening) &&
      (!oaOnly || record.open_access_pdf_url);
  });
  const sort = $("#sort-results").value;
  records.sort((a, b) => {
    if (sort === "score") return (b.total_score || 0) - (a.total_score || 0) || (b.year || 0) - (a.year || 0);
    if (sort === "citations") return (b.citation_count || 0) - (a.citation_count || 0) || (b.year || 0) - (a.year || 0);
    if (sort === "title") return (a.title || "").localeCompare(b.title || "");
    return (b.year || 0) - (a.year || 0) || (b.total_score || 0) - (a.total_score || 0);
  });
  return records;
}

function screeningLabel(status) {
  return ({ include: "纳入", maybe: "待定", exclude: "排除", unscreened: "未筛选" })[status || "unscreened"];
}

function syncSelectionControls() {
  const visibleRecords = currentRecords();
  const selectedVisible = visibleRecords.filter((record) => state.selectedRecordIds.has(record.record_id)).length;
  const selectedRecords = (state.data?.records || []).filter((record) => state.selectedRecordIds.has(record.record_id));
  const selectedPdfs = selectedRecords.filter((record) => safeUrl(record.open_access_pdf_url));
  const selectAll = $("#select-visible-records");
  selectAll.disabled = visibleRecords.length === 0;
  selectAll.checked = visibleRecords.length > 0 && selectedVisible === visibleRecords.length;
  selectAll.indeterminate = selectedVisible > 0 && selectedVisible < visibleRecords.length;
  const downloadButton = $("#batch-download");
  downloadButton.disabled = selectedPdfs.length === 0;
  downloadButton.querySelector("span").textContent = `批量下载 ${selectedPdfs.length}`;
  downloadButton.title = selectedPdfs.length ? `下载选中的 ${selectedPdfs.length} 篇开放PDF` : "选中文献中没有开放PDF";
  const zoteroButton = $("#save-zotero");
  const zoteroConfigured = zoteroButton.dataset.configured === "true";
  zoteroButton.disabled = !zoteroConfigured || selectedRecords.length === 0;
  zoteroButton.querySelector("span").textContent = `保存到本机 Zotero ${selectedRecords.length}`;
  zoteroButton.title = !zoteroConfigured ? "未检测到本机 Zotero，请先启动 Zotero" :
    (selectedRecords.length ? `保存选中的 ${selectedRecords.length} 条文献到 Zotero 当前收藏夹` : "请先选择文献");
}

function renderResults() {
  const records = currentRecords();
  $("#results-body").innerHTML = records.map((record) => {
    const authors = (record.authors || []).join(", ") || "作者信息缺失";
    const source = sourceLabel((record.retrieval_sources || [record.source])[0]);
    const status = record.screening_status || "unscreened";
    const translation = state.translations[record.record_id] || {};
    const pdfUrl = safeUrl(record.open_access_pdf_url);
    const ranking = record.journal_ranking || {};
    const journalLevel = ranking.level || "待核验";
    return `<tr>
      <td class="select-column"><input class="result-select" type="checkbox" data-select-record="${escapeHtml(record.record_id)}" aria-label="选择 ${escapeHtml(record.title)}" ${state.selectedRecordIds.has(record.record_id) ? "checked" : ""}></td>
      <td><div class="paper-title-row"><button class="paper-title" data-record="${escapeHtml(record.record_id)}">${escapeHtml(record.title)}</button><button class="translate-inline" data-translate-title="${escapeHtml(record.record_id)}" title="翻译题名" ${translation.title ? "disabled" : ""}>${icon("languages", 13)}</button></div>${translation.title ? `<div class="paper-title-translation">${escapeHtml(translation.title)}</div>` : ""}<div class="paper-authors">${escapeHtml(authors)}</div></td>
      <td><strong>${escapeHtml(record.year || "-")}</strong></td>
      <td><span class="venue-text" title="${escapeHtml(record.venue || "")}">${escapeHtml(record.venue || "未注明")}</span><span class="journal-level ${journalLevel === "待核验" ? "unverified" : ""}" title="${escapeHtml(ranking.note || "")}">${escapeHtml(journalLevel)}${ranking.category ? ` · ${escapeHtml(ranking.category)}` : ""}</span></td>
      <td><span class="source-tag">${escapeHtml(source)}</span></td>
      <td><span class="score-tag" title="六维质量评分">${escapeHtml(record.total_score ?? "-")}</span></td>
      <td>${record.citation_count == null ? '<span class="muted-dash">-</span>' : Number(record.citation_count).toLocaleString()}</td>
      <td>${pdfUrl ? `<a class="oa-tag" href="${escapeHtml(pdfUrl)}" target="_blank" rel="noopener" title="打开原始 PDF">${icon("lock-open", 12)}开放 PDF</a>` : `<span class="muted-dash">${escapeHtml(record.evidence_depth === "abstract-available" ? "摘要" : "元数据")}</span>`}</td>
      <td><span class="screening-tag ${escapeHtml(status)}">${screeningLabel(status)}</span></td>
      <td><button class="icon-button row-action" data-record="${escapeHtml(record.record_id)}" title="查看详情与筛选">${icon("panel-right-open", 15)}</button></td>
    </tr>`;
  }).join("");
  $("#empty-state").classList.toggle("hidden", records.length > 0);
  $("#visible-count").textContent = `显示 ${records.length} / ${state.data?.records?.length || 0} 条`;
  $$('[data-record]').forEach((button) => button.addEventListener("click", () => openDetail(button.dataset.record)));
  $$('[data-translate-title]').forEach((button) => button.addEventListener("click", () => translateRecordField(button.dataset.translateTitle, "title")));
  $$('[data-select-record]').forEach((input) => input.addEventListener("change", () => {
    if (input.checked) state.selectedRecordIds.add(input.dataset.selectRecord);
    else state.selectedRecordIds.delete(input.dataset.selectRecord);
    syncSelectionControls();
  }));
  syncSelectionControls();
  refreshIcons();
}

function updateScreeningMetrics() {
  if (!state.data?.records) return;
  const counts = { include: 0, maybe: 0, exclude: 0 };
  state.data.records.forEach((record) => { if (counts[record.screening_status] !== undefined) counts[record.screening_status] += 1; });
  state.data.search_metrics ||= {};
  state.data.search_metrics.records_included = counts.include;
  state.data.search_metrics.records_maybe = counts.maybe;
  state.data.search_metrics.records_excluded = counts.exclude;
  state.data.search_metrics.records_screened = counts.include + counts.maybe + counts.exclude;
}

function renderMetrics() {
  const records = state.data?.records || [];
  const logs = state.data?.search_logs || [];
  const years = records.map((record) => Number(record.year)).filter(Boolean);
  const scored = records.map((record) => Number(record.total_score)).filter(Number.isFinite);
  updateScreeningMetrics();
  $("#metric-records").textContent = records.length.toLocaleString();
  $("#metric-sources").textContent = logs.filter((log) => log.execution_status === "success").length;
  $("#metric-pdfs").textContent = records.filter((record) => record.open_access_pdf_url).length;
  $("#metric-years").textContent = years.length ? `${Math.min(...years)}-${Math.max(...years)}` : "-";
  $("#metric-score").textContent = scored.length ? Math.round(scored.reduce((a, b) => a + b, 0) / scored.length) : "-";
  $("#metric-screened").textContent = state.data?.search_metrics?.records_screened || 0;
  $("#result-count-badge").textContent = records.length;
  $("#log-count-badge").textContent = logs.length;
}

function renderFilters() {
  const ids = [...new Set((state.data?.records || []).flatMap((record) => record.retrieval_sources || [record.source]).filter(Boolean))];
  const previous = $("#filter-source").value;
  $("#filter-source").innerHTML = '<option value="">全部来源</option>' + ids.map((id) => `<option value="${escapeHtml(id)}">${escapeHtml(sourceLabel(id))}</option>`).join("");
  if (ids.includes(previous)) $("#filter-source").value = previous;
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString("zh-CN", { hour12: false, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function renderLogs() {
  const statusLabels = { success: "成功", "manual-check-needed": "人工核验", failed: "失败" };
  $("#logs-body").innerHTML = (state.data?.search_logs || []).map((log) => {
    const url = safeUrl(log.query_parameters?.search_url || log.query_parameters?.request_url);
    return `<tr><td><strong>${escapeHtml(sourceLabel(log.source_id))}</strong></td>
      <td><span class="status-tag ${escapeHtml(log.execution_status)}">${escapeHtml(statusLabels[log.execution_status] || log.execution_status)}</span></td>
      <td>${Number(log.records_kept || 0).toLocaleString()}</td>
      <td class="query-cell" title="${escapeHtml(log.query)}">${escapeHtml(log.query)}</td>
      <td>${escapeHtml(formatDate(log.executed_at))}</td>
      <td>${url ? `<a class="icon-button row-action" href="${escapeHtml(url)}" target="_blank" rel="noopener" title="打开来源">${icon("external-link", 14)}</a>` : '<span class="muted-dash">-</span>'}</td></tr>`;
  }).join("");
  refreshIcons();
}

function renderCoverage() {
  const records = state.data?.records || [];
  const counts = {};
  records.forEach((record) => (record.retrieval_sources || [record.source]).forEach((source) => { counts[source] = (counts[source] || 0) + 1; }));
  const maximum = Math.max(1, ...Object.values(counts));
  const ordered = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  $("#coverage-bars").innerHTML = ordered.length ? ordered.map(([source, count]) => `<div class="coverage-row"><span>${escapeHtml(sourceLabel(source))}</span><div class="coverage-track"><span style="width:${Math.max(4, count / maximum * 100)}%"></span></div><strong>${count}</strong></div>`).join("") : '<div class="empty-state"><p>检索完成后显示各来源覆盖情况。</p></div>';

  const protocol = state.data?.search_protocol || {};
  const metrics = state.data?.search_metrics || {};
  const gaps = state.data?.verification_gaps || [];
  const advisories = state.data?.coverage_advisories || [];
  $("#handoff-content").innerHTML = `
    <div class="handoff-item"><span>${icon("clipboard-check", 13)}检索协议</span><p>${escapeHtml(protocol.mode === "systematic" ? "系统检索" : "探索检索")} · ${escapeHtml(protocol.ranking || "-")}<br>${(protocol.inclusion_criteria || []).length} 条纳入标准，${(protocol.exclusion_criteria || []).length} 条排除标准</p></div>
    <div class="handoff-item"><span>${icon("copy-check", 13)}去重记录</span><p>原始 ${metrics.records_retrieved ?? records.length} 条，移除 ${metrics.duplicates_removed || 0} 条，保留 ${records.length} 条。</p></div>
    <div class="handoff-item"><span>${icon(advisories.length ? "triangle-alert" : "circle-check", 13)}分布偏斜</span>${advisories.length ? `<div class="advisory-list">${advisories.map((item) => `<div class="advisory">${escapeHtml(item.dimension)}：${escapeHtml(item.value)} 占 ${Math.round(item.share * 100)}%（${item.count}/${item.known_count}）</div>`).join("")}</div>` : "<p>当前候选集未触发 70% 集中度提示。</p>"}</div>
    <div class="handoff-item"><span>${icon(gaps.length ? "triangle-alert" : "badge-check", 13)}核验缺口</span><p>${gaps.length ? gaps.map(escapeHtml).join("<br>") : "自动来源未报告执行失败。"}</p></div>
    <div class="handoff-item"><span>${icon("waypoints", 13)}模块交接</span><p>候选集可交给文献筛选、证据综合和引用管理模块；用户筛选决定随会话保存。</p></div>`;
  refreshIcons();
}

function scoreLabel(key) {
  return ({ topic_relevance: "主题相关", method_value: "方法价值", data_relevance: "数据适配", source_quality: "来源质量", evidence_completeness: "证据完整", open_materials: "开放材料" })[key] || key;
}

async function translateRecordField(recordId, field) {
  const record = state.data?.records?.find((item) => item.record_id === recordId);
  if (!record) return;
  const translation = state.translations[recordId] ||= {};
  if (field === "abstract" && translation.abstract) {
    translation.abstractView = translation.abstractView === "zh" ? "original" : "zh";
    openDetail(recordId);
    return;
  }
  const text = field === "title" ? record.title : record.abstract;
  if (!text) return showToast(field === "title" ? "当前文献没有可翻译的题名。" : "当前数据源没有提供摘要。");
  const buttons = $$(`[data-translate-${field}="${CSS.escape(recordId)}"]`);
  buttons.forEach((button) => { button.disabled = true; button.classList.add("translating"); });
  try {
    const result = await fetchJson("/api/translate-text", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
    });
    translation[field] = result.translation;
    if (field === "abstract") translation.abstractView = "zh";
    renderResults();
    if (state.currentRecordId === recordId) openDetail(recordId);
    showToast(field === "title" ? "题名中文翻译已生成" : "摘要中文翻译已生成");
  } catch (error) {
    showToast(error.message);
  } finally {
    buttons.forEach((button) => { button.disabled = false; button.classList.remove("translating"); });
  }
}

function openDetail(recordId) {
  const record = state.data?.records?.find((item) => item.record_id === recordId);
  if (!record) return;
  state.currentRecordId = recordId;
  const pdf = safeUrl(record.open_access_pdf_url);
  const page = safeUrl(record.url);
  const doi = record.doi ? `https://doi.org/${encodeURIComponent(record.doi)}` : "";
  const topics = [...(record.fields_of_study || []), ...(record.jel_codes || []).map((code) => `JEL ${code}`), ...(record.methods || [])];
  const scores = record.quality_scores || {};
  const translation = state.translations[recordId] || {};
  const showChineseAbstract = translation.abstract && translation.abstractView === "zh";
  const abstractText = showChineseAbstract ? translation.abstract : (record.abstract || "当前数据源未提供摘要，建议打开来源页面进一步核验。");
  const ranking = record.journal_ranking || {};
  $("#detail-content").innerHTML = `
    <div class="detail-kicker">${escapeHtml((record.retrieval_sources || []).map(sourceLabel).join(" · "))}</div>
    <h2>${escapeHtml(record.title)}</h2>
    ${translation.title ? `<p class="translated-title">${escapeHtml(translation.title)}</p>` : ""}
    <div class="detail-authors">${escapeHtml((record.authors || []).join(", ") || "作者信息缺失")}</div>
    <div class="detail-actions">
      ${pdf ? `<a class="primary" href="${escapeHtml(pdf)}" target="_blank" rel="noopener">${icon("file-down", 14)}开放全文</a>` : ""}
      ${page ? `<a href="${escapeHtml(page)}" target="_blank" rel="noopener">${icon("external-link", 14)}来源页面</a>` : ""}
      ${doi ? `<a href="${escapeHtml(doi)}" target="_blank" rel="noopener">${icon("link", 14)}DOI</a>` : ""}
    </div>
    <div class="detail-meta">
      <div><span>年份</span><strong>${escapeHtml(record.year || "-")}</strong></div><div><span>综合评分</span><strong>${escapeHtml(record.total_score ?? "-")} / 100</strong></div>
      <div><span>期刊来源</span><strong>${escapeHtml(record.venue || "-")}</strong></div><div><span>期刊等级</span><strong>${escapeHtml(ranking.level || "待核验")}${ranking.category ? ` · ${escapeHtml(ranking.category)}` : ""}</strong></div>
      <div><span>DOI</span><strong>${escapeHtml(record.doi || "-")}</strong></div><div><span>核验状态</span><strong>${escapeHtml(record.verification_status || "metadata-only")}</strong></div>
    </div>
    <div class="detail-section"><h3>期刊定级依据</h3><p>${escapeHtml(ranking.note || "未与当前期刊定级清单匹配，需人工核验。")}</p></div>
    <div class="detail-section"><h3>六维评分</h3><div class="score-grid">${Object.entries(scores).map(([key, value]) => `<div class="score-item"><span>${escapeHtml(scoreLabel(key))}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div></div>
    <div class="detail-section"><h3>标题摘要筛选</h3><div class="screening-controls"><button data-screen="include">纳入</button><button data-screen="maybe">待定</button><button data-screen="exclude">排除</button></div><textarea id="screening-reason" class="screening-reason" placeholder="记录纳入或排除原因">${escapeHtml(record.screening_reason || "")}</textarea></div>
    <div class="detail-section"><div class="detail-section-heading"><h3>摘要</h3>${record.abstract ? `<button class="inline-command" data-translate-abstract="${escapeHtml(recordId)}">${icon("languages", 13)}${translation.abstract ? (showChineseAbstract ? "显示原文" : "显示中文") : "翻译摘要"}</button>` : ""}</div>${showChineseAbstract ? '<div class="translation-label">中文翻译</div>' : ""}<p>${escapeHtml(abstractText)}</p></div>
    <div class="detail-section"><h3>主题、方法与分类</h3><div class="chip-list">${topics.length ? topics.map((topic) => `<span>${escapeHtml(topic)}</span>`).join("") : "<span>暂无分类</span>"}</div></div>
    <div class="detail-section"><h3>相关性说明</h3><p>${escapeHtml(record.relevance_note || "尚未评分")}</p></div>`;
  $$('[data-screen]').forEach((button) => button.addEventListener("click", () => saveScreening(button.dataset.screen)));
  $$('[data-translate-abstract]').forEach((button) => button.addEventListener("click", () => translateRecordField(button.dataset.translateAbstract, "abstract")));
  $("#detail-drawer").classList.add("open");
  $("#detail-drawer").setAttribute("aria-hidden", "false");
  $("#drawer-backdrop").classList.add("open");
  refreshIcons();
}

async function saveScreening(status) {
  const record = state.data?.records?.find((item) => item.record_id === state.currentRecordId);
  if (!record) return;
  const reason = $("#screening-reason").value.trim();
  try {
    if (state.data.session_id) {
      await fetchJson("/api/screen", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: state.data.session_id, record_id: record.record_id, status, reason }) });
    }
    record.screening_status = status;
    record.screening_reason = reason || null;
    renderResults(); renderMetrics(); renderCoverage();
    showToast(`已标记为“${screeningLabel(status)}”`);
  } catch (error) { showToast(error.message); }
}

function closeDetail() {
  $("#detail-drawer").classList.remove("open");
  $("#detail-drawer").setAttribute("aria-hidden", "true");
  $("#drawer-backdrop").classList.remove("open");
}

async function renderSessions() {
  try {
    const data = await fetchJson("/api/sessions");
    $("#session-count-badge").textContent = data.sessions.length;
    $("#sessions-body").innerHTML = data.sessions.map((session) => `<tr>
      <td>${escapeHtml(formatDate(session.created_at))}<div class="session-hash" title="${escapeHtml(session.result_sha256)}">${escapeHtml(session.result_sha256)}</div></td>
      <td><strong>${escapeHtml(session.research_question)}</strong><div class="paper-authors">${escapeHtml(session.working_query)}</div></td>
      <td>${escapeHtml(session.mode)}<br><span class="muted-dash">${escapeHtml(session.ranking)}</span></td>
      <td>${session.source_ids.length}</td><td>${session.record_count} / ${session.open_pdf_count}</td>
      <td><button class="icon-button row-action" data-session="${escapeHtml(session.session_id)}" title="载入会话">${icon("folder-open", 14)}</button></td></tr>`).join("");
    $$('[data-session]').forEach((button) => button.addEventListener("click", () => loadSession(button.dataset.session)));
    refreshIcons();
  } catch (error) { showToast(error.message); }
}

async function loadSession(sessionId) {
  setStatus("载入会话", "busy");
  try {
    const data = await fetchJson(`/api/sessions/${encodeURIComponent(sessionId)}`);
    applyData(data, "历史会话");
    showToast(`已载入会话 ${sessionId}`);
  } catch (error) { setStatus("载入失败", "error"); showToast(error.message); }
}

function applyData(data, message = "结果已载入") {
  state.data = data;
  state.selectedRecordIds.clear();
  $("#result-context").textContent = data.input_summary ? `当前研究问题：${data.input_summary}` : "当前检索结果";
  renderFilters(); renderMetrics(); renderResults(); renderLogs(); renderCoverage(); renderSessions();
  setStatus(message, "ready");
}

function toggleVisibleRecords(checked) {
  currentRecords().forEach((record) => {
    if (checked) state.selectedRecordIds.add(record.record_id);
    else state.selectedRecordIds.delete(record.record_id);
  });
  renderResults();
}

function downloadSelectedPdfs() {
  const selected = (state.data?.records || []).filter((record) =>
    state.selectedRecordIds.has(record.record_id) && safeUrl(record.open_access_pdf_url)
  );
  if (!selected.length) return showToast("请先选择带开放PDF的文献。");
  selected.forEach((record) => {
    const link = document.createElement("a");
    link.href = safeUrl(record.open_access_pdf_url);
    link.target = "_blank";
    link.rel = "noopener";
    link.download = `${String(record.title || "paper").replace(/[\\/:*?\"<>|]/g, "_").slice(0, 100)}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  });
  showToast(`已提交 ${selected.length} 篇开放PDF；首次使用时请允许浏览器进行多个下载。`);
}

async function saveSelectedToZotero() {
  const records = (state.data?.records || []).filter((record) => state.selectedRecordIds.has(record.record_id));
  if (!records.length) return showToast("请先选择要保存的文献。");
  setLoading(true, "正在将选中文献保存到本机 Zotero。请勿关闭 Zotero。");
  try {
    const result = await fetchJson("/api/zotero", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ records }),
    });
    const attachmentNote = result.attachments_requested
      ? `，PDF附件 ${result.attachments_saved}/${result.attachments_requested}`
      : "";
    const attachmentFailure = result.attachment_failed_count ? `（${result.attachment_failed_count} 个PDF下载失败）` : "";
    showToast(result.failed_count ? `本机 Zotero 已保存 ${result.saved} 条，${result.failed_count} 条失败` : `已保存 ${result.saved} 条文献到 Zotero 当前收藏夹${attachmentNote}${attachmentFailure}`);
  } catch (error) { showToast(error.message); }
  finally { setLoading(false); }
}

async function runSearch(event) {
  event.preventDefault();
  const payload = currentSearchContext();
  setLoading(true);
  setStatus("检索进行中", "busy");
  try {
    const data = await fetchJson("/api/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    applyData(data, "检索完成");
    showToast(`检索完成：${data.search_metrics?.records_retrieved || 0} 条命中，去重后 ${data.records?.length || 0} 条`);
  } catch (error) { setStatus("检索失败", "error"); showToast(error.message); }
  finally { setLoading(false); }
}

async function translateQuestion({ silent = false } = {}) {
  const question = $("#research-question").value.trim();
  if (!question) { if (!silent) showToast("请先填写经济学问题。"); return; }
  const button = $("#translate-button");
  const requestedQuestion = question;
  button.disabled = true; button.classList.add("translating");
  try {
    const result = await fetchJson("/api/protocol", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_question: question }) });
    if ($("#research-question").value.trim() === requestedQuestion) {
      $("#working-query").value = result.working_query;
      $("#concept-policy").value = (result.concept_blocks?.[0]?.terms || []).join(", ");
      $("#concept-outcome").value = (result.concept_blocks?.[1]?.terms || []).join(", ");
      $("#requested-methods").value = (result.requested_methods || []).join(", ");
      $("#inclusion-criteria").value = (result.inclusion_criteria || []).join("\n");
      $("#exclusion-criteria").value = (result.exclusion_criteria || []).join("\n");
      $("#protocol-confirmed").checked = false;
      if (!silent) showToast(result.translation_source === "local-economics-glossary" ? "已使用本地经济学术语同步检索协议" : "检索式与检索协议已同步更新");
    }
  } catch (error) { if (!silent) showToast(error.message); }
  finally { button.disabled = false; button.classList.remove("translating"); }
}

async function loadSample() {
  setStatus("载入中", "busy");
  try {
    const data = await fetchJson("/api/sample");
    applyData(data, "最近结果");
    showToast(data.records?.length ? `已载入 ${data.records.length} 条最近结果` : "暂无最近检索结果");
  } catch (error) { setStatus("载入失败", "error"); showToast(error.message); }
}

async function importCorpus(file) {
  if (!file) return;
  setLoading(true, "正在验证、标准化并合并已有文献语料。");
  try {
    const parsed = JSON.parse(await file.text());
    const records = Array.isArray(parsed) ? parsed : (parsed.literature_corpus || parsed.records);
    if (!Array.isArray(records)) throw new Error("JSON 中未找到 records 或 literature_corpus 数组。");
    const data = await fetchJson("/api/import", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ records, existing_records: state.data?.records || [], search_context: currentSearchContext() }),
    });
    applyData(data, "语料已合并");
    showToast(`已导入并合并 ${records.length} 条已有语料`);
  } catch (error) { showToast(`导入失败：${error.message}`); }
  finally { setLoading(false); $("#corpus-file").value = ""; }
}

function downloadBlob(content, mime, filename) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type: mime }));
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

function exportData(type) {
  if (!state.data?.records?.length) return showToast("当前没有可导出的文献。");
  let content, mime, extension;
  if (type === "json") {
    content = JSON.stringify(state.data, null, 2); mime = "application/json"; extension = "json";
  } else {
    const columns = ["title", "authors", "year", "venue", "journal_level", "journal_category", "issn", "doi", "sources", "score", "screening_status", "screening_reason", "citation_count", "open_access_pdf_url", "url"];
    const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const rows = currentRecords().map((record) => [record.title, (record.authors || []).join("; "), record.year, record.venue, record.journal_ranking?.level || "待核验", record.journal_ranking?.category, (record.issn || []).join("; "), record.doi, (record.retrieval_sources || []).join("; "), record.total_score, record.screening_status, record.screening_reason, record.citation_count, record.open_access_pdf_url, record.url].map(quote).join(","));
    content = "\ufeff" + [columns.join(","), ...rows].join("\r\n"); mime = "text/csv;charset=utf-8"; extension = "csv";
  }
  downloadBlob(content, mime, `literature-search-${new Date().toISOString().slice(0, 10)}.${extension}`);
  showToast(`已生成 ${extension.toUpperCase()} 导出文件`);
}

async function exportCitation() {
  const records = currentRecords().filter((record) => record.screening_status !== "exclude");
  if (!records.length) return showToast("当前没有可导出的文献。");
  const format = $("#citation-format").value;
  try {
    const data = await fetchJson("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ format, records }) });
    downloadBlob(data.content, data.content_type, `literature-search-${new Date().toISOString().slice(0, 10)}.${data.extension}`);
    showToast(`已导出 ${records.length} 条 ${format.toUpperCase()} 引用`);
  } catch (error) { showToast(error.message); }
}

function bindEvents() {
  $("#search-form").addEventListener("submit", runSearch);
  $("#load-sample").addEventListener("click", loadSample);
  $("#select-visible-records").addEventListener("change", (event) => toggleVisibleRecords(event.currentTarget.checked));
  $("#batch-download").addEventListener("click", downloadSelectedPdfs);
  $("#save-zotero").addEventListener("click", saveSelectedToZotero);
  $("#translate-button").addEventListener("click", () => translateQuestion());
  $("#auto-translate").addEventListener("change", (event) => { if (event.currentTarget.checked) translateQuestion(); });
  $("#research-question").addEventListener("input", () => {
    clearTimeout(state.translationTimer);
    if ($("#auto-translate").checked) state.translationTimer = setTimeout(() => translateQuestion({ silent: true }), 700);
  });
  ["#filter-text", "#filter-source", "#filter-journal-level", "#filter-oa", "#filter-screening", "#sort-results"].forEach((selector) => $(selector).addEventListener("input", renderResults));
  $$(".tabs button").forEach((button) => button.addEventListener("click", () => {
    $$(".tabs button").forEach((item) => item.classList.toggle("active", item === button));
    $$(".tab-view").forEach((view) => view.classList.toggle("active", view.id === `view-${button.dataset.tab}`));
    state.activeTab = button.dataset.tab;
    if (state.activeTab === "sessions") renderSessions();
  }));
  $$("[data-step]").forEach((button) => button.addEventListener("click", () => {
    const input = $("#result-limit");
    input.value = Math.min(100, Math.max(1, Number(input.value || 20) + Number(button.dataset.step)));
  }));
  $("#toggle-sources").addEventListener("click", (event) => {
    const inputs = $$('input[name="source"]');
    const shouldCheck = inputs.some((input) => !input.checked);
    inputs.forEach((input) => { input.checked = shouldCheck; });
    event.currentTarget.textContent = shouldCheck ? "取消全选" : "全部选择";
  });
  $("#search-mode").addEventListener("change", (event) => {
    if (event.currentTarget.value === "systematic") showToast("系统检索需要确认检索协议后才能执行。");
  });
  $("#close-drawer").addEventListener("click", closeDetail);
  $("#drawer-backdrop").addEventListener("click", closeDetail);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeDetail(); });
  $("#export-json").addEventListener("click", () => exportData("json"));
  $("#export-csv").addEventListener("click", () => exportData("csv"));
  $("#export-citation").addEventListener("click", exportCitation);
  $("#import-corpus").addEventListener("click", () => $("#corpus-file").click());
  $("#corpus-file").addEventListener("change", (event) => importCorpus(event.target.files[0]));
  $("#refresh-sessions").addEventListener("click", renderSessions);
}

async function init() {
  bindEvents(); refreshIcons();
  try {
    const config = await fetchJson("/api/config");
    populateConfig(config);
    await loadSample();
  } catch (error) { setStatus("服务异常", "error"); showToast(error.message); }
}

init();
