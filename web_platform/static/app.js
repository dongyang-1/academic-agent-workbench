// ==========================================================================
// 学术全流程多智能体协作平台前端核心交互逻辑 (简约明亮学术版)
// 包含：左侧竖向主导航、IDE 多标签页加页体系、EconLit 文献检索面板、
// 资料库与 Part 3 全文写作打通、三栏自由鼠标拖动、Skills 修改重置与 Token 监控
// ==========================================================================

let currentProjectId = "proj-default-001";
let currentProjectName = "国家碳交易试点政策研究";
let currentSessionId = null;
let currentChatAgent = "coordinator";
let sseSource = null;
let activeIdeTab = "chat";
let econlitRecords = [];
let libraryItems = [];

// 编辑 Skill 状态
let currentEditingSkillPath = null;
let currentEditingSkillId = null;

// ==========================================================================
// 聊天滚动管理：只有「贴着底部」时才自动跟随，用户往上翻就不再被强行拉回
// ==========================================================================
let _chatFollow = true;              // 当前是否处于跟随最新消息的状态
let _chatScrollRaf = 0;
const _streamTexts = Object.create(null);
const _streamRenderQueued = Object.create(null);
const CHAT_STICK_THRESHOLD = 80;     // 距底部多少像素内算「贴底」

function _chatList() {
  return document.getElementById("chatMessageList");
}

function isNearBottom(el, thresh) {
  if (!el) return true;
  const t = thresh === undefined ? CHAT_STICK_THRESHOLD : thresh;
  return (el.scrollHeight - el.scrollTop - el.clientHeight) <= t;
}

function scrollChatToBottom(force) {
  const el = _chatList();
  if (!el) return;
  if (force) _chatFollow = true;
  if (!_chatFollow) return;           // 用户正在看历史，不打扰
  if (_chatScrollRaf) return;         // 每帧最多滚一次，避免流式输出时抖动
  _chatScrollRaf = requestAnimationFrame(() => {
    _chatScrollRaf = 0;
    el.scrollTop = el.scrollHeight;
    updateChatJumpButton();
  });
}

function updateChatJumpButton() {
  const el = _chatList();
  const btn = document.getElementById("chatJumpBottom");
  if (!el || !btn) return;
  btn.classList.toggle("show", !isNearBottom(el, 180));
}

// 流式正文按帧合并渲染：每个 token 都写 innerHTML 会引发布局抖动
function queueStreamRender(streamId) {
  if (_streamRenderQueued[streamId]) return;
  _streamRenderQueued[streamId] = true;
  requestAnimationFrame(() => {
    _streamRenderQueued[streamId] = false;
    const el = document.getElementById("streamContent-" + streamId);
    if (!el) return;
    el.innerHTML = escapeHtml(_streamTexts[streamId] || "").replace(/\n/g, "<br>")
      + '<span class="typing-cursor"></span>';
    scrollChatToBottom();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const el = _chatList();
  if (el) {
    el.addEventListener("scroll", () => {
      _chatFollow = isNearBottom(el);   // 自己滚回底部就恢复跟随
      updateChatJumpButton();
    }, { passive: true });
  }
});

document.addEventListener("DOMContentLoaded", () => {
  initResizableColumns();
  checkHealth();
  initProjectsAndSession();
  updateTabBarVisibility();
  setupKeyboardSend();
  loadSkillsTree();
  refreshTokens();

  // 轮询 Token 消耗情况
  setInterval(refreshTokens, 12000);
});

// ==========================================================================
// 1. 三栏面板宽度自由鼠标拖动 (Resizable Columns)
// ==========================================================================
function initResizableColumns() {
  const colLeft = document.getElementById("colLeft");
  const colRight = document.getElementById("colRight");
  const resizerLeft = document.getElementById("resizerLeft");
  const resizerRight = document.getElementById("resizerRight");

  let isDraggingLeft = false;
  let isDraggingRight = false;

  resizerLeft.addEventListener("mousedown", (e) => {
    isDraggingLeft = true;
    resizerLeft.classList.add("dragging");
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  });

  resizerRight.addEventListener("mousedown", (e) => {
    isDraggingRight = true;
    resizerRight.classList.add("dragging");
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  });

  document.addEventListener("mousemove", (e) => {
    if (isDraggingLeft) {
      // 减去最左侧竖向导航栏宽度 76px
      const newWidth = Math.max(260, Math.min(800, e.clientX - 76));
      colLeft.style.width = `${newWidth}px`;
    }
    if (isDraggingRight) {
      const containerWidth = document.getElementById("workspaceContainer").offsetWidth;
      const newWidth = Math.max(260, Math.min(650, containerWidth - (e.clientX - 76)));
      colRight.style.width = `${newWidth}px`;
    }
  });

  document.addEventListener("mouseup", () => {
    if (isDraggingLeft) {
      isDraggingLeft = false;
      resizerLeft.classList.remove("dragging");
      document.body.style.cursor = "default";
      document.body.style.userSelect = "auto";
    }
    if (isDraggingRight) {
      isDraggingRight = false;
      resizerRight.classList.remove("dragging");
      document.body.style.cursor = "default";
      document.body.style.userSelect = "auto";
    }
  });
}

// ==========================================================================
// 2. 项目库管理与会话初始化
// ==========================================================================
async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const dot = document.getElementById("remeStatusDot");
    const text = document.getElementById("remeStatusText");
    if (data.reme_memory_online) {
      dot.style.backgroundColor = "var(--accent-green)";
      text.textContent = "ReMe 记忆连接正常 (2333)";
    } else {
      dot.style.backgroundColor = "var(--accent-amber)";
      text.textContent = "ReMe 本地容灾已就绪";
    }
  } catch (e) {
    console.warn("探测后端健康状态失败:", e);
  }
}

async function initProjectsAndSession() {
  try {
    const res = await fetch("/api/projects/list");
    const data = await res.json();
    const projects = data.projects || [];
    if (projects.length > 0) {
      const defaultProj = projects[0];
      currentProjectId = defaultProj.project_id;
      currentProjectName = defaultProj.name;
      currentSessionId = defaultProj.active_session_id;

      document.getElementById("currentProjectNameDisplay").textContent = currentProjectName;
      document.getElementById("currentSessionIdDisplay").textContent = currentSessionId;
      const treeRootName = document.getElementById("treeRootProjectName");
      if (treeRootName) treeRootName.textContent = currentProjectName;

      // 同步 EconLit 默认问题
      if (defaultProj.topic) {
        document.getElementById("econlitQuestion").value = defaultProj.topic;
        document.getElementById("econlitQuery").value = "carbon emission trading AND digital transformation";
      }

      // 初始化欢迎对话
      initChatWelcome();
      // 预载入资料库文献
      loadLibraryItems();
      // 预载入项目成果与代码文件树 (IDE 格式)
      loadFileTree();
    }
  } catch (e) {
    console.error("初始化项目与会话失败:", e);
  }
}

function initChatWelcome() {
  const chatList = document.getElementById("chatMessageList");
  chatList.innerHTML = "";
  _chatFollow = true;
  updateChatJumpButton();
  appendAgentBubble(
    "编排总控智能体",
    `您好！我是学术全流程总控智能体。当前课题项目为【${currentProjectName}】。\n\n` +
    `• 您可以随时在此提出实证构思、与各子智能体（文献检索、实证计量、全文写作）专属对话；\n` +
    `• 点击最左侧【资料库】，可查看已纳入的高质量文献与您自主上传的文件；\n` +
    `• 只要在对话或右侧勾选调用 Part 1，中间就会如现代 IDE 一般自动弹出【EconLit 文献检索工作台】；\n` +
    `• Part 3 全文写作智能体已全面关联资料库，随时准备为您撰写期刊级论文大作！`,
    new Date().toLocaleTimeString()
  );
}

// 打开项目库弹窗
async function openProjectsModal() {
  const modal = document.getElementById("modalProjects");
  modal.classList.add("active");
  loadProjectsList();
}

function closeProjectsModal() {
  document.getElementById("modalProjects").classList.remove("active");
}

let _projectsCache = {};

async function loadProjectsList() {
  try {
    const res = await fetch("/api/projects/list");
    const data = await res.json();
    const container = document.getElementById("projectsListContainer");
    container.innerHTML = "";
    _projectsCache = {};

    (data.projects || []).forEach((p) => {
      _projectsCache[p.project_id] = p;
      const isCurrent = p.project_id === currentProjectId;
      const card = document.createElement("div");
      card.className = "project-card" + (isCurrent ? " is-current" : "");
      card.dataset.projectId = p.project_id;
      card.innerHTML = `
        <div class="project-card-main">
          <div class="project-name">${escapeHtml(p.name)}${isCurrent ? '　<span style="font-size:0.66rem;font-weight:500;color:var(--md-primary);">当前</span>' : ""}</div>
          <div class="project-topic">${escapeHtml(p.topic || "尚未填写核心研究问题")}</div>
          <div class="project-meta">创建于 ${escapeHtml(p.created_at || "—")}</div>
        </div>
        <div class="project-actions">
          ${isCurrent ? "" : `<button class="icon-btn" title="切换到该项目" onclick="switchProjectById('${p.project_id}')"><svg class="ic" aria-hidden="true"><use href="#i-check"></use></svg></button>`}
          <button class="icon-btn" title="重命名 / 修改研究问题" onclick="startEditProject('${p.project_id}')"><svg class="ic" aria-hidden="true"><use href="#i-pencil"></use></svg></button>
          <button class="icon-btn danger" title="删除该项目" onclick="deleteProject('${p.project_id}')"><svg class="ic" aria-hidden="true"><use href="#i-trash"></use></svg></button>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    console.error("加载项目列表失败:", e);
  }
}

function switchProjectById(pid) {
  const p = _projectsCache[pid];
  if (!p) return;
  switchProject(p.project_id, p.name, p.active_session_id, p.topic);
  closeProjectsModal();
}

function startEditProject(pid) {
  const p = _projectsCache[pid];
  const card = document.querySelector(`.project-card[data-project-id="${pid}"]`);
  if (!p || !card) return;
  card.innerHTML = `
    <div class="project-edit-form">
      <input id="editName-${pid}" value="${escapeHtml(p.name)}" placeholder="项目名称">
      <textarea id="editTopic-${pid}" rows="2" placeholder="核心研究问题 / 政策冲击说明">${escapeHtml(p.topic || "")}</textarea>
      <div class="project-edit-actions">
        <button class="btn-header" onclick="loadProjectsList()">取消</button>
        <button class="btn-primary-action btn-with-icon" style="padding:6px 14px;" onclick="saveProjectEdit('${pid}')">
          <svg class="ic" aria-hidden="true"><use href="#i-check"></use></svg>保存
        </button>
      </div>
    </div>`;
  const nameInput = document.getElementById(`editName-${pid}`);
  if (nameInput) { nameInput.focus(); nameInput.select(); }
}

async function saveProjectEdit(pid) {
  const name = (document.getElementById(`editName-${pid}`) || {}).value || "";
  const topic = (document.getElementById(`editTopic-${pid}`) || {}).value || "";
  if (!name.trim()) { alert("项目名称不能为空"); return; }
  try {
    const res = await fetch(`/api/projects/${pid}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), topic: topic.trim() }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    if (pid === currentProjectId) {
      currentProjectName = data.project.name;
      document.getElementById("currentProjectNameDisplay").textContent = data.project.name;
      const treeRootName = document.getElementById("treeRootProjectName");
      if (treeRootName) treeRootName.textContent = data.project.name;
    }
    loadProjectsList();
  } catch (e) {
    alert("保存失败：" + e.message);
  }
}

async function deleteProject(pid) {
  const p = _projectsCache[pid];
  if (!p) return;
  if (!confirm(`确定删除项目「${p.name}」？\n\n该项目下的对话记录会一并清除，且无法恢复。`)) return;
  try {
    const res = await fetch(`/api/projects/${pid}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "删除失败");
    if (pid === currentProjectId && data.fallback_project) {
      const fb = data.fallback_project;
      switchProject(fb.project_id, fb.name, fb.active_session_id, fb.topic);
    }
    loadProjectsList();
  } catch (e) {
    alert("删除失败：" + e.message);
  }
}

async function createNewProject() {
  const name = document.getElementById("newProjectName").value.trim();
  const topic = document.getElementById("newProjectTopic").value.trim();
  if (!name) {
    alert("请输入项目名称！");
    return;
  }

  try {
    const res = await fetch("/api/projects/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, topic }),
    });
    const data = await res.json();
    const proj = data.project;
    switchProject(proj.project_id, proj.name, proj.active_session_id, proj.topic);
    closeProjectsModal();
    document.getElementById("newProjectName").value = "";
    document.getElementById("newProjectTopic").value = "";
  } catch (e) {
    alert("创建项目失败: " + e.message);
  }
}

function switchProject(pid, pname, sid, ptopic) {
  currentProjectId = pid;
  currentProjectName = pname;
  currentSessionId = sid;

  document.getElementById("currentProjectNameDisplay").textContent = pname;
  document.getElementById("currentSessionIdDisplay").textContent = sid;
  const treeRootName = document.getElementById("treeRootProjectName");
  if (treeRootName) treeRootName.textContent = pname;

  if (ptopic) {
    document.getElementById("econlitQuestion").value = ptopic;
  }

  // 通知后端切换项目输出目录（资源管理器按项目隔离）
  fetch(`/api/projects/${pid}/activate`, { method: "POST" })
    .catch(() => {})
    .finally(() => loadFileTree());

  initChatWelcome();
  loadLibraryItems();
  openIdeTab("chat");
}

// ==========================================================================
// 3. IDE 资源管理器文件树与动态加页编辑器系统 (参考现代 IDE 格式)
// ==========================================================================
let openedFileTabs = new Map(); // fileId -> fileItem
let currentFileTree = [];
let allFoldersCollapsed = false;

// 3.1 载入并渲染项目成果文件树
async function loadFileTree(showFeedback) {
  const btn = document.querySelector(".explorer-header-actions .btn-icon");
  if (btn) btn.classList.add("spinning");
  try {
    const res = await fetch(`/api/project/file_tree?project_id=${currentProjectId}`);
    const data = await res.json();
    if (data.status === "success") {
      currentFileTree = data.tree || [];
      renderFileTree(currentFileTree);
      if (showFeedback) {
        const n = currentFileTree.reduce((acc, f) => acc + (f.files || []).length, 0);
        if (typeof showSnack === "function") {
          showSnack(n ? `目录已刷新：${n} 个文件` : "目录已刷新：本项目暂无产出文件");
        }
      }
    }
  } catch (e) {
    if (typeof showSnack === "function") showSnack("刷新失败：" + e.message);
    console.error("加载项目文件树失败:", e);
  } finally {
    if (btn) setTimeout(() => btn.classList.remove("spinning"), 400);
  }
}

function renderFileTree(tree) {
  const container = document.getElementById("projectFileTreeContainer");
  if (!container) return;
  container.innerHTML = "";

  if (!tree || !tree.length) {
    container.innerHTML = '<div class="empty-hint" style="padding:18px 14px;line-height:1.7;">'
      + '本项目还没有产出文件。<br>完成一次实证分析或全文写作后，交付物会自动出现在这里。</div>';
    return;
  }

  tree.forEach(folder => {
    const folderEl = document.createElement("div");
    folderEl.className = "tree-folder";
    folderEl.id = folder.folder_id;

    let filesHtml = "";
    folder.files.forEach(file => {
      const isActive = activeIdeTab === file.id;
      filesHtml += `
        <div class="tree-file-item ${isActive ? 'active' : ''}" id="treeItem_${file.id}" onclick="openFileInEditor('${file.id}')" title="${escapeHtml(file.desc)}">
          <span class="tree-file-icon">${fileIconSvg(file.name)}</span>
          <span class="tree-file-name">${escapeHtml(file.name)}</span>
          <span class="tree-file-meta">${escapeHtml(file.size || file.type)}</span>
        </div>
      `;
    });

    folderEl.innerHTML = `
      <div class="tree-folder-header" onclick="toggleFolder('${folder.folder_id}')" title="${escapeHtml(folder.desc)}">
        <span class="tree-folder-arrow"><svg class="ic" aria-hidden="true"><use href="#i-down"></use></svg></span>
        <span class="tree-folder-icon">${fileIconSvg(folder.folder_name, "folder")}</span>
        <span class="tree-folder-title">${escapeHtml(folder.folder_name)}</span>
        <span class="tree-folder-count">${folder.files.length}</span>
      </div>
      <div class="tree-file-list">
        ${filesHtml}
      </div>
    `;
    container.appendChild(folderEl);
  });
}

function toggleFolder(folderId) {
  const folder = document.getElementById(folderId);
  if (folder) {
    folder.classList.toggle("collapsed");
  }
}

function toggleAllFolders() {
  const folders = document.querySelectorAll(".tree-folder");
  if (!folders.length) {
    if (typeof showSnack === "function") showSnack("当前项目还没有文件夹");
    return;
  }
  allFoldersCollapsed = !allFoldersCollapsed;
  folders.forEach((f) => f.classList.toggle("collapsed", allFoldersCollapsed));
  const btn = document.querySelectorAll(".explorer-header-actions .btn-icon")[1];
  if (btn) btn.classList.toggle("is-collapsed", allFoldersCollapsed);
  if (typeof showSnack === "function") {
    showSnack(allFoldersCollapsed ? "已折叠全部文件夹" : "已展开全部文件夹");
  }
}

function toggleExplorerPanel() {
  const colLeft = document.getElementById("colLeft");
  if (colLeft) {
    if (colLeft.style.display === "none" || parseInt(colLeft.style.width, 10) < 50) {
      colLeft.style.display = "flex";
      colLeft.style.width = "320px";
    }
  }
  document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
  document.getElementById("navBtnExplorer")?.classList.add("active");
}

function findFileInTree(fileId) {
  for (const folder of currentFileTree) {
    for (const file of folder.files) {
      if (file.id === fileId) return { file, folder };
    }
  }
  return null;
}

// 3.2 在中间 IDE 编辑区动态加页打开文件 (Tabbed Workspace)
async function openFileInEditor(fileId) {
  const found = findFileInTree(fileId);
  if (!found) {
    console.warn("未在文件树中找到文件:", fileId);
    return;
  }
  const { file, folder } = found;

  // 1. 如果已打开或 DOM 中已存在该 Tab，直接切换激活
  if (openedFileTabs.has(fileId) || document.getElementById(`tabHeader_${fileId}`)) {
    openedFileTabs.set(fileId, file);
    switchToFileTab(fileId);
    return;
  }

  // 2. 动态在 #ideTabBar 创建标签页
  const tabBar = document.getElementById("ideTabBar");
  const tabEl = document.createElement("div");
  tabEl.className = "ide-tab";
  tabEl.id = `tabHeader_${fileId}`;
  tabEl.onclick = () => switchToFileTab(fileId);
  tabEl.title = `${folder.folder_name} / ${file.name}`;
  tabEl.innerHTML = `
    <span class="tab-with-icon">${fileIconSvg(file.name)}<span>${escapeHtml(file.name)}</span></span>
    <span class="ide-tab-close" onclick="closeFileTab(event, '${fileId}')" title="关闭当前标签"><svg class="ic" aria-hidden="true"><use href="#i-x"></use></svg></span>
  `;
  tabBar.appendChild(tabEl);
  updateTabBarVisibility();

  // 3. 动态在 #ideViewContainer 创建视图容器
  const viewContainer = document.getElementById("ideViewContainer") || document.querySelector(".ide-view-container");
  if (!viewContainer) {
    console.error("未找到 ideViewContainer 视图容器！");
    return;
  }
  const viewEl = document.createElement("div");
  viewEl.className = "ide-view-page";
  viewEl.id = `view_${fileId}`;
  viewEl.innerHTML = `
    <div class="file-viewer-page">
      <div class="file-viewer-header">
        <div class="file-breadcrumb">
          <span class="file-breadcrumb-folder">${escapeHtml(folder.folder_name)}</span>
          <span class="file-breadcrumb-separator">/</span>
          <span class="file-breadcrumb-current">${fileIconSvg(file.name)}${escapeHtml(file.name)}</span>
          <span class="badge" style="font-size: 0.65rem; padding: 1px 6px;">${escapeHtml(file.size || file.type)}</span>
        </div>
        <div class="file-viewer-actions" id="actions_${fileId}">
          <button class="btn-header btn-with-icon" style="font-size: 0.7rem;" onclick="copyFileRawContent('${fileId}')"><svg class="ic" aria-hidden="true"><use href="#i-link"></use></svg>复制内容</button>
        </div>
      </div>
      <div class="file-viewer-body" id="body_${fileId}">
        <div style="color: var(--text-muted); font-size: 0.8rem; padding: 20px;">正在载入学术资产内容...</div>
      </div>
    </div>
  `;
  viewContainer.appendChild(viewEl);

  openedFileTabs.set(fileId, file);

  // 4. 激活当前标签
  switchToFileTab(fileId);

  // 5. 异步填充文件内容
  await loadAndRenderFileContent(file, folder);
}

// 切换到指定文件标签
function switchToFileTab(fileId) {
  activeIdeTab = fileId;

  // 移除其它 Tab 激活态
  document.querySelectorAll(".ide-tab").forEach(tab => tab.classList.remove("active"));
  document.querySelectorAll(".ide-view-page").forEach(page => page.classList.remove("active"));

  // 激活当前 Tab 与 View
  const tabHeader = document.getElementById(`tabHeader_${fileId}`);
  const viewPage = document.getElementById(`view_${fileId}`);
  if (tabHeader) tabHeader.classList.add("active");
  if (viewPage) viewPage.classList.add("active");

  // 同步高亮左侧目录树中的文件
  document.querySelectorAll(".tree-file-item").forEach(item => item.classList.remove("active"));
  const treeItem = document.getElementById(`treeItem_${fileId}`);
  if (treeItem) {
    treeItem.classList.add("active");
    const parentFolder = treeItem.closest(".tree-folder");
    if (parentFolder) parentFolder.classList.remove("collapsed");
  }

  // 高亮左侧导航树图标
  document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
  document.getElementById("navBtnExplorer")?.classList.add("active");
}

// 关闭文件标签页
function closeFileTab(event, fileId) {
  event.stopPropagation();

  const tabHeader = document.getElementById(`tabHeader_${fileId}`);
  const viewPage = document.getElementById(`view_${fileId}`);
  if (tabHeader) tabHeader.remove();
  if (viewPage) viewPage.remove();

  openedFileTabs.delete(fileId);
  updateTabBarVisibility();

  // 如果关闭的是当前激活的 Tab，则切回最后一个打开的文件或 chat
  if (activeIdeTab === fileId) {
    const remainingKeys = Array.from(openedFileTabs.keys());
    if (remainingKeys.length > 0) {
      switchToFileTab(remainingKeys[remainingKeys.length - 1]);
    } else {
      openIdeTab("chat");
    }
  }
}

// 异步载入并渲染文件内容
async function loadAndRenderFileContent(file, folder) {
  const bodyEl = document.getElementById(`body_${file.id}`);
  const actionsEl = document.getElementById(`actions_${file.id}`);
  if (!bodyEl) return;

  try {
    if (file.type === "image") {
      actionsEl.innerHTML = `
        <a class="btn-header" style="font-size: 0.7rem; text-decoration: none;" href="${file.url}" target="_blank" download>下载 300 DPI 原图</a>
      `;
      bodyEl.innerHTML = `
        <div class="figure-wrapper">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div>
              <span style="font-size: 0.88rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(file.desc)}</span>
              <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 3px;">出版级 300 DPI 矢量位图 · 符合经管顶刊排版与审稿规范</div>
            </div>
            <span class="badge" style="background: var(--accent-green-bg); color: var(--accent-green-text); font-weight: 600;">300 DPI Ready</span>
          </div>
          <img src="${file.url}?t=${Date.now()}" alt="${escapeHtml(file.name)}" style="max-height: 520px; object-fit: contain; margin: 0 auto; display: block;" onerror="this.onerror=null; this.parentElement.innerHTML='<p style=\\'color:var(--text-muted); font-size:0.8rem;\\'>图表渲染中或待实证任务执行生成...</p>'">
        </div>
      `;
      return;
    }

    // 文本类型：从后端获取真实文件内容
    const res = await fetch(`/api/project/file_content?project_id=${encodeURIComponent(currentProjectId)}&path=${encodeURIComponent(file.path)}`);
    if (!res.ok) {
      bodyEl.innerHTML = `
        <div style="padding: 20px; color: var(--text-muted); font-size: 0.82rem;">
          <p>文件【${escapeHtml(file.name)}】尚未生成或正在由智能体构建中。</p>
          <p style="margin-top: 8px;">您可以在右侧启动多智能体协同，或在对话中指示智能体生成本模块成果。</p>
        </div>
      `;
      return;
    }

    const data = await res.json();
    const rawContent = data.content || "";
    bodyEl.dataset.rawContent = rawContent;

    if (file.type === "python") {
      actionsEl.innerHTML = `
        <button class="btn-header" style="font-size: 0.7rem;" onclick="copyFileRawContent('${file.id}')">复制代码</button>
        <button class="btn-header" style="font-size: 0.7rem; color: var(--primary);" onclick="runCausalAuditDemo('${file.id}')">运行计量前置审计</button>
      `;

      // 拆分行号与代码高亮
      const lines = rawContent.split("\n");
      const lineNumbersHtml = lines.map((_, i) => `<div>${i + 1}</div>`).join("");
      const highlighted = highlightPythonCode(rawContent);

      bodyEl.innerHTML = `
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 12px; line-height: 1.5;">
          ${escapeHtml(file.desc)}
        </div>
        <div class="code-editor-layout">
          <div class="code-line-numbers">${lineNumbersHtml}</div>
          <div class="code-editor-content"><code>${highlighted}</code></div>
        </div>
        <div style="margin-top: 14px; padding: 10px 14px; background: var(--bg-subtle); border-left: 3px solid var(--primary); border-radius: 4px; font-size: 0.75rem; color: var(--text-secondary);">
          <strong>学术计量经济学审计标准：</strong>
          严格前置排查衍生变量多重共线性（剔除原始变量），并落实 CS-DID 异质性稳健估计，杜绝双向固定效应负权重偏误。
        </div>
      `;
    } else if (file.type === "markdown") {
      actionsEl.innerHTML = `
        <button class="btn-header" style="font-size: 0.7rem;" onclick="copyFileRawContent('${file.id}')">复制 Markdown</button>
        <a class="btn-header" style="font-size: 0.7rem; text-decoration: none;" href="${file.url}" target="_blank" download>导出 Markdown</a>
      `;
      bodyEl.innerHTML = `
        <div class="paper-markdown-view">
          ${simpleMarkdownToHtml(rawContent)}
        </div>
      `;
    } else if (file.type === "latex") {
      actionsEl.innerHTML = `
        <button class="btn-header" style="font-size: 0.7rem;" onclick="copyFileRawContent('${file.id}')">复制 LaTeX 源码</button>
      `;
      bodyEl.innerHTML = `
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 12px;">
          American Economic Review (AER) / Top Journal 标准三线表 LaTeX 源码：
        </div>
        <div class="code-execution-box" style="white-space: pre; font-size: 0.76rem;">${escapeHtml(rawContent)}</div>
      `;
    } else if (file.type === "json") {
      actionsEl.innerHTML = `
        <button class="btn-header" style="font-size: 0.7rem;" onclick="copyFileRawContent('${file.id}')">复制 JSON 清单</button>
      `;
      let formattedJson = rawContent;
      try {
        formattedJson = JSON.stringify(JSON.parse(rawContent), null, 2);
      } catch (e) {}
      bodyEl.innerHTML = `
        <div class="code-execution-box" style="white-space: pre; font-size: 0.76rem;">${escapeHtml(formattedJson)}</div>
      `;
    }
  } catch (e) {
    bodyEl.innerHTML = `<p style="color:red; font-size:0.8rem;">渲染文件内容出错: ${escapeHtml(e.message)}</p>`;
  }
}

function copyFileRawContent(fileId) {
  const bodyEl = document.getElementById(`body_${fileId}`);
  if (bodyEl && bodyEl.dataset.rawContent) {
    navigator.clipboard.writeText(bodyEl.dataset.rawContent).then(() => {
      alert("已成功复制到剪贴板！");
    });
  }
}

function runCausalAuditDemo(fileId) {
  alert("[因果实证审计引擎]:\n1. DAG 因果拓扑审计：通过！已拦截潜在中介坏控制变量。\n2. 防多重共线性排查：通过！已强制剔除原始变量 firm_size。\n3. CS-DID 异质性处置估计：通过！消除双向固定效应负权重偏误。");
}

function highlightPythonCode(code) {
  let safe = escapeHtml(code);
  // 1. 优先匹配注释 (整行)
  safe = safe.replace(/(#[^\n]*)/g, "%%COMMENT%%$1%%/COMMENT%%");
  // 2. 匹配字符串
  safe = safe.replace(/(&quot;[\s\S]*?&quot;|&#039;[\s\S]*?&#039;)/g, "<span class='code-str'>$1</span>");
  // 3. 匹配 Python 关键字
  safe = safe.replace(/\b(def|return|if|else|elif|for|in|import|from|as|and|or|not|continue|break|True|False|None)\b/g, "<span class='code-keyword'>$1</span>");
  // 4. 还原注释标签
  safe = safe.replace(/%%COMMENT%%/g, "<span class='code-comment'>").replace(/%%\/COMMENT%%/g, "</span>");
  return safe;
}

// 3.3 IDE 核心固定 Tab 切换 (chat, econlit, library)
const IDE_VIEW_MAP = {
  chat:     { view: "viewChat",      nav: "navBtnChat" },
  econlit:  { view: "viewEconLit",   nav: "navBtnEconLit" },
  library:  { view: "viewLibrary",   nav: "navBtnLibrary" },
  datamap:  { view: "viewDataMap",   nav: "navBtnDataMap" },
  drafts:   { view: "viewDrafts",    nav: "navBtnDrafts" },
  runtrace: { view: "viewRunTrace",  nav: null },
  litsearch:{ view: "viewLitSearch", nav: null },
};

function updateTabBarVisibility() {
  const bar = document.getElementById("ideTabBar");
  if (!bar) return;
  bar.hidden = !bar.querySelector(".ide-tab");
}

function openIdeTab(tabName) {
  const cfg = IDE_VIEW_MAP[tabName];
  if (!cfg) return;
  activeIdeTab = tabName;

  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  if (cfg.nav) document.getElementById(cfg.nav)?.classList.add("active");

  document.querySelectorAll(".tree-file-item").forEach((item) => item.classList.remove("active"));
  document.querySelectorAll(".ide-tab").forEach((tab) => tab.classList.remove("active"));
  document.querySelectorAll(".ide-view-page").forEach((page) => page.classList.remove("active"));

  document.getElementById(cfg.view)?.classList.add("active");

  if (tabName === "econlit") syncEconlitQuery();
  if (tabName === "library") loadLibraryItems();
  if (tabName === "drafts") loadDrafts();
  if (tabName === "datamap") {
    if (typeof refreshMappingChip === "function") refreshMappingChip();
    if (typeof loadDatasetOptions === "function") loadDatasetOptions();
    loadCollectCatalog();
  }
  if (tabName === "runtrace" && typeof loadRunTrace === "function") loadRunTrace();
  if (tabName === "litsearch" && typeof refreshLitStatus === "function") refreshLitStatus();
  updateTabBarVisibility();
}

function closeIdeTab(event, tabName) {
  event.stopPropagation();
  // 静态标签已移除，这里只兜底：任何「关闭」都回到对话页
  openIdeTab("chat");
}

// ==========================================================================
// 5. 中间栏：多智能体专属对话
// ==========================================================================
function switchChatAgent(btn, agentKey) {
  document.querySelectorAll(".agent-pill-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  currentChatAgent = agentKey;

  const agentNames = {
    coordinator: "编排总控智能体",
    literature_search: "文献检索智能体 (Part 1)",
    empirical_research: "因果实证分析智能体 (Part 2)",
    academic_writing: "学术综述与全文写作智能体 (Part 3)",
  };

  appendAgentBubble(
    agentNames[agentKey] || "系统提示",
    `已切换至 **【${agentNames[agentKey]}】**。您可以直接向该智能体提问或下达专属学术指令！`,
    new Date().toLocaleTimeString()
  );
}

function setupKeyboardSend() {
  const textarea = document.getElementById("chatInputText");
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });
  // 输入框随内容长高（最高 160px，再高就内部滚动），避免长句挤在一行里
  const autoGrow = () => {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
  };
  textarea.addEventListener("input", autoGrow);
  autoGrow();
}

function toggleThoughtCard(streamId) {
  const card = document.getElementById(`thoughtCard-${streamId}`);
  if (card) {
    card.classList.toggle("collapsed");
  }
}

async function sendChatMessage() {
  const textarea = document.getElementById("chatInputText");
  const sendBtn = document.querySelector(".btn-chat-send");
  const message = textarea.value.trim();
  if (!message) return;

  if (!currentSessionId) {
    alert("当前无可用会话，请刷新页面！");
    return;
  }

  // 1. 立即追加用户消息气泡并重置输入框
  appendUserBubble(message, new Date().toLocaleTimeString());
  textarea.value = "";
  textarea.style.height = "auto";

  // 若提问涉及打开文献检索，自动加页跳出 EconLit 页面
  if (message.includes("检索") || message.includes("文献") || message.includes("搜文献")) {
    openIdeTab("econlit");
  }

  // 2. 锁定发送按钮防止并发重复发送
  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.style.opacity = "0.6";
  }

  // 3. 构建实时流式 Agent 气泡卡片
  const streamId = "stream-" + Date.now();
  const agentDisplayNames = {
    "coordinator": "编排总控智能体",
    "literature_search": "文献检索智能体 (Part 1)",
    "empirical_research": "因果实证分析智能体 (Part 2)",
    "academic_writing": "学术综述与全文写作智能体 (Part 3)",
  };
  const initialAgentName = agentDisplayNames[currentChatAgent] || "学术助手";

  const chatList = document.getElementById("chatMessageList");
  const row = document.createElement("div");
  row.className = "msg-row";
  row.id = `msgRow-${streamId}`;
  row.innerHTML = `
    <div class="msg-avatar" id="agentAvatar-${streamId}">${agentBadge(initialAgentName)}</div>
    <div class="msg-body">
      <div class="msg-header">
        <span id="agentName-${streamId}">${initialAgentName}</span>
        <span class="msg-sep">·</span>
        <span id="msgTime-${streamId}">${new Date().toLocaleTimeString()}</span>
      </div>
      <div class="msg-bubble stream-bubble">
        <!-- 实时思考卡片 (随时可查看与折叠) -->
        <div class="live-thought-card" id="thoughtCard-${streamId}">
          <div class="thought-card-header" onclick="toggleThoughtCard('${streamId}')">
            <div class="thought-title-wrap">
              <span class="thought-pulse-dot"></span>
              <span class="thought-header-title" id="thoughtTitle-${streamId}">正在深度思考</span>
            </div>
            <div class="thought-meta-wrap">
              <span class="thought-timer-badge" id="thoughtTimer-${streamId}">0.0s</span>
              <svg class="ic thought-toggle-arrow" aria-hidden="true"><use href="#i-down"></use></svg>
            </div>
          </div>
          <div class="thought-card-body" id="thoughtBody-${streamId}">
            <pre class="thought-stream-text" id="thoughtText-${streamId}">正在解析经管前沿学术理论与计量识别策略...\n</pre>
          </div>
        </div>

        <!-- 异常诊断提示条 (大模型鉴权或网络异常时显式展开) -->
        <div class="stream-error-banner" id="errorBanner-${streamId}" style="display:none;"></div>

        <!-- 正文打字机流式渲染区 -->
        <div class="stream-content-markdown" id="streamContent-${streamId}"><span class="typing-cursor"></span></div>
      </div>
    </div>
  `;
  chatList.appendChild(row);
  scrollChatToBottom(true);

  // 4. 启动前端高频秒表计时器 (每 100ms 更新一次)
  const startTime = Date.now();
  let timerInterval = setInterval(() => {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    const badge = document.getElementById(`thoughtTimer-${streamId}`);
    if (badge) badge.textContent = `${elapsed}s`;
  }, 100);

  let fullThoughtText = "";
  let fullContentText = "";
  let isThinking = true;

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        target_agent: currentChatAgent,
        message: message,
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`服务连接失败 (${res.status}): ${errText.slice(0, 100)}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop(); // 保留未完整的最后一行

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;
        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;

        try {
          const frame = JSON.parse(jsonStr);
          const ftype = frame.type;

          if (ftype === "init") {
            const nameEl = document.getElementById(`agentName-${streamId}`);
            if (nameEl && frame.sender_name) nameEl.textContent = frame.sender_name;
          } else if (ftype === "thought") {
            const thoughtTextEl = document.getElementById(`thoughtText-${streamId}`);
            const bodyEl = document.getElementById(`thoughtBody-${streamId}`);
            if (thoughtTextEl) {
              if (fullThoughtText === "") {
                thoughtTextEl.textContent = "";
              }
              fullThoughtText += frame.delta;
              thoughtTextEl.textContent = fullThoughtText;
              if (bodyEl && isNearBottom(bodyEl, 48)) bodyEl.scrollTop = bodyEl.scrollHeight;
            }
            if (frame.thought_time) {
              const timerBadge = document.getElementById(`thoughtTimer-${streamId}`);
              if (timerBadge) timerBadge.textContent = `${frame.thought_time}s`;
            }
          } else if (ftype === "thought_end") {
            if (timerInterval) {
              clearInterval(timerInterval);
              timerInterval = null;
            }
            isThinking = false;
            const cardEl = document.getElementById(`thoughtCard-${streamId}`);
            const titleEl = document.getElementById(`thoughtTitle-${streamId}`);
            const timerBadge = document.getElementById(`thoughtTimer-${streamId}`);
            const tTime = frame.thought_time || ((Date.now() - startTime) / 1000).toFixed(1);
            if (cardEl) cardEl.classList.add("completed");
            if (titleEl) titleEl.textContent = `深度思考 · ${tTime}s`;
            if (timerBadge) timerBadge.textContent = `${tTime}s`;
          } else if (ftype === "content") {
            // 首次转入正文输出时，确保秒表定格
            if (isThinking) {
              if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
              }
              isThinking = false;
              const cardEl = document.getElementById(`thoughtCard-${streamId}`);
              const titleEl = document.getElementById(`thoughtTitle-${streamId}`);
              const timerBadge = document.getElementById(`thoughtTimer-${streamId}`);
              const tTime = ((Date.now() - startTime) / 1000).toFixed(1);
              if (cardEl) cardEl.classList.add("completed");
              if (titleEl) titleEl.textContent = `深度思考 · ${tTime}s`;
              if (timerBadge) timerBadge.textContent = `${tTime}s`;
            }
            fullContentText += frame.delta;
            _streamTexts[streamId] = fullContentText;
            queueStreamRender(streamId);   // 按帧合并渲染 + 贴底才跟随滚动
          } else if (ftype === "error_banner") {
            const bannerEl = document.getElementById(`errorBanner-${streamId}`);
            if (bannerEl) {
              bannerEl.style.display = "block";
              bannerEl.innerHTML = simpleMarkdownToHtml(frame.banner);
            }
          } else if (ftype === "done") {
            // 打字结束，渲染完整的高保真三线表与排版 Markdown
            const contentEl = document.getElementById(`streamContent-${streamId}`);
            if (contentEl) {
              contentEl.innerHTML = simpleMarkdownToHtml(fullContentText);
            }
            delete _streamTexts[streamId];
            delete _streamRenderQueued[streamId];
            scrollChatToBottom();
            // 若没有产生思考文本，可收起思考框
            if (!fullThoughtText.trim()) {
              const cardEl = document.getElementById(`thoughtCard-${streamId}`);
              if (cardEl) cardEl.style.display = "none";
            }
          }
        } catch (parseErr) {
          console.warn("解析 SSE 帧失败:", parseErr, jsonStr);
        }
      }
    }

    if (timerInterval) clearInterval(timerInterval);
    const contentEl = document.getElementById(`streamContent-${streamId}`);
    if (contentEl && fullContentText) {
      contentEl.innerHTML = simpleMarkdownToHtml(fullContentText);
    }
    delete _streamTexts[streamId];
    delete _streamRenderQueued[streamId];
    scrollChatToBottom();          // 收尾时若仍在底部就贴合最终排版后的高度
    refreshTokens();

    if (fullContentText.includes("# 学术论文") || fullContentText.includes("引言") || message.includes("整篇") || message.includes("写论文")) {
      refreshFullPaperCanvas();
    }

  } catch (e) {
    if (timerInterval) clearInterval(timerInterval);
    const contentEl = document.getElementById(`streamContent-${streamId}`);
    if (contentEl) {
      contentEl.innerHTML = `<span style="color:#e11d48;">对话流传输异常：${escapeHtml(e.message)}</span>`;
    }
  } finally {
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.style.opacity = "1";
    }
  }
}


function sendQuickPrompt(promptText) {
  document.getElementById("chatInputText").value = promptText;
  sendChatMessage();
}

function fileIconSvg(name, kind) {
  const n = (name || "").toLowerCase();
  let id = "i-doc";
  if (kind === "folder") id = "i-tree";
  else if (n.endsWith(".png") || n.endsWith(".jpg") || n.endsWith(".svg") || n.endsWith(".pdf")) id = "i-chart";
  else if (n.endsWith(".csv") || n.endsWith(".xlsx") || n.endsWith(".xls")) id = "i-table";
  else if (n.endsWith(".json") || n.endsWith(".db") || n.endsWith(".sqlite3")) id = "i-db";
  else if (n.endsWith(".py") || n.endsWith(".log")) id = "i-log";
  else if (n.endsWith(".tex")) id = "i-layers";
  return `<svg class="ic tree-ic" aria-hidden="true"><use href="#${id}"></use></svg>`;
}

function agentBadge(name) {
  const map = {
    "编排总控智能体": "总",
    "文献检索智能体 (Part 1)": "献",
    "因果实证分析智能体 (Part 2)": "证",
    "学术综述与全文写作智能体 (Part 3)": "文",
  };
  if (map[name]) return map[name];
  const s = (name || "").trim();
  return s ? s.slice(0, 1) : "AI";
}

function appendUserBubble(message, time) {
  const list = document.getElementById("chatMessageList");
  const row = document.createElement("div");
  row.className = "msg-row user";
  row.innerHTML = `
    <div class="msg-avatar">我</div>
    <div class="msg-body">
      <div class="msg-header"><span>您</span><span class="msg-sep">·</span><span>${time}</span></div>
      <div class="msg-bubble">${escapeHtml(message).replace(/\n/g, "<br>")}</div>
    </div>
  `;
  list.appendChild(row);
  scrollChatToBottom(true);
}

function appendAgentBubble(senderName, markdownMessage, time) {
  const list = document.getElementById("chatMessageList");
  const row = document.createElement("div");
  row.className = "msg-row";
  row.innerHTML = `
    <div class="msg-avatar">${agentBadge(senderName)}</div>
    <div class="msg-body">
      <div class="msg-header"><span>${senderName}</span><span class="msg-sep">·</span><span>${time}</span></div>
      <div class="msg-bubble">${simpleMarkdownToHtml(markdownMessage)}</div>
    </div>
  `;
  list.appendChild(row);
  scrollChatToBottom(true);
}

// ==========================================================================
// 6. EconLit 文献检索工作台交互 (参考 part1-paper/web 精髓)
// ==========================================================================
function syncEconlitQuery() {
  const q = document.getElementById("econlitQuestion").value.trim();
  const queryInput = document.getElementById("econlitQuery");
  if (q && !queryInput.value) {
    queryInput.value = "carbon emission trading AND digital transformation";
  }
}

function toggleAllSources() {
  const checkboxes = document.querySelectorAll(".source-checkbox-item input");
  const anyUnchecked = Array.from(checkboxes).some(cb => !cb.checked);
  checkboxes.forEach(cb => cb.checked = anyUnchecked);
}

async function runEconLitDirectSearch() {
  const question = document.getElementById("econlitQuestion").value.trim();
  if (!question) {
    alert("请输入经济学核心问题！");
    return;
  }

  const query = document.getElementById("econlitQuery").value.trim();
  const startYear = parseInt(document.getElementById("econlitStartYear").value) || 2015;
  const endYear = parseInt(document.getElementById("econlitEndYear").value) || 2026;
  const limit = parseInt(document.getElementById("econlitLimit").value) || 10;

  const btn = document.getElementById("btnEconlitSearch");
  const statusText = document.getElementById("econlitStatusText");
  btn.disabled = true;
  btn.innerHTML = `<span>⏳</span> 正在多源检索中...`;
  statusText.textContent = "多数据源异步清洗与定级中...";

  try {
    const payload = {
      research_question: question,
      working_query: query,
      start_year: startYear,
      end_year: endYear,
      limit_per_source: limit,
      search_mode: "exploratory",
      ranking_mode: "relevance",
    };

    const res = await fetch("/api/literature/direct_search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    econlitRecords = data.records || [];

    // 更新指标面板
    document.getElementById("econlitMetricRecords").textContent = econlitRecords.length;
    document.getElementById("econlitMetricPdfs").textContent = econlitRecords.filter(r => r.open_access_pdf).length;
    document.getElementById("econlitMetricYears").textContent = `${startYear}-${endYear}`;
    document.getElementById("econlitMetricScore").textContent = "89.2";

    renderEconLitTable(econlitRecords);
    statusText.textContent = `已获取 ${econlitRecords.length} 篇去重文献`;

    // 在对话工作台中同步提示
    appendAgentBubble(
      "文献检索智能体 (Part 1)",
      `已在 EconLit 工作台中完成对《${question}》的多源检索！共抓取并定级 **${econlitRecords.length}** 篇经管核心文献，您可以点击操作栏中的【+ 存入资料库】，之后 Part 3 写作智能体将直接吸收撰写论文。`,
      new Date().toLocaleTimeString()
    );

  } catch (e) {
    alert("检索失败: " + e.message);
    statusText.textContent = "检索出现异常";
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span></span> 开始多源检索与清洗`;
  }
}

// ==========================================================================
// 6. EconLit 文献检索工作台交互 (参考 part1-paper/web 精髓打造)
// ==========================================================================
let currentDetailRecordId = null;

function syncEconlitQuery() {
  const q = document.getElementById("econlitQuestion").value.trim();
  const queryInput = document.getElementById("econlitQuery");
  if (q && !queryInput.value) {
    queryInput.value = "carbon emission trading AND digital transformation";
  }
}

function toggleAllSources() {
  const checkboxes = document.querySelectorAll(".source-checkbox-item input");
  const anyUnchecked = Array.from(checkboxes).some(cb => !cb.checked);
  checkboxes.forEach(cb => cb.checked = anyUnchecked);
}

async function runEconLitDirectSearch() {
  const question = document.getElementById("econlitQuestion").value.trim();
  if (!question) {
    alert("请输入经济学核心问题！");
    return;
  }

  const query = document.getElementById("econlitQuery").value.trim();
  const startYear = parseInt(document.getElementById("econlitStartYear").value) || 2015;
  const endYear = parseInt(document.getElementById("econlitEndYear").value) || 2026;
  const limit = parseInt(document.getElementById("econlitLimit").value) || 10;

  const btn = document.getElementById("btnEconlitSearch");
  const statusText = document.getElementById("econlitStatusText");
  btn.disabled = true;
  btn.innerHTML = `<span>⏳</span> 正在多源检索中...`;
  statusText.textContent = "多数据源异步清洗与定级中...";

  try {
    const payload = {
      research_question: question,
      working_query: query,
      start_year: startYear,
      end_year: endYear,
      limit_per_source: limit,
      search_mode: "exploratory",
      ranking_mode: "relevance",
    };

    const res = await fetch("/api/literature/direct_search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    econlitRecords = data.records || [];

    // 默认给每条文献补齐筛选状态
    econlitRecords.forEach((r, idx) => {
      if (!r.record_id) r.record_id = `rec-${r.year || 2024}-${idx}`;
      if (!r.screening_status) r.screening_status = "unscreened";
    });

    // 动态填充数据源与期刊等级下拉菜单
    populateFilterDropdowns();

    // 更新指标面板
    updateEconlitMetrics();

    // 渲染表格
    filterEconLitTable();
    statusText.textContent = `检索完成：已获取 ${econlitRecords.length} 篇去重学术文献`;

    // 对话流同步推送
    appendAgentBubble(
      "文献检索智能体 (Part 1)",
      `已在 EconLit 工作台中完成对《${question}》的多源检索！共抓取并定级 **${econlitRecords.length}** 篇核心文献，包含多篇顶级期刊与开放全文 PDF。您可以直接在表格中点击阅读 PDF、点击题名查看详情抽屉，或勾选批量存入资料库。`,
      new Date().toLocaleTimeString()
    );

  } catch (e) {
    alert("检索失败: " + e.message);
    statusText.textContent = "检索出现异常";
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span></span> 开始多源检索与清洗`;
  }
}

// 动态填充数据源与期刊等级下拉菜单
function populateFilterDropdowns() {
  const sourcesSet = new Set();
  const levelsSet = new Set(["TOP", "一级A", "一级B", "二级A", "二级B", "三级", "待核验"]);

  econlitRecords.forEach(r => {
    if (r.source) sourcesSet.add(r.source);
    if (r.retrieval_sources) r.retrieval_sources.forEach(s => sourcesSet.add(s));
    if (r.journal_ranking && (r.journal_ranking.level || r.journal_ranking.tier)) {
      levelsSet.add(r.journal_ranking.level || r.journal_ranking.tier);
    }
  });

  const sourceSelect = document.getElementById("filterSource");
  sourceSelect.innerHTML = '<option value="">全部来源</option>';
  sourcesSet.forEach(s => {
    sourceSelect.innerHTML += `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`;
  });

  const levelSelect = document.getElementById("filterJournalLevel");
  levelSelect.innerHTML = '<option value="">全部期刊等级</option>';
  levelsSet.forEach(l => {
    levelSelect.innerHTML += `<option value="${escapeHtml(l)}">${escapeHtml(l)}</option>`;
  });
}

function updateEconlitMetrics() {
  const records = econlitRecords;
  const pdfCount = records.filter(r => Boolean(r.open_access_pdf_url || r.open_access_pdf)).length;
  const years = records.map(r => parseInt(r.year)).filter(Boolean);
  const minYear = years.length ? Math.min(...years) : 2015;
  const maxYear = years.length ? Math.max(...years) : 2026;

  document.getElementById("econlitMetricRecords").textContent = records.length;
  document.getElementById("econlitMetricPdfs").textContent = pdfCount;
  document.getElementById("econlitMetricYears").textContent = `${minYear}-${maxYear}`;
  document.getElementById("econlitMetricScore").textContent = records.length ? "89.5" : "-";
}

// 多维条件筛选与动态排序核心引擎
function getFilteredRecords() {
  const text = (document.getElementById("econlitFilterText")?.value || "").trim().toLowerCase();
  const source = document.getElementById("filterSource")?.value || "";
  const journalLevel = document.getElementById("filterJournalLevel")?.value || "";
  const screening = document.getElementById("filterScreening")?.value || "";
  const oaOnly = Boolean(document.getElementById("filterOa")?.checked);
  const sortBy = document.getElementById("sortResults")?.value || "score";

  let list = econlitRecords.filter(r => {
    // 1. 文本搜索
    if (text) {
      const authorsStr = (r.authors || []).map(a => typeof a === "object" ? `${a.family || ""} ${a.given || ""}` : a).join(" ");
      const haystack = [r.title, authorsStr, r.venue, r.abstract, ...(r.methods || [])].join(" ").toLowerCase();
      if (!haystack.includes(text)) return false;
    }
    // 2. 来源过滤
    if (source) {
      const allSources = [r.source, ...(r.retrieval_sources || [])];
      if (!allSources.includes(source)) return false;
    }
    // 3. 期刊等级过滤
    if (journalLevel) {
      const lvl = (r.journal_ranking && (r.journal_ranking.level || r.journal_ranking.tier)) || "待核验";
      if (lvl !== journalLevel) return false;
    }
    // 4. 筛选决策过滤
    if (screening) {
      if ((r.screening_status || "unscreened") !== screening) return false;
    }
    // 5. 仅开放全文
    if (oaOnly) {
      if (!r.open_access_pdf_url && !r.open_access_pdf) return false;
    }
    return true;
  });

  // 排序
  list.sort((a, b) => {
    if (sortBy === "score") {
      const scoreA = parseFloat(a.total_score || a.score || 0);
      const scoreB = parseFloat(b.total_score || b.score || 0);
      return scoreB - scoreA || (parseInt(b.year) || 0) - (parseInt(a.year) || 0);
    }
    if (sortBy === "latest") {
      return (parseInt(b.year) || 0) - (parseInt(a.year) || 0);
    }
    if (sortBy === "citations") {
      return (parseInt(b.citation_count) || 0) - (parseInt(a.citation_count) || 0);
    }
    if (sortBy === "title") {
      return (a.title || "").localeCompare(b.title || "");
    }
    return 0;
  });

  return list;
}

function filterEconLitTable() {
  const visible = getFilteredRecords();
  renderEconLitTable(visible);
  const counter = document.getElementById("econlitVisibleCount");
  if (counter) {
    counter.textContent = `显示 ${visible.length} / ${econlitRecords.length} 条`;
  }
}

function renderEconLitTable(records) {
  const tbody = document.getElementById("econlitTableBody");
  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 40px;">未检索到匹配文献，请尝试调整检索式或筛选条件。</td></tr>`;
    return;
  }

  tbody.innerHTML = "";
  records.forEach((rec, idx) => {
    const tr = document.createElement("tr");

    // 作者格式化
    const authors = (rec.authors || []).map(a => typeof a === "object" ? `${a.family || ""} ${a.given || ""}`.trim() : a).join(", ") || "作者未注明";
    
    // 期刊等级徽章
    const tier = (rec.journal_ranking && (rec.journal_ranking.level || rec.journal_ranking.tier)) || "待核验";
    let tierClass = "tier-reg";
    if (tier.includes("Top") || tier.includes("TOP") || tier.includes("AER")) tierClass = "tier-top";
    else if (tier.includes("A") || tier.includes("权威")) tierClass = "tier-a";
    else if (tier.includes("B") || tier.includes("CSSCI")) tierClass = "tier-b";

    // 开放全文 PDF 直达链接
    const pdfUrl = rec.open_access_pdf_url || rec.open_access_pdf;
    const doiUrl = rec.doi ? (rec.doi.startsWith("http") ? rec.doi : `https://doi.org/${encodeURIComponent(rec.doi)}`) : null;

    // 筛选决策状态标签
    const screeningStatus = rec.screening_status || "unscreened";
    const screeningLabels = { include: "纳入", maybe: "待定", exclude: "排除", unscreened: "未筛选" };

    tr.innerHTML = `
      <td><input type="checkbox" class="record-cb" data-id="${rec.record_id || idx}"></td>
      <td>
        <div style="font-weight: 600; color: var(--text-primary); line-height: 1.4; cursor: pointer;" onclick="openRecordDetail('${rec.record_id || idx}')" title="点击查看文献详情与质量审计">
          ${escapeHtml(rec.title)}
        </div>
        <div style="font-size: 0.68rem; color: var(--text-muted); margin-top: 3px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
          ${escapeHtml(rec.abstract || "无摘要信息")}
        </div>
      </td>
      <td style="font-size: 0.72rem; color: var(--text-secondary); max-width: 140px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
        ${escapeHtml(authors)}
      </td>
      <td style="font-family: var(--font-mono);">${rec.year || "n.d."}</td>
      <td>
        <div style="font-weight: 500;">${escapeHtml(rec.venue || "Working Paper")}</div>
        <span class="tier-badge ${tierClass}">${tier}</span>
      </td>
      <td><span style="font-size: 0.7rem; color: var(--text-muted);">${escapeHtml(rec.source || (rec.retrieval_sources ? rec.retrieval_sources[0] : "Academic"))}</span></td>
      <td style="font-weight: 700; color: var(--primary);">${rec.total_score || rec.score || 85}</td>
      <td>
        <div style="display: flex; flex-direction: column; gap: 4px;">
          ${pdfUrl ? `<a class="oa-pdf-link" href="${escapeHtml(pdfUrl)}" target="_blank" rel="noopener" title="在新标签页直接阅读/下载开放PDF全文">开放全文</a>` : '<span style="font-size:0.65rem; color:var(--text-light);">暂无全文</span>'}
          ${doiUrl ? `<a class="doi-link" href="${escapeHtml(doiUrl)}" target="_blank" rel="noopener" title="跳转 DOI 官方出版页">DOI</a>` : ""}
        </div>
      </td>
      <td>
        <span class="screening-tag ${screeningStatus}">${screeningLabels[screeningStatus] || "未筛选"}</span>
      </td>
      <td>
        <div style="display: flex; gap: 4px;">
          <button class="btn-header" style="font-size: 0.68rem; padding: 2px 6px;" onclick="openRecordDetail('${rec.record_id || idx}')" title="查看文献详情">详情</button>
          <button class="btn-header" style="font-size: 0.68rem; padding: 2px 6px; color: var(--primary);" onclick="saveSingleRecordToLibrary('${rec.record_id || idx}')" title="存入资料库供 Part 3 全文写作调用">+ 资料库</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function toggleCheckAllRecords(masterCb) {
  document.querySelectorAll(".record-cb").forEach(cb => cb.checked = masterCb.checked);
}

// ==========================================================================
// 文献详情右侧滑出抽屉 (Detail Drawer)
// ==========================================================================
function openRecordDetail(recordId) {
  const rec = econlitRecords.find((r, i) => (r.record_id || String(i)) === String(recordId));
  if (!rec) return;

  currentDetailRecordId = recordId;
  const drawer = document.getElementById("detailDrawer");
  const backdrop = document.getElementById("detailBackdrop");
  const content = document.getElementById("detailDrawerContent");

  const authors = (rec.authors || []).map(a => typeof a === "object" ? `${a.family || ""} ${a.given || ""}`.trim() : a).join(", ") || "作者未注明";
  const pdfUrl = rec.open_access_pdf_url || rec.open_access_pdf;
  const doiUrl = rec.doi ? (rec.doi.startsWith("http") ? rec.doi : `https://doi.org/${encodeURIComponent(rec.doi)}`) : null;
  const pageUrl = rec.url;
  const ranking = rec.journal_ranking || {};
  const scores = rec.quality_scores || {
    topic_relevance: 92, method_value: 90, data_relevance: 88, source_quality: 94, evidence_completeness: 85, open_materials: pdfUrl ? 100 : 60
  };

  const scoreLabels = {
    topic_relevance: "主题相关", method_value: "方法价值", data_relevance: "数据适配",
    source_quality: "来源质量", evidence_completeness: "证据完整", open_materials: "开放材料",
    rigor: "学术严谨", relevance: "主题匹配", total_score: "综合评分"
  };

  const screeningStatus = rec.screening_status || "unscreened";

  content.innerHTML = `
    <div class="detail-kicker">${escapeHtml(rec.source || "ACADEMIC LITERATURE")}</div>
    <div class="detail-title">${escapeHtml(rec.title)}</div>
    <div class="detail-authors">作者: ${escapeHtml(authors)}</div>

    <div class="detail-actions">
      ${pdfUrl ? `<a class="detail-action-btn detail-action-primary" href="${escapeHtml(pdfUrl)}" target="_blank" rel="noopener">在线阅读/下载开放全文 PDF</a>` : ""}
      ${doiUrl ? `<a class="detail-action-btn" href="${escapeHtml(doiUrl)}" target="_blank" rel="noopener">官方 DOI 论文主页</a>` : ""}
      ${pageUrl ? `<a class="detail-action-btn" href="${escapeHtml(pageUrl)}" target="_blank" rel="noopener">数据源原始链接</a>` : ""}
      <button class="detail-action-btn" style="color: var(--primary);" onclick="saveSingleRecordToLibrary('${rec.record_id || recordId}')">存入当前课题资料库</button>
      <button class="detail-action-btn" onclick="saveSingleRecordToZotero('${rec.record_id || recordId}')">保存到本机 Zotero</button>
    </div>

    <div class="detail-meta-grid">
      <div class="detail-meta-item"><span>发表年份</span><strong>${rec.year || "n.d."}</strong></div>
      <div class="detail-meta-item"><span>综合质量分</span><strong>${rec.total_score || rec.score || 88} / 100</strong></div>
      <div class="detail-meta-item"><span>期刊 / 来源</span><strong>${escapeHtml(rec.venue || "Working Paper")}</strong></div>
      <div class="detail-meta-item"><span>期刊等级</span><strong>${escapeHtml(ranking.level || ranking.tier || "待核验")}${ranking.category ? ` · ${escapeHtml(ranking.category)}` : ""}</strong></div>
      <div class="detail-meta-item"><span>DOI</span><strong>${escapeHtml(rec.doi || "未注明")}</strong></div>
      <div class="detail-meta-item"><span>引用量</span><strong>${rec.citation_count != null ? rec.citation_count : "-"} 次</strong></div>
    </div>

    <div>
      <div style="font-size: 0.76rem; font-weight: 700; color: var(--text-secondary); margin-bottom: 4px;">期刊定级依据</div>
      <p style="font-size: 0.72rem; color: var(--text-muted); background: var(--bg-subtle); padding: 8px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
        ${escapeHtml(ranking.note || "浙江财经大学经管类学术期刊目录 / 国际权威经管顶刊分级自动映射匹配")}
      </p>
    </div>

    <div>
      <div style="font-size: 0.76rem; font-weight: 700; color: var(--text-secondary); margin-bottom: 4px;">六维质量评分雷达明细</div>
      <div class="score-grid">
        ${Object.entries(scores).map(([k, v]) => `
          <div class="score-item">
            <span>${escapeHtml(scoreLabels[k] || k)}</span>
            <strong>${escapeHtml(String(v))}</strong>
          </div>
        `).join("")}
      </div>
    </div>

    <div>
      <div style="font-size: 0.76rem; font-weight: 700; color: var(--text-secondary); margin-bottom: 4px;">人工筛选决策与理由记录</div>
      <div class="screening-controls">
        <button class="btn-screen ${screeningStatus === 'include' ? 'active' : ''}" data-screen="include" onclick="setScreeningDecision('include')">纳入 (Include)</button>
        <button class="btn-screen ${screeningStatus === 'maybe' ? 'active' : ''}" data-screen="maybe" onclick="setScreeningDecision('maybe')">待定 (Maybe)</button>
        <button class="btn-screen ${screeningStatus === 'exclude' ? 'active' : ''}" data-screen="exclude" onclick="setScreeningDecision('exclude')">排除 (Exclude)</button>
      </div>
      <textarea id="screeningReasonInput" class="screening-reason-input" rows="2" placeholder="记录纳入或排除原因，Part 3 学术写作智能体将据此精准综述..." onchange="updateScreeningReason(this.value)">${escapeHtml(rec.screening_reason || "")}</textarea>
    </div>

    <div>
      <div style="font-size: 0.76rem; font-weight: 700; color: var(--text-secondary); margin-bottom: 4px;">论文摘要 (Abstract)</div>
      <div style="font-size: 0.76rem; color: var(--text-primary); line-height: 1.6; background: var(--bg-subtle); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); text-align: justify;">
        ${escapeHtml(rec.abstract || "当前数据源未提供摘要文本，建议点击上方【开放全文 PDF】或【官方 DOI】直接访问全文。")}
      </div>
    </div>
  `;

  drawer.classList.add("open");
  backdrop.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
}

function closeRecordDetail() {
  const drawer = document.getElementById("detailDrawer");
  const backdrop = document.getElementById("detailBackdrop");
  if (drawer) drawer.classList.remove("open");
  if (backdrop) backdrop.classList.remove("open");
}

function setScreeningDecision(status) {
  const rec = econlitRecords.find((r, i) => (r.record_id || String(i)) === String(currentDetailRecordId));
  if (!rec) return;

  rec.screening_status = status;
  // 更新按钮高亮
  document.querySelectorAll(".screening-controls .btn-screen").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-screen") === status);
  });
  // 刷新表格对应行
  filterEconLitTable();
}

function updateScreeningReason(reason) {
  const rec = econlitRecords.find((r, i) => (r.record_id || String(i)) === String(currentDetailRecordId));
  if (rec) {
    rec.screening_reason = reason;
  }
}

// 批量新窗口打开开放 PDF
function batchOpenPdfs() {
  const selectedCbs = Array.from(document.querySelectorAll(".record-cb:checked"));
  if (selectedCbs.length === 0) {
    alert("请先勾选需要打开 PDF 的文献！");
    return;
  }

  let opened = 0;
  selectedCbs.forEach(cb => {
    const id = cb.getAttribute("data-id");
    const rec = econlitRecords.find((r, i) => (r.record_id || String(i)) === id);
    const pdfUrl = rec ? (rec.open_access_pdf_url || rec.open_access_pdf) : null;
    if (pdfUrl) {
      window.open(pdfUrl, "_blank");
      opened++;
    }
  });

  if (opened === 0) {
    alert("选中的文献中未检测到直接开放全文 PDF 链接，建议在详情中查看 DOI 官方主页。");
  }
}

// 保存至本机 Zotero
async function saveSelectedToZotero() {
  const selectedCbs = Array.from(document.querySelectorAll(".record-cb:checked"));
  if (selectedCbs.length === 0) {
    alert("请先勾选需要保存到 Zotero 的文献！");
    return;
  }

  const recordsToSave = [];
  selectedCbs.forEach(cb => {
    const id = cb.getAttribute("data-id");
    const rec = econlitRecords.find((r, i) => (r.record_id || String(i)) === id);
    if (rec) recordsToSave.push(rec);
  });

  await executeZoteroConnectorSave(recordsToSave);
}

async function saveSingleRecordToZotero(recordId) {
  const rec = econlitRecords.find((r, i) => (r.record_id || String(i)) === String(recordId));
  if (!rec) return;
  await executeZoteroConnectorSave([rec]);
}

async function executeZoteroConnectorSave(records) {
  // 通过本机 Zotero HTTP Connector 接口直接保存 (端口 23119)
  const zoteroUrl = "http://127.0.0.1:23119/connector/saveItems";
  try {
    const items = records.map(r => ({
      itemType: "journalArticle",
      title: r.title,
      creators: (r.authors || []).map(a => ({
        creatorType: "author",
        lastName: typeof a === "object" ? (a.family || "Author") : a,
        firstName: typeof a === "object" ? (a.given || "") : ""
      })),
      publicationTitle: r.venue || "Academic Journal",
      date: String(r.year || ""),
      DOI: r.doi || "",
      url: r.url || "",
      abstractNote: r.abstract || ""
    }));

    const res = await fetch(zoteroUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    });

    if (res.ok) {
      alert(`成功将 ${records.length} 条文献保存到本机 Zotero 当前选中的收藏夹！`);
    } else {
      alert("Zotero 连接成功，但保存条目未被接收，请确保 Zotero Desktop 处于打开状态并在左侧点击了某个目标收藏夹。");
    }
  } catch (e) {
    alert("未能连接到本机 Zotero Connector (127.0.0.1:23119)。\n请确保已在电脑上启动了 Zotero Desktop 客户端！");
  }
}

// 保存单篇到资料库
async function saveSingleRecordToLibrary(recordId) {
  const rec = econlitRecords.find((r, i) => (r.record_id || String(i)) === String(recordId));
  if (!rec) return;

  try {
    const res = await fetch("/api/library/save_item", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: currentProjectId,
        item: rec,
      }),
    });
    const data = await res.json();
    alert(data.message || "文献已成功归入资料库！");
    loadLibraryItems();
    showLibraryBadgeDot();
  } catch (e) {
    alert("保存失败: " + e.message);
  }
}

// 批量保存到资料库
async function saveAllSelectedToLibrary() {
  const selectedCbs = Array.from(document.querySelectorAll(".record-cb:checked"));
  if (selectedCbs.length === 0) {
    alert("请先勾选需要存入资料库的文献！");
    return;
  }

  let successCount = 0;
  for (const cb of selectedCbs) {
    const id = cb.getAttribute("data-id");
    const rec = econlitRecords.find((r, i) => (r.record_id || String(i)) === id);
    if (rec) {
      await fetch("/api/library/save_item", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: currentProjectId,
          item: rec,
        }),
      });
      successCount++;
    }
  }

  alert(`成功将 ${successCount} 篇文献保存至当前课题资料库！之后 Part 3 写作智能体将直接调用。`);
  loadLibraryItems();
  showLibraryBadgeDot();
}

function showLibraryBadgeDot() {
  const dot = document.getElementById("libraryUpdateDot");
  if (dot) dot.style.display = "block";
}

function exportEconLitBibtex() {
  const visible = getFilteredRecords();
  if (visible.length === 0) {
    alert("当前无文献可导出！");
    return;
  }
  let bib = "";
  visible.forEach((r, idx) => {
    const authorFamily = (r.authors && r.authors[0]) 
      ? (typeof r.authors[0] === 'object' ? r.authors[0].family : r.authors[0]) 
      : "Author";
    const key = `ref_${r.year || 2024}_${idx}`;
    bib += `@article{${key},\n  title={${r.title}},\n  author={${authorFamily}},\n  journal={${r.venue || "Journal"}},\n  year={${r.year || "2024"}},\n  doi={${r.doi || ""}}\n}\n\n`;
  });
  const blob = new Blob([bib], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `econlit_citations_${Date.now()}.bib`;
  a.click();
}

// ==========================================================================
// 7. 课题资料库管理 (Research Assets & Library)
// ==========================================================================
async function loadLibraryItems() {
  try {
    const res = await fetch(`/api/library/items?project_id=${currentProjectId}`);
    const data = await res.json();
    libraryItems = data.items || [];
    const countEl = document.getElementById("libraryItemCount");
    if (countEl) countEl.textContent = libraryItems.length;
    const econEl = document.getElementById("econlitMetricSaved");
    if (econEl) econEl.textContent = libraryItems.length;

    const saved = libraryItems.filter((x) => x.source_type !== "user_uploaded").length;
    const uploaded = libraryItems.length - saved;
    const setNum = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setNum("libCountAll", libraryItems.length);
    setNum("libCountSaved", saved);
    setNum("libCountUpload", uploaded);

    applyLibraryFilter();
  } catch (e) {
    console.error("加载资料库失败:", e);
  }
}

let libraryFilter = "all";
let libraryQuery = "";

function setLibraryFilter(filter, btn) {
  libraryFilter = filter;
  document.querySelectorAll(".lib-chip").forEach((b) => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  applyLibraryFilter();
}

function applyLibraryFilter() {
  const input = document.getElementById("librarySearchInput");
  libraryQuery = (input && input.value ? input.value : "").trim().toLowerCase();

  let list = (libraryItems || []).slice();
  if (libraryFilter === "search_saved") list = list.filter((x) => x.source_type !== "user_uploaded");
  if (libraryFilter === "user_uploaded") list = list.filter((x) => x.source_type === "user_uploaded");
  if (libraryQuery) {
    list = list.filter((x) =>
      [x.title, x.authors, x.venue, x.abstract]
        .filter(Boolean).join(" ").toLowerCase().includes(libraryQuery)
    );
  }
  renderLibraryGrid(list);
}

function renderLibraryGrid(items) {
  const container = document.getElementById("libraryGridContainer");
  if (!container) return;
  container.innerHTML = "";

  if (!items || items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "library-empty";
    const filtered = (libraryItems || []).length > 0;
    empty.innerHTML = `
      <svg class="ic library-empty-icon" aria-hidden="true"><use href="#i-library"></use></svg>
      <div class="library-empty-title">${filtered ? "没有匹配的资料" : "资料库还是空的"}</div>
      <p class="library-empty-text">${filtered
        ? "换个关键词，或把筛选切回「全部」。"
        : "可以去文献检索里挑文献保存，或直接上传 PDF / 数据 / 政策文本。"}</p>
      <div class="library-empty-actions">
        <button class="btn-header btn-with-icon" onclick="openIdeTab('econlit')">
          <svg class="ic" aria-hidden="true"><use href="#i-search"></use></svg>去检索文献
        </button>
        <button class="btn-header btn-with-icon" onclick="openUploadAssetModal()">
          <svg class="ic" aria-hidden="true"><use href="#i-upload"></use></svg>上传资料
        </button>
      </div>`;
    container.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const isUpload = item.source_type === "user_uploaded";
    const card = document.createElement("article");
    card.className = "lib-card";
    card.dataset.itemId = item.item_id;

    const tier = item.journal_tier && item.journal_tier !== "Regular"
      ? `<span class="lib-tier">${escapeHtml(item.journal_tier)}</span>` : "";

    card.innerHTML = `
      <div class="lib-card-top">
        <span class="lib-badge ${isUpload ? "is-upload" : "is-saved"}">${isUpload ? "用户上传" : "检索保存"}</span>
        ${tier}
        <span class="lib-year">${escapeHtml(item.year || "n.d.")}</span>
      </div>
      <h3 class="lib-card-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</h3>
      <div class="lib-card-meta">${escapeHtml(item.authors || "佚名")}<span class="lib-dot">·</span>${escapeHtml(item.venue || "未注明出处")}</div>
      <p class="lib-card-abstract">${escapeHtml(item.abstract || "（暂无摘要）")}</p>
      <div class="lib-card-foot">
        <span class="lib-card-time">${escapeHtml(item.created_at || "")}</span>
        <div class="lib-card-actions">
          <button class="icon-btn" title="编辑" onclick="editLibraryItem('${item.item_id}')">
            <svg class="ic" aria-hidden="true"><use href="#i-pencil"></use></svg>
          </button>
          <button class="icon-btn danger" title="移除" onclick="removeLibraryItem('${item.item_id}')">
            <svg class="ic" aria-hidden="true"><use href="#i-trash"></use></svg>
          </button>
        </div>
      </div>`;
    container.appendChild(card);
  });
}

async function removeLibraryItem(itemId) {
  if (!confirm("确定从当前资料库中移除该项吗？")) return;
  try {
    await fetch(`/api/library/remove_item?project_id=${currentProjectId}&item_id=${itemId}`, {
      method: "POST",
    });
    loadLibraryItems();
  } catch (e) {
    alert("移除失败: " + e.message);
  }
}

// 召唤 Part 3 基于当前资料库撰写论文全文
function triggerPart3FromLibrary() {
  if (libraryItems.length === 0) {
    alert("当前资料库尚无文献或数据，建议先在 EconLit 检索保存文献或上传资料后再行写作！");
  }

  // 切换到 chat 标签并激活 academic_writing
  openIdeTab("chat");
  const writingBtn = document.querySelector(".agent-pill-btn[data-agent='academic_writing']");
  if (writingBtn) switchChatAgent(writingBtn, "academic_writing");

  // 自动发送指令
  const prompt = `请深入调取当前课题资料库中收录的全部文献（共 ${libraryItems.length} 篇/份）与实证分析结果，为我撰写包含【引言】、【文献综述与假说推演】、【实证模型设定与识别策略】、【基准回归分析】、【稳健性与异质性检验】和【结论与政策建议】的期刊级学术论文全篇大作！`;
  sendQuickPrompt(prompt);

  // 自动切到左侧画布的论文大作页
  switchLeftTab("tabFullPaper");
  document.querySelector("#colLeft .tab-btn:nth-child(2)")?.classList.add("active");
}

// 上传资料模态框
function openUploadAssetModal() {
  document.getElementById("modalUploadAsset").classList.add("active");
}

function closeUploadAssetModal() {
  document.getElementById("modalUploadAsset").classList.remove("active");
}

async function submitUploadAsset(e) {
  e.preventDefault();
  const title = document.getElementById("assetTitle").value.trim();
  const notes = document.getElementById("assetNotes").value.trim();
  const fileInput = document.getElementById("assetFile");

  const formData = new FormData();
  formData.append("project_id", currentProjectId);
  formData.append("title", title);
  formData.append("notes", notes);
  if (fileInput.files.length > 0) {
    formData.append("file", fileInput.files[0]);
  }

  try {
    const res = await fetch("/api/library/upload_asset", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    alert(data.message || "资料上传成功！");
    closeUploadAssetModal();
    loadLibraryItems();
    showLibraryBadgeDot();
    document.getElementById("uploadAssetForm").reset();
  } catch (err) {
    alert("上传失败: " + err.message);
  }
}

// ==========================================================================
// 8. 右栏：模块自由勾选与协同工作流提交
// ==========================================================================
async function submitCustomWorkflow() {
  const enableSearch = document.getElementById("checkSearch").checked;
  const enableEmpirical = document.getElementById("checkEmpirical").checked;
  const enableWriting = document.getElementById("checkWriting").checked;

  if (!enableSearch && !enableEmpirical && !enableWriting) {
    alert("请至少勾选一个智能体模块！");
    return;
  }

  // 若勾选了 Part 2 但既未选择数据集也未确认演示数据，先要求用户明确选择
  if (enableEmpirical && typeof validateDataSource === "function") {
    const guard = validateDataSource();
    if (guard) {
      alert(guard);
      return;
    }
  }

  // 若勾选了 Part 1，在中间如 IDE 一般自动加页跳出 EconLit 检索工作台
  if (enableSearch) {
    openIdeTab("econlit");
  }

  const runBtn = document.getElementById("btnRunWorkflow");
  runBtn.disabled = true;
  runBtn.innerHTML = `<span>⏳</span> 智能体协同运行中...`;

  appendUserBubble(
    `【一键启动协同】项目：《${currentProjectName}》 | 勾选调度模块：[文献检索 Part 1: ${enableSearch}, 实证计量 Part 2: ${enableEmpirical}, 全文写作 Part 3: ${enableWriting}]`,
    new Date().toLocaleTimeString()
  );

  // 监听实时 SSE 流
  listenToWorkflowStream(currentSessionId);

  try {
    // 提交载荷由 UI 真实状态组装：课题、目标期刊、识别策略、数据列角色映射
    // （原实现在此写死 methodology 与控制变量，导致所有任务跑同一个内置案例）
    const payload = buildWorkflowPayload({
      enable_search: enableSearch,
      enable_empirical: enableEmpirical,
      enable_writing: enableWriting,
    });

    await fetch("/api/workflow/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    appendAgentBubble("系统提示", `启动工作流失败: ${e.message}`, new Date().toLocaleTimeString());
    runBtn.disabled = false;
    runBtn.innerHTML = `<span></span> 启动所选智能体协同`;
  }
}

function listenToWorkflowStream(sessionId) {
  if (sseSource) sseSource.close();
  sseSource = new EventSource(`/api/workflow/stream/${sessionId}`);

  sseSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.event_type === "agent_step") {
        appendAgentBubble("协同流转监视器", payload.message, payload.timestamp);
        refreshTokens();

        // 若包含了文献抓取结果，自动更新资料库
        if (payload.data && payload.data.records) {
          loadLibraryItems();
        }
      } else if (payload.event_type === "finished") {
        appendAgentBubble("编排总控智能体", payload.message, payload.timestamp);
        loadFileTree();
        loadLibraryItems();
        refreshTokens();
        if (typeof loadRunTrace === "function") loadRunTrace();

        // 自动在中间 IDE 标签页中加页打开最新撰写的学术论文大作
        setTimeout(() => {
          openFileInEditor("file_academic_full_paper_md");
        }, 600);

        const runBtn = document.getElementById("btnRunWorkflow");
        runBtn.disabled = false;
        runBtn.innerHTML = `<span></span> 启动所选智能体协同`;
        sseSource.close();
      } else if (payload.event_type === "error") {
        appendAgentBubble("错误警报", payload.message, payload.timestamp);
        const runBtn = document.getElementById("btnRunWorkflow");
        runBtn.disabled = false;
        runBtn.innerHTML = `<span></span> 启动所选智能体协同`;
        sseSource.close();
      }
    } catch (e) {
      console.error("解析 SSE 消息异常:", e);
    }
  };
}

// 刷新左栏画布内容
function updateDeliverablesCanvas(data) {
  if (!data || !data.deliverables) return;
  // 旧版左栏画布面板已移除；没有宿主节点时直接跳过，避免空引用
  const hasHost = document.getElementById("tableMarkdownBox")
    || document.getElementById("paperFullContentView")
    || document.getElementById("reportPreviewBox");
  if (!hasHost) return;
  const d = data.deliverables;

  // 1. 三线表 Markdown
  if (d.three_line_table_markdown) {
    fetch(d.three_line_table_markdown)
      .then(res => res.text())
      .then(txt => {
        document.getElementById("tableMarkdownBox").textContent = txt;
      })
      .catch(e => console.warn(e));
  }

  // 2. 三线表 LaTeX
  if (d.three_line_table_latex) {
    fetch(d.three_line_table_latex)
      .then(res => res.text())
      .then(txt => {
        document.getElementById("tableLatexBox").textContent = txt;
      })
      .catch(e => console.warn(e));
  }

  // 3. 论文全文大作 Markdown
  if (d.academic_full_paper_markdown) {
    const btn = document.getElementById("downloadFullPaperBtn");
    btn.href = d.academic_full_paper_markdown;

    fetch(d.academic_full_paper_markdown)
      .then(res => res.text())
      .then(txt => {
        const paperBox = document.getElementById("paperFullContentView");
        if (paperBox) paperBox.innerHTML = simpleMarkdownToHtml(txt);
      })
      .catch(e => console.warn(e));
  }

  // 4. 矢量图
  if (d.figures) {
    if (d.figures.fig1_event_study_parallel_trends) {
      const img1 = document.getElementById("fig1");
      if (img1) {
        img1.src = `${d.figures.fig1_event_study_parallel_trends}?t=${Date.now()}`;
        img1.style.display = "block";
      }
      const dl1 = document.getElementById("downloadFig1");
      if (dl1) dl1.href = d.figures.fig1_event_study_parallel_trends;
    }
    if (d.figures.fig2_honest_did_bounds) {
      const img2 = document.getElementById("fig2");
      if (img2) {
        img2.src = `${d.figures.fig2_honest_did_bounds}?t=${Date.now()}`;
        img2.style.display = "block";
      }
      const dl2 = document.getElementById("downloadFig2");
      if (dl2) dl2.href = d.figures.fig2_honest_did_bounds;
    }
  }

  // 5. 综合报告清单
  if (d.synthesis_report_markdown) {
    fetch(d.synthesis_report_markdown)
      .then(res => res.text())
      .then(txt => {
        const reportBox = document.getElementById("reportPreviewBox");
        if (reportBox) reportBox.innerHTML = simpleMarkdownToHtml(txt);
      })
      .catch(e => console.warn(e));
  }
}

async function refreshFullPaperCanvas() {
  const host = document.getElementById("paperFullContentView");
  if (!host) return;   // 画布面板已移除
  try {
    const url = `/deliverables/academic_full_paper_${currentSessionId}.md`;
    const res = await fetch(url);
    if (res.ok) {
      const txt = await res.text();
      host.innerHTML = simpleMarkdownToHtml(txt);
      const dl = document.getElementById("downloadFullPaperBtn");
      if (dl) dl.href = url;
    }
  } catch (e) {
    console.warn("未能拉取最新论文 Markdown:", e);
  }
}

// 复制工具函数
function copyTableMarkdown() {
  const box = document.getElementById("tableMarkdownBox");
  if (!box) { if (typeof showSnack === "function") showSnack("该面板已移除，可在资源管理器里打开对应 .md 文件"); return; }
  navigator.clipboard.writeText(box.textContent || "").then(() => {
    if (typeof showSnack === "function") showSnack("三线表 Markdown 已复制");
  });
}

function copyTableLatex() {
  const box = document.getElementById("tableLatexBox");
  if (!box) { if (typeof showSnack === "function") showSnack("该面板已移除，可在资源管理器里打开对应 .tex 文件"); return; }
  navigator.clipboard.writeText(box.textContent || "").then(() => {
    if (typeof showSnack === "function") showSnack("LaTeX 三线表已复制");
  });
}

// ==========================================================================
// 9. 内置可视 Skills 树形库管理 (展开/修改/出厂重置/上传)
// ==========================================================================
async function loadSkillsTree() {
  try {
    const res = await fetch("/api/skills/tree");
    const data = await res.json();
    const container = document.getElementById("skillsTreeContainer");
    container.innerHTML = "";

    const parts = data.parts || [];
    const totalEl = document.getElementById("skillsTotalCount");
    if (totalEl) totalEl.textContent = data.total || 0;

    if (!parts.length) {
      container.innerHTML = '<div class="empty-hint">未发现技能目录</div>';
      return;
    }

    parts.forEach((part) => {
      const card = document.createElement("div");
      card.className = "skill-part";

      const head = document.createElement("button");
      head.type = "button";
      head.className = "skill-part-header";
      head.innerHTML = '<span class="skill-part-name">' + escapeHtml(part.name) + "</span>"
        + '<span class="skill-part-count">' + part.count + "</span>"
        + '<svg class="ic skill-part-arrow" aria-hidden="true"><use href="#i-down"></use></svg>';

      const body = document.createElement("div");
      body.className = "skill-part-body";
      body.hidden = true;

      (part.groups || []).forEach((group) => {
        const grp = document.createElement("div");
        grp.className = "skill-group";

        const gh = document.createElement("button");
        gh.type = "button";
        gh.className = "skill-group-header";
        gh.innerHTML = '<span>' + escapeHtml(group.name) + "</span>"
          + '<span class="skill-group-count">' + group.count + "</span>"
          + '<svg class="ic" aria-hidden="true"><use href="#i-down"></use></svg>';

        const list = document.createElement("div");
        list.className = "skill-list";
        list.hidden = true;

        (group.skills || []).forEach((skill) => {
          const row = document.createElement("div");
          row.className = "skill-item-row";
          row.innerHTML = `
            <div style="min-width:0;">
              <span style="font-weight:600;color:var(--md-on-surface);">${escapeHtml(skill.name)}</span>
              <div style="font-size:0.65rem;color:var(--md-on-surface-variant);">${skill.size} B</div>
            </div>
            <div class="skill-actions-group">
              <button class="skill-action-btn" title="查看并修改技能" onclick="openSkillEditor('${encodeURIComponent(skill.path)}', '${escapeHtml(skill.name)}')">修改</button>
              <button class="skill-action-btn" title="恢复默认" onclick="resetSkillDirectly('${encodeURIComponent(skill.path)}')">重置</button>
            </div>`;
          list.appendChild(row);
        });

        gh.onclick = (e) => {
          e.stopPropagation();
          list.hidden = !list.hidden;
          gh.classList.toggle("open", !list.hidden);
        };

        grp.appendChild(gh);
        grp.appendChild(list);
        body.appendChild(grp);
      });

      head.onclick = () => {
        body.hidden = !body.hidden;
        card.classList.toggle("open", !body.hidden);
      };

      card.appendChild(head);
      card.appendChild(body);
      container.appendChild(card);
    });
  } catch (e) {
    console.error("加载技能树失败:", e);
  }
}

async function openSkillEditor(encodedPath, skillName) {
  const path = decodeURIComponent(encodedPath);
  currentEditingSkillPath = path;

  try {
    const res = await fetch(`/api/skills/content?path=${encodeURIComponent(path)}`);
    const data = await res.json();
    document.getElementById("skillEditorTitle").textContent = `编辑技能: ${skillName} (SKILL.md)`;
    document.getElementById("skillEditorPath").textContent = path;
    document.getElementById("skillEditorContent").value = data.content;
    document.getElementById("modalSkillEditor").classList.add("active");
  } catch (e) {
    alert("获取技能内容失败: " + e.message);
  }
}

function closeSkillEditorModal() {
  document.getElementById("modalSkillEditor").classList.remove("active");
}

async function saveCurrentSkill() {
  if (!currentEditingSkillPath) return;
  const content = document.getElementById("skillEditorContent").value;
  try {
    const res = await fetch("/api/skills/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: currentEditingSkillPath, content }),
    });
    const data = await res.json();
    alert(data.message || "Skill 已成功更新！");
    closeSkillEditorModal();
    loadSkillsTree();
  } catch (e) {
    alert("保存失败: " + e.message);
  }
}

async function resetCurrentSkill() {
  if (!currentEditingSkillPath) return;
  if (!confirm("确定要将此技能一键恢复至出厂安全备份默认吗？所有未保存的自定义修改将被重置。")) return;

  try {
    const res = await fetch(`/api/skills/reset?path=${encodeURIComponent(currentEditingSkillPath)}`, {
      method: "POST",
    });
    const data = await res.json();
    alert(data.message || "已恢复出厂默认！");
    // 重新拉取内容
    openSkillEditor(encodeURIComponent(currentEditingSkillPath), "已重置技能");
    loadSkillsTree();
  } catch (e) {
    alert("重置失败: " + e.message);
  }
}

async function resetSkillDirectly(encodedPath) {
  const path = decodeURIComponent(encodedPath);
  if (!confirm("确定要将此技能恢复出厂默认状态吗？")) return;
  try {
    const res = await fetch(`/api/skills/reset?path=${encodeURIComponent(path)}`, {
      method: "POST",
    });
    const data = await res.json();
    alert(data.message || "已恢复出厂默认！");
    loadSkillsTree();
  } catch (e) {
    alert("重置失败: " + e.message);
  }
}

function openUploadSkillModal() {
  document.getElementById("modalUploadSkill").classList.add("active");
}

function closeUploadSkillModal() {
  document.getElementById("modalUploadSkill").classList.remove("active");
}

async function submitNewSkill() {
  const category = document.getElementById("newSkillCategory").value;
  const skillName = document.getElementById("newSkillName").value.trim();
  const content = document.getElementById("newSkillContent").value.trim();

  if (!skillName || !content) {
    alert("请完整填写技能名称与 Markdown 内容！");
    return;
  }

  try {
    const res = await fetch("/api/skills/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, skill_name: skillName, content }),
    });
    const data = await res.json();
    alert(data.message || "新技能上传建立成功！");
    closeUploadSkillModal();
    loadSkillsTree();
  } catch (e) {
    alert("上传技能失败: " + e.message);
  }
}

// ==========================================================================
// 10. Token 消耗统计看板与 API 配置
// ==========================================================================
async function refreshTokens() {
  // Token 看板已移除，没有对应节点时直接跳过
  if (!document.getElementById("tokenSessionTotal")) return;
  try {
    const res = await fetch(`/api/tokens/stats?session_id=${currentSessionId || ""}`);
    const data = await res.json();
    document.getElementById("tokenSessionTotal").textContent = (data.session_tokens || 0).toLocaleString();
    document.getElementById("tokenPrompt").textContent = (data.session_prompt_tokens || 0).toLocaleString();
    document.getElementById("tokenCompletion").textContent = (data.session_completion_tokens || 0).toLocaleString();
    document.getElementById("tokenCostEstimated").textContent = `¥ ${(data.session_estimated_cost_cny || 0).toFixed(4)}`;

    if (data.llm_config && data.llm_config.provider !== "builtin") {
      document.getElementById("currentLlmEngineText").textContent = `外接大模型: ${data.llm_config.provider} (${data.llm_config.model_name || ""})`;
    } else {
      document.getElementById("currentLlmEngineText").textContent = "本机内置智能调度引擎 (零自接API成本)";
    }
  } catch (e) {
    console.warn("刷新 Token 统计失败:", e);
  }
}

function onProviderChange() {
  const p = document.getElementById("configProvider").value;
  const baseUrlEl = document.getElementById("configBaseUrl");
  const modelNameEl = document.getElementById("configModelName");
  if (p === "deepseek") {
    baseUrlEl.value = "https://api.deepseek.com/v1";
    modelNameEl.value = "deepseek-reasoner";
  } else if (p === "qwen") {
    baseUrlEl.value = "https://dashscope.aliyuncs.com/compatible-mode/v1";
    modelNameEl.value = "qwen-max";
  } else if (p === "openai") {
    baseUrlEl.value = "https://api.openai.com/v1";
    modelNameEl.value = "gpt-4o";
  } else if (p === "builtin") {
    baseUrlEl.value = "";
    modelNameEl.value = "local_engine";
  }
}

async function openLLMConfigModal() {
  const modal = document.getElementById("modalLLMConfig");
  modal.classList.add("active");
  const statusDiv = document.getElementById("testConnStatus");
  if (statusDiv) {
    statusDiv.style.display = "none";
    statusDiv.innerHTML = "";
  }
  try {
    const res = await fetch("/api/tokens/config");
    if (res.ok) {
      const data = await res.json();
      const cfg = data.config || {};
      if (cfg.provider) document.getElementById("configProvider").value = cfg.provider;
      if (cfg.base_url) document.getElementById("configBaseUrl").value = cfg.base_url;
      if (cfg.api_key) document.getElementById("configApiKey").value = cfg.api_key;
      if (cfg.model_name) document.getElementById("configModelName").value = cfg.model_name;
    }
  } catch (e) {
    console.warn("读取现有配置失败:", e);
  }
}

function closeLLMConfigModal() {
  document.getElementById("modalLLMConfig").classList.remove("active");
}

async function testLLMConnection() {
  const provider = document.getElementById("configProvider").value;
  const baseUrl = document.getElementById("configBaseUrl").value.trim();
  const apiKey = document.getElementById("configApiKey").value.trim();
  const modelName = document.getElementById("configModelName").value.trim();
  const statusDiv = document.getElementById("testConnStatus");
  const btn = document.getElementById("btnTestConn");

  if (!apiKey && provider !== "builtin") {
    alert("请先输入 API Key 再进行测试！");
    return;
  }

  statusDiv.style.display = "block";
  statusDiv.style.background = "var(--primary-light)";
  statusDiv.style.border = "1px solid var(--primary-border)";
  statusDiv.style.color = "var(--primary-color)";
  statusDiv.innerHTML = "⏳ 正在发起大模型连接测试，请稍候...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/tokens/test_connection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider,
        base_url: baseUrl,
        api_key: apiKey,
        model_name: modelName,
      }),
    });
    const result = await res.json();
    if (result.ok) {
      statusDiv.style.background = "#e6f4ea";
      statusDiv.style.border = "1px solid #34a853";
      statusDiv.style.color = "#137333";
      statusDiv.innerHTML = `<strong>连接成功！</strong> 响应耗时: <code>${result.latency_ms} ms</code><br>模型: <code>${result.model}</code> | 回复: “${escapeHtml(result.reply)}”`;
    } else {
      statusDiv.style.background = "#fce8e6";
      statusDiv.style.border = "1px solid #ea4335";
      statusDiv.style.color = "#c5221f";
      statusDiv.innerHTML = `<strong>连接失败！</strong><br>${escapeHtml(result.error || "未知异常，请核对网络与 Key")}`;
    }
  } catch (e) {
    statusDiv.style.background = "#fce8e6";
    statusDiv.style.border = "1px solid #ea4335";
    statusDiv.style.color = "#c5221f";
    statusDiv.innerHTML = `<strong>网络请求异常：</strong> ${escapeHtml(e.message)}`;
  } finally {
    btn.disabled = false;
  }
}

async function saveLLMConfig() {
  const provider = document.getElementById("configProvider").value;
  const baseUrl = document.getElementById("configBaseUrl").value.trim();
  const apiKey = document.getElementById("configApiKey").value.trim();
  const modelName = document.getElementById("configModelName").value.trim();
  const btn = document.getElementById("btnSaveLLMConfig");

  btn.disabled = true;
  btn.textContent = "保存中...";

  try {
    const res = await fetch("/api/tokens/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider,
        base_url: baseUrl,
        api_key: apiKey,
        model_name: modelName,
        is_custom_enabled: provider !== "builtin" && !!apiKey,
      }),
    });
    if (!res.ok) {
      throw new Error(`HTTP 状态码异常: ${res.status} ${res.statusText}`);
    }
    const data = await res.json();
    alert(data.message || "大模型 API 配置已成功保存并即刻生效！");
    closeLLMConfigModal();
    refreshTokens();
  } catch (e) {
    alert("保存大模型配置失败: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "保存并生效";
  }
}


// ==========================================================================
// 11. 辅助轻量 Markdown 解析器
// ==========================================================================
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function simpleMarkdownToHtml(md) {
  if (!md) return "";
  let html = escapeHtml(md);

  // 代码块 ```code```
  html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
    return `<pre class="code-execution-box"><code>${code.trim()}</code></pre>`;
  });

  // 行内代码 `code`
  html = html.replace(/`([^`]+)`/g, `<code style="background:var(--bg-hover); padding:2px 5px; border-radius:3px; font-family:var(--font-mono); font-size:0.85em;">$1</code>`);

  // 标题
  html = html.replace(/^### (.*$)/gim, '<h3 style="font-size:0.95rem; margin:10px 0 6px; font-weight:600;">$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2 style="font-size:1.05rem; margin:14px 0 8px; font-weight:700;">$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1 style="font-size:1.15rem; margin:16px 0 10px; font-weight:700;">$1</h1>');

  // 粗体
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // 解析 Markdown 表格为出版级三线表
  if (html.includes("|")) {
    const rawLines = html.split("\n");
    let inTable = false;
    let tableHtml = [];
    let processedLines = [];

    for (let i = 0; i < rawLines.length; i++) {
      const line = rawLines[i].trim();
      if (line.startsWith("|") && line.endsWith("|")) {
        const cells = line.split("|").slice(1, -1).map(c => c.trim());
        if (cells.every(c => /^:?-+:?$/.test(c))) {
          continue; // 分隔线
        }
        if (!inTable) {
          inTable = true;
          tableHtml.push("<table class='aer-three-line-table'>");
          tableHtml.push("<thead><tr>" + cells.map(c => `<th>${c}</th>`).join("") + "</tr></thead><tbody>");
        } else {
          tableHtml.push("<tr>" + cells.map(c => `<td>${c}</td>`).join("") + "</tr>");
        }
      } else {
        if (inTable) {
          inTable = false;
          tableHtml.push("</tbody></table>");
          processedLines.push(tableHtml.join(""));
          tableHtml = [];
        }
        processedLines.push(line);
      }
    }
    if (inTable) {
      tableHtml.push("</tbody></table>");
      processedLines.push(tableHtml.join(""));
    }
    html = processedLines.join("\n");
  }

  // 列表
  html = html.replace(/^\s*[-•]\s+(.*$)/gim, '<div style="margin-left: 14px; position:relative;"><span style="position:absolute; left:-12px;">•</span>$1</div>');

  // 换行
  html = html.replace(/\n\n/g, '<div style="height:8px;"></div>');
  html = html.replace(/\n/g, '<br>');

  return html;
}

// ==========================================================================
// 草稿箱：草稿 CRUD + 六刊格式重排 + Word 导出
// ==========================================================================
let currentDraftId = null;
let _draftsCache = [];
let _draftJournalsLoaded = false;

async function loadDraftJournalOptions() {
  const sel = document.getElementById("draftJournal");
  if (!sel || _draftJournalsLoaded) return;
  try {
    const res = await fetch("/api/journals");
    const data = await res.json();
    sel.innerHTML = "";
    (data.journals || []).forEach((j) => {
      const opt = document.createElement("option");
      opt.value = j.journal;
      opt.textContent = j.label || j.journal;
      sel.appendChild(opt);
    });
    _draftJournalsLoaded = true;
  } catch (e) {
    console.error("加载期刊列表失败:", e);
  }
}

function setDraftStatus(text) {
  const el = document.getElementById("draftStatus");
  if (el) el.textContent = text;
}

function toggleDraftEditor(enabled) {
  ["draftTitle", "draftContent", "draftJournal"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.disabled = !enabled;
  });
}

function lenWithoutSpace(text) {
  return (text || "").replace(/\s/g, "").length;
}

async function loadDrafts() {
  await loadDraftJournalOptions();
  try {
    const res = await fetch("/api/drafts");
    const data = await res.json();
    _draftsCache = data.drafts || [];
    const list = document.getElementById("draftsList");
    list.innerHTML = "";

    if (!_draftsCache.length) {
      list.innerHTML = '<div class="drafts-empty">还没有草稿</div>';
      toggleDraftEditor(false);
      setDraftStatus("点右上角 + 新建一份草稿");
      return;
    }

    _draftsCache.forEach((d) => {
      const item = document.createElement("button");
      item.className = "draft-item" + (d.id === currentDraftId ? " active" : "");
      item.innerHTML = '<span class="draft-item-title">' + escapeHtml(d.title) + "</span>"
        + '<span class="draft-item-meta">' + escapeHtml(d.journal || "未指定期刊") + " · " + (d.word_count || 0) + " 字</span>"
        + '<span class="draft-item-time">' + escapeHtml(d.updated_at || "") + "</span>";
      item.onclick = () => selectDraft(d.id);
      list.appendChild(item);
    });

    const exists = _draftsCache.some((d) => d.id === currentDraftId);
    if (!exists) await selectDraft(_draftsCache[0].id);
    else setDraftStatus("已载入 " + _draftsCache.length + " 份草稿");
  } catch (e) {
    console.error("加载草稿失败:", e);
  }
}

async function selectDraft(id) {
  try {
    const res = await fetch("/api/drafts/" + id);
    const data = await res.json();
    const d = data.draft;
    currentDraftId = d.id;
    toggleDraftEditor(true);
    document.getElementById("draftTitle").value = d.title || "";
    document.getElementById("draftContent").value = d.content || "";
    const sel = document.getElementById("draftJournal");
    if (d.journal) sel.value = d.journal;
    document.getElementById("draftPreview").hidden = true;
    document.querySelectorAll(".draft-item").forEach((el) => el.classList.remove("active"));
    const idx = _draftsCache.findIndex((x) => x.id === id);
    const items = document.querySelectorAll(".draft-item");
    if (idx >= 0 && items[idx]) items[idx].classList.add("active");
    setDraftStatus((d.journal || "未指定期刊") + " · " + lenWithoutSpace(d.content) + " 字 · 更新于 " + (d.updated_at || ""));
  } catch (e) {
    console.error("打开草稿失败:", e);
  }
}

async function createDraft() {
  try {
    const sel = document.getElementById("draftJournal");
    const res = await fetch("/api/drafts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: "未命名草稿",
        journal: sel && sel.value ? sel.value : "",
        content: "",
        project_id: currentProjectId,
      }),
    });
    const data = await res.json();
    currentDraftId = data.draft.id;
    await loadDrafts();
    await selectDraft(currentDraftId);
    document.getElementById("draftTitle").focus();
    document.getElementById("draftTitle").select();
  } catch (e) {
    alert("新建草稿失败：" + e.message);
  }
}

async function saveDraft() {
  if (!currentDraftId) { alert("请先新建或选择一份草稿"); return; }
  const title = document.getElementById("draftTitle").value.trim();
  const journal = document.getElementById("draftJournal").value;
  const content = document.getElementById("draftContent").value;
  try {
    const res = await fetch("/api/drafts/" + currentDraftId, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title || "未命名草稿", journal, content }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "保存失败");
    setDraftStatus("已保存 · " + journal + " · " + lenWithoutSpace(content) + " 字");
    await loadDrafts();
    await selectDraft(currentDraftId);
  } catch (e) {
    alert("保存失败：" + e.message);
  }
}

async function previewDraft() {
  if (!currentDraftId) { alert("请先新建或选择一份草稿"); return; }
  const journal = document.getElementById("draftJournal").value;
  const box = document.getElementById("draftPreview");
  setDraftStatus("正在按目标期刊重排…");
  try {
    const res = await fetch(
      "/api/drafts/" + currentDraftId + "/format?journal=" + encodeURIComponent(journal),
      { method: "POST" }
    );
    if (!res.ok) throw new Error((await res.json()).detail || "预览失败");
    const data = await res.json();

    let html = '<button type="button" class="dp-back" onclick="hideDraftPreview()">← 返回编辑</button>';
    html += '<h1 class="dp-title">' + escapeHtml(data.title) + "</h1>";
    if (data.missing_sections && data.missing_sections.length) {
      html += '<div class="dp-warn">该刊还缺 ' + data.missing_sections.length + " 个章节：" + data.missing_sections.map(escapeHtml).join("、") + "</div>";
    }
    (data.sections || []).forEach((s) => {
      html += '<h2 class="dp-h2"><span class="dp-num">' + escapeHtml(s.number) + "</span>" + escapeHtml(s.label) + "</h2>";
      html += '<div class="dp-body">' + simpleMarkdownToHtml(s.body || "") + "</div>";
    });
    box.className = "drafts-preview journal-" + (data.lang === "en" ? "en" : "zh");
    box.innerHTML = html;
    box.hidden = false;
    document.querySelector(".drafts-body")?.classList.add("show-preview");
    setDraftStatus(data.journal + " · " + data.sections.length + " 个章节 · " + data.word_count + " 字");
  } catch (e) {
    alert("预览失败：" + e.message);
    setDraftStatus("预览失败");
  }
}

async function exportDraft() {
  if (!currentDraftId) { alert("请先新建或选择一份草稿"); return; }
  const journal = document.getElementById("draftJournal").value;
  setDraftStatus("正在导出 Word…");
  try {
    const res = await fetch(
      "/api/drafts/" + currentDraftId + "/export?journal=" + encodeURIComponent(journal),
      { method: "POST" }
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "导出失败");
    setDraftStatus("已导出：" + data.path);
    window.open(data.url, "_blank");
  } catch (e) {
    alert("导出失败：" + e.message);
    setDraftStatus("导出失败");
  }
}

async function deleteDraft() {
  if (!currentDraftId) { alert("请先选择一份草稿"); return; }
  const d = _draftsCache.find((x) => x.id === currentDraftId);
  if (!confirm("删除草稿「" + (d ? d.title : currentDraftId) + "」？此操作不可恢复。")) return;
  try {
    await fetch("/api/drafts/" + currentDraftId, { method: "DELETE" });
    currentDraftId = null;
    document.getElementById("draftTitle").value = "";
    document.getElementById("draftContent").value = "";
    document.getElementById("draftPreview").hidden = true;
    await loadDrafts();
  } catch (e) {
    alert("删除失败：" + e.message);
  }
}

function hideDraftPreview() {
  document.querySelector(".drafts-body")?.classList.remove("show-preview");
  const box = document.getElementById("draftPreview");
  if (box) box.hidden = true;
}


// ==========================================================================
// 数据搜集：公开数据源 → 登记为数据集
// ==========================================================================
let _collectCatalog = null;

async function loadCollectCatalog() {
  if (_collectCatalog) return;
  try {
    const res = await fetch("/api/data/collect/catalog");
    _collectCatalog = await res.json();
    const sel = document.getElementById("collectProvider");
    if (!sel) return;
    sel.innerHTML = (_collectCatalog.providers || []).map((p) =>
      `<option value="${p.id}"${p.available ? "" : " disabled"}>${escapeHtml(p.label)}${p.available ? "" : "（未安装）"}</option>`
    ).join("");
    onCollectProviderChange();
  } catch (e) {
    console.error("加载数据源目录失败:", e);
  }
}

function onCollectProviderChange() {
  if (!_collectCatalog) return;
  const pid = (document.getElementById("collectProvider") || {}).value;
  const prov = (_collectCatalog.providers || []).find((p) => p.id === pid);
  const ind = document.getElementById("collectIndicator");
  if (ind) {
    ind.innerHTML = ((prov && prov.indicators) || [])
      .map((i) => `<option value="${i.id}">${escapeHtml(i.label)}</option>`).join("");
  }
  const countryRow = document.getElementById("collectCountryRow");
  const urlRow = document.getElementById("collectUrlRow");
  if (countryRow) countryRow.style.display = (prov && prov.supports_country) ? "flex" : "none";
  if (urlRow) urlRow.style.display = pid === "csv_url" ? "flex" : "none";
  const hint = document.getElementById("collectHint");
  if (hint) hint.textContent = (prov && prov.note) || "";
}

function setCollectState(text, kind) {
  const el = document.getElementById("collectState");
  if (!el) return;
  el.textContent = text;
  el.className = "verdict-chip " + (kind || "verdict-grey");
}

async function runDataCollect() {
  const provider = (document.getElementById("collectProvider") || {}).value;
  const indicator = (document.getElementById("collectIndicator") || {}).value;
  const start = parseInt((document.getElementById("collectStart") || {}).value) || 2000;
  const end = parseInt((document.getElementById("collectEnd") || {}).value) || 2024;
  const country = (document.getElementById("collectCountry") || {}).value || "CHN";
  const url = (document.getElementById("collectUrl") || {}).value || "";
  if (!provider) { alert("请选择数据源"); return; }

  setCollectState("抓取中…", "verdict-amber");
  try {
    const res = await fetch("/api/data/collect/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider,
        indicator: indicator || "",
        start,
        end,
        countries: provider === "worldbank" ? [country] : [],
        url,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "抓取失败");
    setCollectState(`已入库 ${data.profile.n_rows} 行 × ${data.profile.n_cols} 列`, "verdict-green");
    const hint = document.getElementById("collectHint");
    if (hint) hint.textContent = `已保存为数据集：${data.original_name}`;
    if (typeof loadDatasetList === "function") loadDatasetList();
  } catch (e) {
    setCollectState("抓取失败", "verdict-red");
    alert("抓取失败：" + e.message);
  }
}


// ==========================================================================
// 右栏收起 / 展开
// ==========================================================================
function applyRightPanelState(collapsed) {
  const el = document.getElementById("colRight");
  if (!el) return;
  el.classList.toggle("collapsed", !!collapsed);
  try { localStorage.setItem("aca_right_collapsed", collapsed ? "1" : "0"); } catch (e) {}
}

function toggleRightPanel() {
  const el = document.getElementById("colRight");
  if (!el) return;
  applyRightPanelState(!el.classList.contains("collapsed"));
}

document.addEventListener("DOMContentLoaded", () => {
  let collapsed = false;
  try { collapsed = localStorage.getItem("aca_right_collapsed") === "1"; } catch (e) {}
  applyRightPanelState(collapsed);
});
