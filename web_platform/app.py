# -*- coding: utf-8 -*-
"""
学术全流程多智能体协同 Web 平台后端服务 (FastAPI)
版本 3.0:
1. 左侧全局项目库 (Projects Hub) 与资料库 (Research Assets Hub)
2. 支持 IDE 多标签页 (Tabbed Workspace)，调用 Part 1 自动弹出 EconLit 检索工作台
3. 资料库支持用户手动上传与检索保存，并与 Part 3 全文写作智能体深度打通
4. 维持多用户 Session 隔离、ReMe 记忆服务同步与 Token 实时统计
"""

import asyncio
import functools
import json
import logging
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 确保导入 orchestrator
CURRENT_DIR = Path(__file__).resolve().parent
INTEGRATED_ROOT = CURRENT_DIR.parent
for _p in (str(INTEGRATED_ROOT), str(CURRENT_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from orchestrator.workflow import AcademicWorkflowCoordinator
from orchestrator.skills_manager import skills_manager
from orchestrator.token_tracker import token_tracker
from core.paths import abs_path, to_rel, migrate_legacy_paths

import literature_bridge  # Part 1 文献检索能力桥接（原 :8765 独立前端）

# 日志初始化
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AcademicWebPlatform")

app = FastAPI(
    title="学术全流程因果实证分析与全文写作智能体工作台",
    description="支持多项目管理、资料库联动、IDE多标签页工作台与Token监控",
    version="3.0.0",
)


import drafts as drafts_api  # 草稿箱：草稿 CRUD + 期刊格式重排 + Word 导出

app.include_router(drafts_api.router)


@app.on_event("startup")
async def _bootstrap_portable_paths():
    """整目录搬到新机器/云主机后，把库里残留的旧绝对路径改挂到当前项目根。"""
    try:
        stats = migrate_legacy_paths()
        if stats["files"] or stats["sqlite"]:
            logger.info(
                "路径迁移完成：文本文件 %s 个 / 数据库字段 %s 处（跳过超大文件 %s）",
                stats["files"], stats["sqlite"], stats["skipped"],
            )
    except Exception as exc:  # 迁移失败不影响主流程
        logger.warning("路径迁移跳过：%s", exc)

# CORS：只放行本机入口（8088 主工作台 / 8765 旧前端 / 前端调试端口）。
# 不再 allow_origins=["*"]——那等于把本地服务与本地数据对任意网页敞开。
# 需要额外来源时用环境变量 ACA_ALLOWED_ORIGINS 以逗号分隔追加。
ALLOWED_ORIGINS = [
    "http://127.0.0.1:8088",
    "http://localhost:8088",
    "http://127.0.0.1:8765",
    "http://localhost:8765",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
_extra = os.getenv("ACA_ALLOWED_ORIGINS", "")
if _extra:
    ALLOWED_ORIGINS += [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 公网部署保护（可选）
# 不设置下面两个环境变量时中间件完全不启用，本地行为与之前一致。
# 云端部署时设置 ACA_BASIC_USER / ACA_BASIC_PASS，浏览器弹原生登录框，
# 登录成功后同源请求（含 SSE）自动带凭据，前端零改动。
# ---------------------------------------------------------------------------
_BASIC_USER = os.getenv("ACA_BASIC_USER", "").strip()
_BASIC_PASS = os.getenv("ACA_BASIC_PASS", "").strip()


def _load_accounts() -> Dict[str, str]:
    """单账号用 ACA_BASIC_USER/PASS；多人共享时用 ACA_BASIC_USERS="u1:p1,u2:p2"。"""
    accts: Dict[str, str] = {}
    if _BASIC_USER and _BASIC_PASS:
        accts[_BASIC_USER] = _BASIC_PASS
    for item in os.getenv("ACA_BASIC_USERS", "").split(","):
        if ":" in item:
            u, p = item.split(":", 1)
            if u.strip() and p.strip():
                accts[u.strip()] = p.strip()
    return accts


_ACCOUNTS = _load_accounts()

if _ACCOUNTS:
    import base64
    import secrets as _secrets

    from starlette.middleware.base import BaseHTTPMiddleware

    class _BasicAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # 预检请求浏览器不带凭据，必须放行，否则跨域调用被拦在 OPTIONS
            if request.method == "OPTIONS":
                return await call_next(request)
            auth = request.headers.get("authorization", "")
            ok = False
            if auth.lower().startswith("basic "):
                try:
                    raw = base64.b64decode(auth[6:]).decode("utf-8", "ignore")
                    user, pwd = raw.split(":", 1)
                    ok = any(
                        _secrets.compare_digest(user, u) and _secrets.compare_digest(pwd, p)
                        for u, p in _ACCOUNTS.items()
                    )
                except Exception:
                    ok = False
            if not ok:
                return JSONResponse(
                    {"detail": "Unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="ACA Workbench"'},
                )
            return await call_next(request)

    app.add_middleware(_BasicAuthMiddleware)
    logger.info("已启用 Basic Auth 访问控制（%d 个账号）", len(_ACCOUNTS))

# 目录映射
STATIC_DIR = CURRENT_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
DELIVERABLES_DIR = INTEGRATED_ROOT / "part2-empirical-research" / "deliverables"
DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_ASSETS_DIR = INTEGRATED_ROOT / "part2-empirical-research" / "data" / "library_uploads"
UPLOAD_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DATASETS_DIR = INTEGRATED_ROOT / "part2-empirical-research" / "data" / "uploads"
UPLOAD_DATASETS_DIR.mkdir(parents=True, exist_ok=True)
DATASET_INDEX_FILE = UPLOAD_DATASETS_DIR / "_index.json"

# ---- 项目级交付目录：每个项目一个独立文件夹，资源管理器按项目隔离 ----
CURRENT_PROJECT_ID = "proj-default-001"


def _project_deliverables(project_id: str = "") -> Path:
    pid = (project_id or CURRENT_PROJECT_ID or "proj-default-001").strip()
    d = DELIVERABLES_DIR / "projects" / pid
    d.mkdir(parents=True, exist_ok=True)
    return d


def _activate_project(project_id: str) -> Path:
    """切换项目时把各处输出目录指向该项目文件夹。"""
    global CURRENT_PROJECT_ID
    pid = (project_id or "proj-default-001").strip()
    CURRENT_PROJECT_ID = pid
    d = _project_deliverables(pid)
    try:
        coordinator.output_dir = d
    except Exception:
        pass
    try:
        ea = getattr(coordinator, "empirical_agent", None)
        if ea is not None:
            ea.output_dir = str(d)
    except Exception:
        pass
    return d

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/deliverables", StaticFiles(directory=str(DELIVERABLES_DIR)), name="deliverables")

# 全局协调器与数据存储
coordinator = AcademicWorkflowCoordinator(output_dir=str(DELIVERABLES_DIR))
active_sessions: Dict[str, Dict[str, Any]] = {}
session_event_queues: Dict[str, asyncio.Queue] = {}

# 全局项目库与资料库存储
projects_store: Dict[str, Dict[str, Any]] = {}

# 持久化仓库：会话与项目库落 SQLite，服务重启不丢
from core.store import store  # noqa: E402
from core.skill_loader import skill_loader  # noqa: E402

_PROJECTS_KV_KEY = "projects_store"
_LAST_PERSIST: Dict[str, float] = {}


def _persist_session(session_id: str) -> None:
    """把单个会话上下文写入状态库"""
    st = active_sessions.get(session_id)
    if st is None:
        return
    try:
        store.save_session(session_id, st, project_id=st.get("project_id", ""))
    except Exception as exc:  # noqa: BLE001  持久化失败不能影响主流程
        logger.warning("会话持久化失败 %s: %s", session_id, exc)


def _persist_projects() -> None:
    """把项目库写入状态库"""
    try:
        store.set_kv(_PROJECTS_KV_KEY, projects_store)
    except Exception as exc:  # noqa: BLE001
        logger.warning("项目库持久化失败: %s", exc)


def _migrate_legacy_deliverables() -> None:
    """老版本把交付物直接放在 deliverables/ 根下，这里一次性收进默认项目目录。"""
    try:
        target = _project_deliverables("proj-default-001")
        for entry in list(DELIVERABLES_DIR.iterdir()):
            if entry.name in ("projects", "drafts"):
                continue
            dest = target / entry.name
            if dest.exists():
                continue
            shutil.move(str(entry), str(dest))
    except Exception as exc:  # noqa: BLE001
        logger.warning("交付物目录迁移跳过: %s", exc)


def _restore_state() -> None:
    """启动时从状态库恢复会话与项目库"""
    try:
        restored_projects = store.get_kv(_PROJECTS_KV_KEY, None)
        if isinstance(restored_projects, dict) and restored_projects:
            projects_store.update(restored_projects)
        for meta in store.list_sessions(limit=200):
            sid = meta["session_id"]
            state = store.load_session(sid)
            if isinstance(state, dict):
                state.setdefault("logs", [])
                state.setdefault("chat_history", [])
                active_sessions[sid] = state
        logger.info("已从状态库恢复：%d 个项目 / %d 个会话",
                    len(projects_store), len(active_sessions))
    except Exception as exc:  # noqa: BLE001
        logger.warning("状态恢复失败，将以空状态启动: %s", exc)


def _to_web_url(filepath: Optional[str]) -> Optional[str]:
    """把交付物绝对路径转换为前端可访问的 /deliverables/... 路径"""
    if not filepath:
        return None
    p = Path(filepath)
    if "deliverables" in p.parts:
        idx = p.parts.index("deliverables")
        return "/" + "/".join(p.parts[idx:])
    return f"/deliverables/{p.name}"


async def _push_event(session_id: str, event_type: str, message: str, progress: int = 0, data: Optional[Dict[str, Any]] = None):
    """向指定会话的事件队列推送事件并记录日志"""
    event = {
        "event_type": event_type,
        "message": message,
        "progress": progress,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "data": data or {},
    }
    if session_id in active_sessions:
        active_sessions[session_id]["progress"] = progress
        if "logs" not in active_sessions[session_id]:
            active_sessions[session_id]["logs"] = []
        active_sessions[session_id]["logs"].append(event)
        # 落库（1 秒节流，避免高频事件反复写盘）
        now = time.time()
        if now - _LAST_PERSIST.get(session_id, 0) >= 1.0:
            _LAST_PERSIST[session_id] = now
            _persist_session(session_id)

    if session_id in session_event_queues:
        await session_event_queues[session_id].put(event)


def _init_default_project():
    """初始化默认研究项目与初始资料库"""
    default_pid = "proj-default-001"
    default_sid = f"session-{datetime.now().strftime('%Y%m%d%H%M%S')}-default"
    
    initial_library = [
        {
            "item_id": "lib-callaway-2021",
            "title": "Difference-in-Differences with multiple time periods",
            "authors": "Callaway, B. & Sant'Anna, P. H. C.",
            "year": "2021",
            "venue": "Journal of Econometrics",
            "journal_tier": "Top International",
            "source_type": "benchmark_saved",
            "abstract": "现代交错实施 DID 核心奠基之作，解决了异质性处置效应与双向固定效应负权重问题。",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        {
            "item_id": "lib-rambachan-2023",
            "title": "A More Credible Approach to Parallel Trends",
            "authors": "Rambachan, A. & Roth, J.",
            "year": "2023",
            "venue": "Review of Economic Studies",
            "journal_tier": "Top 5 International",
            "source_type": "benchmark_saved",
            "abstract": "HonestDiD 敏感性分析边界检验，经管顶刊审稿人关注的平行趋势检验最新黄金标准。",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    ]

    projects_store[default_pid] = {
        "project_id": default_pid,
        "name": "国家碳交易试点政策的因果效应研究",
        "topic": "国家碳排放权交易试点(ETS)对企业数字化转型的政策效应——兼论管理层短视的调节作用",
        "active_session_id": default_sid,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "library_items": initial_library,
    }

    active_sessions[default_sid] = {
        "session_id": default_sid,
        "project_id": default_pid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "idle",
        "progress": 0,
        "logs": [],
        "chat_history": [
            {
                "sender": "coordinator",
                "sender_name": "编排总控智能体",
                "message": "您好！我是学术全流程总控智能体。您可以随时在此与我交流研究构思、在上方单独切换并与子智能体（文献检索、实证计量、全文写作）对话，或在右侧自由勾选所需智能体一键启动协同。",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
        ],
        "context_data": {
            "literature": initial_library,
            "empirical": {},
            "hypotheses": [],
            "full_paper_text": None,
        },
        "result": None,
    }
    session_event_queues[default_sid] = asyncio.Queue()
    _persist_projects()
    _persist_session(default_sid)


# 先恢复历史状态；若库中没有任何项目（首次启动），再灌入默认示例项目
_restore_state()
_migrate_legacy_deliverables()          # 老版本根目录交付物 → 默认项目目录
_activate_project(CURRENT_PROJECT_ID)   # 输出目录指向当前项目
if not projects_store:
    _init_default_project()
else:
    for sid in list(active_sessions.keys()):
        session_event_queues.setdefault(sid, asyncio.Queue())


class ResearchTaskRequest(BaseModel):
    research_topic: str
    methodology: str = "auto"
    control_variables: List[str] = []
    derived_mappings: Optional[Dict[str, str]] = None
    session_id: Optional[str] = None
    project_id: Optional[str] = "proj-default-001"
    enable_search: bool = True
    enable_empirical: bool = True
    enable_writing: bool = True

    # 数据与列角色映射：实证分析的必需输入
    data_path: Optional[str] = None
    id_col: Optional[str] = None
    time_col: Optional[str] = None
    outcome_col: Optional[str] = None
    treatment_col: Optional[str] = None
    g_col: Optional[str] = None
    cluster_col: Optional[str] = None
    # IV 专用列角色
    endogenous_col: Optional[str] = None
    instrument_cols: List[str] = []
    mediators: List[str] = []
    moderators: List[str] = []
    demo_mode: bool = False
    target_journal: str = "经济研究"
    max_strategy_attempts: int = 3

    def to_task_spec(self) -> "TaskSpec":
        from core.contracts import DataSpec, TaskSpec

        data = DataSpec(
            file_path=self.data_path,
            id_col=self.id_col,
            time_col=self.time_col,
            outcome_col=self.outcome_col,
            treatment_col=self.treatment_col,
            g_col=self.g_col,
            cluster_col=self.cluster_col,
            endogenous_col=self.endogenous_col,
            instrument_cols=self.instrument_cols,
            controls=self.control_variables,
            mediators=self.mediators,
            moderators=self.moderators,
        )
        return TaskSpec(
            research_question=self.research_topic,
            data=data,
            strategy=self.methodology or "auto",
            demo_mode=self.demo_mode,
            target_journal=self.target_journal,
            max_strategy_attempts=self.max_strategy_attempts,
            output_directory=str(DELIVERABLES_DIR),
        )


class ChatMessageRequest(BaseModel):
    session_id: str
    target_agent: str = "coordinator"
    message: str


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>学术全流程多智能体平台正在准备前端资源，请稍候刷新...</h2>")


@app.get("/api/health")
async def health_check():
    memory_status = coordinator.memory_client.status()
    return {
        "status": "healthy",
        "service": "Academic-MultiAgent-Interactive-Platform",
        "version": "3.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reme_memory_online": memory_status["online"],
        "reme_memory_error": memory_status.get("last_error"),
        "llm_configured": bool(token_tracker.llm_config.get("api_key")),
        "skills_indexed": skill_loader.count(),
        "active_sessions_count": len(active_sessions),
        "projects_count": len(projects_store),
    }


# -------------------------------------------------------------
# 项目库 API (Projects Hub)
# -------------------------------------------------------------
@app.get("/api/projects/list")
async def list_projects():
    """获取所有研究项目列表"""
    return {"projects": list(projects_store.values())}


@app.get("/api/project/file_tree")
async def get_project_file_tree(project_id: Optional[str] = None):
    """
    获取学术项目的成果资产与过程代码文件树结构 (参考现代 IDE 格式)
    组织为 5 大核心专业文件夹：
    1. 01_思考与过程代码
    2. 02_学术论文大作
    3. 03_出版级三线表
    4. 04_300DPI实证矢量图
    5. 05_综合验收与清单
    """
    pid = (project_id or CURRENT_PROJECT_ID or "proj-default-001").strip()
    base_dir = _project_deliverables(pid)

    def _file_info(rel_path: str, name: str, file_type: str, icon: str, desc: str):
        full_path = base_dir / rel_path
        exists = full_path.exists()
        size_str = ""
        if exists:
            sz = full_path.stat().st_size
            if sz < 1024:
                size_str = f"{sz} B"
            elif sz < 1024 * 1024:
                size_str = f"{sz / 1024:.1f} KB"
            else:
                size_str = f"{sz / (1024 * 1024):.1f} MB"
        return {
            "id": f"file_{rel_path.replace('/', '_').replace('.', '_')}",
            "name": name,
            "path": rel_path,
            "url": f"/deliverables/projects/{pid}/{rel_path}",
            "type": file_type, # python, markdown, latex, image, json
            "icon": icon,
            "desc": desc,
            "exists": exists,
            "size": size_str,
        }

    tree = [
        {
            "folder_id": "dir_01_code",
            "folder_name": "01_思考与过程代码",
            "icon": "📂",
            "desc": "因果拓扑推演、防范共线性审计与 CS-DID 估计过程源码",
            "files": [
                _file_info("code/dag_causal_audit.py", "dag_causal_audit.py", "python", "🐍", "因果有向无环图 (DAG) 前置审计与坏控制拦截"),
                _file_info("code/collinearity_guard.py", "collinearity_guard.py", "python", "🐍", "严格防范多重共线性审计与衍生变量清理"),
                _file_info("code/staggered_did_model.py", "staggered_did_model.py", "python", "🐍", "多期双向固定效应 CS-DID 异质性稳健回归"),
            ]
        },
        {
            "folder_id": "dir_02_paper",
            "folder_name": "02_学术论文大作",
            "icon": "📂",
            "desc": "Part 3 智能体结合资料库文献与实证结果生成的期刊级论文初稿",
            "files": [
                _file_info("academic_full_paper.md", "academic_full_paper.md", "markdown", "📝", "经管顶刊规范全文大作 (引言/文献/假说/实证/结论)"),
                _file_info("narratives/empirical_narrative_for_writing.md", "empirical_narrative.md", "markdown", "📝", "因果实证叙事与故事推演草稿"),
            ]
        },
        {
            "folder_id": "dir_03_tables",
            "folder_name": "03_出版级三线表",
            "icon": "📂",
            "desc": "AER / Top Journal 出版级三线表 (Markdown 与 LaTeX 源码)",
            "files": [
                _file_info("tables/table1_descriptive_stats.md", "table1_descriptive_stats.md", "markdown", "📊", "主要变量描述性统计三线表 (Markdown)"),
                _file_info("tables/table1_descriptive_stats.tex", "table1_descriptive_stats.tex", "latex", "📜", "主要变量描述性统计 (AER LaTeX 源码)"),
                _file_info("tables/table2_baseline_regression.md", "table2_baseline_regression.md", "markdown", "📊", "基准双向固定效应回归三线表 (Markdown)"),
                _file_info("tables/table2_baseline_regression.tex", "table2_baseline_regression.tex", "latex", "📜", "基准回归出版级 LaTeX AER 三线表源码"),
            ]
        },
        {
            "folder_id": "dir_04_figures",
            "folder_name": "04_300DPI实证矢量图",
            "icon": "📂",
            "desc": "300 DPI 出版级实证检验高分辨率矢量与位图图表",
            "files": [
                _file_info("figures/fig1_event_study_parallel_trends.png", "fig1_event_study_parallel_trends.png", "image", "📈", "动态平行趋势检验 (Event Study 95% 置信区间)"),
                _file_info("figures/fig2_honest_did_sensitivity.png", "fig2_honest_did_sensitivity.png", "image", "📈", "HonestDiD 相对偏离敏感性分析边界图"),
            ]
        },
        {
            "folder_id": "dir_05_reports",
            "folder_name": "05_综合验收与清单",
            "icon": "📂",
            "desc": "三阶段协同总结、学术规范验收报告与结构化资产清单",
            "files": [
                _file_info("academic_synthesis_report.md", "academic_synthesis_report.md", "markdown", "📋", "学术多智能体全流程综合验收总结报告"),
                _file_info("empirical_deliverables_manifest.json", "deliverables_manifest.json", "json", "📦", "实证交付成果资产结构化校验清单"),
            ]
        }
    ]
    # 只保留真实存在的文件，避免每个项目都显示同一批占位名
    for folder in tree:
        folder["files"] = [f for f in folder["files"] if f.get("exists")]
    tree = [f for f in tree if f["files"]]

    return {"status": "success", "project_id": pid, "tree": tree}


@app.get("/api/project/file_content")
async def get_project_file_content(path: str, project_id: Optional[str] = None):
    """按项目读取交付物文件内容（文件按项目隔离在 projects/<pid>/ 下）"""
    # 安全校验：禁止跨级跳转
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="非法文件访问路径")

    base_dir = _project_deliverables(project_id or CURRENT_PROJECT_ID)
    target = (base_dir / path).resolve()
    if not str(target).startswith(str(base_dir.resolve())) or not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在或尚未生成")
    
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"status": "success", "path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")


class CreateProjectRequest(BaseModel):
    name: str
    topic: str


@app.post("/api/projects/create")
async def create_project(req: CreateProjectRequest):
    """新建研究项目"""
    pid = f"proj-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
    sid = f"session-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    projects_store[pid] = {
        "project_id": pid,
        "name": req.name or "未命名学术课题项目",
        "topic": req.topic or "",
        "active_session_id": sid,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "library_items": [],
    }

    active_sessions[sid] = {
        "session_id": sid,
        "project_id": pid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "idle",
        "progress": 0,
        "logs": [],
        "chat_history": [
            {
                "sender": "coordinator",
                "sender_name": "编排总控智能体",
                "message": f"项目【{req.name}】已建立！您可以在此与各智能体深度交互，或在资料库中维护用于写作的文献与资料。",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
        ],
        "context_data": {
            "literature": [],
            "empirical": {},
            "hypotheses": [],
            "full_paper_text": None,
        },
        "result": None,
    }
    session_event_queues[sid] = asyncio.Queue()
    _persist_projects()
    _persist_session(sid)
    logger.info("创建新项目: %s, 绑定会话: %s", pid, sid)
    return {"project": projects_store[pid]}


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    topic: Optional[str] = None


@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, req: UpdateProjectRequest):
    """重命名项目 / 修改研究问题"""
    proj = projects_store.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="项目名称不能为空")
        proj["name"] = name
    if req.topic is not None:
        proj["topic"] = req.topic.strip()
    proj["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _persist_projects()
    logger.info("更新项目: %s", project_id)
    return {"status": "success", "project": proj}




@app.post("/api/projects/{project_id}/activate")
async def activate_project(project_id: str):
    """把工作台输出目录切到指定项目（资源管理器、交付物按项目隔离）"""
    if project_id not in projects_store:
        raise HTTPException(status_code=404, detail="项目不存在")
    d = _activate_project(project_id)
    return {"status": "success", "project_id": project_id, "deliverables_dir": to_rel(d)}

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """删除项目，并清理其下所有会话（不可恢复）"""
    proj = projects_store.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    if len(projects_store) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个项目，无法删除最后一个")

    for sid, st in list(active_sessions.items()):
        if st.get("project_id") == project_id:
            active_sessions.pop(sid, None)
            session_event_queues.pop(sid, None)
    try:
        store.delete_sessions_by_project(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("清理项目会话失败 %s: %s", project_id, exc)

    projects_store.pop(project_id, None)
    _persist_projects()
    try:
        import shutil as _sh
        d = DELIVERABLES_DIR / "projects" / project_id
        if d.exists():
            _sh.rmtree(d, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("清理项目交付目录失败 %s: %s", project_id, exc)

    # 若删的是当前打开的项目，回退到剩余的第一个
    fallback = next(iter(projects_store.values()), None)
    logger.info("删除项目: %s", project_id)
    return {"status": "success", "fallback_project": fallback}


# -------------------------------------------------------------
# 资料库 API (Research Assets & Library)
# -------------------------------------------------------------
@app.get("/api/library/items")
async def get_library_items(project_id: str = "proj-default-001"):
    """获取指定项目的资料库文献与文件列表"""
    proj = projects_store.get(project_id)
    if not proj:
        # 回退至第一个可用项目
        proj = next(iter(projects_store.values())) if projects_store else {"library_items": []}
    return {"items": proj.get("library_items", [])}


class SaveLibraryItemRequest(BaseModel):
    project_id: str
    item: Dict[str, Any]


@app.post("/api/library/save_item")
async def save_library_item(req: SaveLibraryItemRequest):
    """将 Part 1 检索到的文献保存到资料库中"""
    proj = projects_store.get(req.project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="未找到目标项目")

    item_data = req.item
    item_id = item_data.get("record_id") or f"lib-{uuid.uuid4().hex[:8]}"

    # 去重检查
    existing_ids = [x["item_id"] for x in proj["library_items"]]
    if item_id in existing_ids:
        return {"status": "exists", "message": "该文献已存在于资料库中。"}

    authors = item_data.get("authors", [])
    author_str = ", ".join([f"{a.get('family', '')} {a.get('given', '')}".strip() for a in authors if isinstance(a, dict)]) if authors else "Unknown"

    entry = {
        "item_id": item_id,
        "title": item_data.get("title", "未命名文献"),
        "authors": author_str,
        "year": str(item_data.get("year", "n.d.")),
        "venue": item_data.get("venue", "Working Paper"),
        "journal_tier": item_data.get("journal_ranking", {}).get("tier", "Regular"),
        "source_type": "search_saved",
        "abstract": item_data.get("abstract", "")[:300],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "raw_record": item_data,
    }
    proj["library_items"].append(entry)

    # 同步更新当前会话的上下文
    sid = proj.get("active_session_id")
    if sid and sid in active_sessions:
        active_sessions[sid]["context_data"]["literature"].append(item_data)
    _persist_projects()
    if sid:
        _persist_session(sid)

    return {"status": "success", "message": f"文献《{entry['title'][:20]}...》已成功纳入资料库！", "entry": entry}


@app.post("/api/library/upload_asset")
async def upload_asset_to_library(
    project_id: str = Form("proj-default-001"),
    title: str = Form(...),
    notes: Optional[str] = Form(""),
    file: Optional[UploadFile] = File(None),
):
    """用户手动向资料库上传文献或资料文件 (PDF/MD/BibTeX/Excel)"""
    proj = projects_store.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="未找到目标项目")

    file_name = file.filename if file else "文本资料"
    saved_path = None
    if file:
        target_path = UPLOAD_ASSETS_DIR / f"{uuid.uuid4().hex[:6]}_{file.filename}"
        with open(target_path, "wb") as f:
            f.write(await file.read())
        saved_path = str(target_path)

    entry = {
        "item_id": f"upload-{uuid.uuid4().hex[:8]}",
        "title": title or file_name,
        "authors": "用户上传资料",
        "year": str(datetime.now().year),
        "venue": file_name,
        "journal_tier": "Custom Upload",
        "source_type": "user_uploaded",
        "abstract": notes or f"用户本地上传文献资料: {file_name}",
        "file_path": saved_path,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    proj["library_items"].append(entry)

    # 同步注入上下文供 Part 3 引用
    sid = proj.get("active_session_id")
    if sid and sid in active_sessions:
        active_sessions[sid]["context_data"]["literature"].append({
            "title": title,
            "authors": [{"family": "用户资料", "given": ""}],
            "year": datetime.now().year,
            "venue": file_name,
            "screening_reason": notes,
        })
    _persist_projects()
    if sid:
        _persist_session(sid)

    return {"status": "success", "message": f"资料《{title}》已成功上传至资料库！", "entry": entry}


class LibraryItemPatch(BaseModel):
    project_id: str
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[str] = None
    venue: Optional[str] = None
    journal_tier: Optional[str] = None
    abstract: Optional[str] = None


@app.put("/api/library/item/{item_id}")
async def update_library_item(item_id: str, req: LibraryItemPatch):
    """编辑资料库条目（题名、作者、年份、期刊、等级、摘要）"""
    proj = projects_store.get(req.project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="未找到目标项目")
    target = next((x for x in proj.get("library_items", []) if x.get("item_id") == item_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="资料库中没有该条目")
    for field in ("title", "authors", "year", "venue", "journal_tier", "abstract"):
        val = getattr(req, field)
        if val is not None:
            target[field] = val.strip() if isinstance(val, str) else val
    target["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _persist_projects()
    sid = proj.get("active_session_id")
    if sid:
        _persist_session(sid)
    return {"status": "success", "item": target}


@app.post("/api/library/remove_item")
async def remove_library_item(project_id: str, item_id: str):
    """从资料库移除指定文献"""
    proj = projects_store.get(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="未找到目标项目")
    before = len(proj.get("library_items", []))
    proj["library_items"] = [x for x in proj["library_items"] if x.get("item_id") != item_id]
    _persist_projects()
    sid = proj.get("active_session_id")
    if sid:
        _persist_session(sid)
    return {"status": "success", "removed": before - len(proj["library_items"])}


# -------------------------------------------------------------
# 实证数据集：上传、列画像、预览
# -------------------------------------------------------------
SUPPORTED_DATA_EXT = {".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".dta", ".json", ".txt"}

# 列角色推断：命中即给出建议，用户仍可在前端改
_ROLE_HINTS: List[tuple] = [
    ("id_col", ("id", "code", "symbol", "stkcd", "firm", "company", "企业", "公司", "个体", "股票代码", "证券代码")),
    ("time_col", ("year", "time", "period", "date", "quarter", "month", "年份", "年度", "时间", "季度")),
    ("g_col", ("g", "first_treat", "treat_year", "policy_year", "adopt", "first", "首次", "处理年份", "政策年份", "试点年份")),
    ("treatment_col", ("treat", "treated", "did", "du", "policy", "处理", "政策", "试点")),
    ("outcome_col", ("y", "outcome", "dep", "dv", "roa", "roe", "tobin", "tfp", "patent", "ln", "被解释", "因变量")),
    ("cluster_col", ("industry", "ind", "province", "city", "region", "行业", "省份", "城市", "地区")),
]


def _dataset_index() -> Dict[str, Any]:
    if DATASET_INDEX_FILE.exists():
        try:
            with open(DATASET_INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.warning("数据集索引损坏，已重置")
    return {}


def _write_dataset_index(idx: Dict[str, Any]) -> None:
    with open(DATASET_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def _read_any(path: Path):
    import pandas as pd

    suf = path.suffix.lower()
    if suf in (".csv", ".tsv", ".txt"):
        sep = "\t" if suf == ".tsv" else None
        try:
            return pd.read_csv(path, sep=sep) if sep else pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="gbk")
    if suf in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if suf == ".parquet":
        return pd.read_parquet(path)
    if suf == ".dta":
        return pd.read_stata(path)
    if suf == ".json":
        return pd.read_json(path)
    raise ValueError(f"暂不支持的数据格式：{path.suffix}")


def _role_score(col: str, key: str) -> int:
    """
    列名与角色关键词的匹配强度。
    短键（如 y / g）只在完全相等或独立词元时命中，避免 leverage 因含字母 g 被误判为处理年份。
    """
    k = (key or "").lower()
    if not k:
        return 0
    low = col.lower()
    if low == k:
        return 100
    tokens = [t for t in re.split(r"[^a-z0-9\u4e00-\u9fff]+", low) if t]
    if k in tokens:
        return 80
    if not k.isascii() and k in col:      # 中文关键词直接子串匹配
        return 60
    if len(k) >= 4 and k in low:          # 英文长键才允许子串
        return 45
    return 0


def _assign_role_suggestions(columns: List[str]) -> Dict[str, List[str]]:
    """
    为每个角色挑出得分最高的列（且只允许归属一个角色），返回 列名 -> 建议角色列表。
    避免同一角色被多个列同时命中造成下拉框全标"建议"。
    """
    best: Dict[str, tuple] = {}           # role -> (score, col)
    for role, keys in _ROLE_HINTS:
        for col in columns:
            s = max((_role_score(col, k) for k in keys), default=0)
            if s <= 0:
                continue
            if role not in best or s > best[role][0]:
                best[role] = (s, col)

    out: Dict[str, List[str]] = {c: [] for c in columns}
    for role, (s, col) in best.items():
        if s >= 40:
            out.setdefault(col, []).append(role)
    return out


def _profile_dataframe(df) -> Dict[str, Any]:
    """列级画像：类型、唯一值数、缺失率、样例值、建议角色"""
    n_rows = int(len(df))
    names = [str(c) for c in df.columns]
    role_map = _assign_role_suggestions(names)

    cols: List[Dict[str, Any]] = []
    for c in df.columns:
        s = df[c]
        n_missing = int(s.isna().sum())
        try:
            n_unique = int(s.nunique(dropna=True))
        except Exception:
            n_unique = 0
        non_null = s.dropna()
        sample = [str(v)[:24] for v in non_null.head(3).tolist()]
        dtype = str(s.dtype)
        if dtype.startswith(("int", "float")):
            kind = "numeric"
        elif dtype == "bool":
            kind = "binary"
        elif dtype.startswith("datetime"):
            kind = "datetime"
        elif n_unique <= max(2, int(n_rows * 0.02)) and n_unique <= 40:
            kind = "categorical"
        else:
            kind = "text"
        if n_unique == 2 and kind != "numeric":
            kind = "binary"
        cols.append({
            "name": str(c),
            "dtype": dtype,
            "kind": kind,
            "n_unique": n_unique,
            "n_missing": n_missing,
            "missing_rate": round(n_missing / n_rows, 4) if n_rows else 0.0,
            "sample": sample,
            "suggested_roles": role_map.get(str(c), []),
        })
    return {
        "n_rows": n_rows,
        "n_cols": len(df.columns),
        "columns": cols,
    }


@app.post("/api/data/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    project_id: str = Form("proj-default-001"),
):
    """上传实证数据集并立即返回列级画像，供前端做列角色映射"""
    name = file.filename or "dataset.csv"
    suf = Path(name).suffix.lower()
    if suf not in SUPPORTED_DATA_EXT:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式 {suf}，支持：{sorted(SUPPORTED_DATA_EXT)}")

    file_id = f"ds-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    target = UPLOAD_DATASETS_DIR / f"{file_id}{suf}"
    content = await file.read()
    with open(target, "wb") as f:
        f.write(content)

    try:
        df = _read_any(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"文件解析失败：{exc}")

    profile = _profile_dataframe(df)
    idx = _dataset_index()
    idx[file_id] = {
        "file_id": file_id,
        "original_name": name,
        "path": to_rel(target),
        "project_id": project_id,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_rows": profile["n_rows"],
        "n_cols": profile["n_cols"],
    }
    _write_dataset_index(idx)

    return {
        "status": "success",
        "file_id": file_id,
        "original_name": name,
        "path": to_rel(target),
        "profile": profile,
    }


@app.get("/api/data/list")
async def list_datasets():
    """列出已上传的数据集（供列映射面板复用历史文件）"""
    return {"status": "success", "datasets": list(_dataset_index().values())}


@app.get("/api/data/profile/{file_id}")
async def get_dataset_profile(file_id: str):
    idx = _dataset_index()
    meta = idx.get(file_id)
    if not meta or not Path(abs_path(meta["path"])).exists():
        raise HTTPException(status_code=404, detail="未找到该数据集")
    try:
        df = _read_any(Path(abs_path(meta["path"])))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"文件解析失败：{exc}")
    return {"status": "success", "file_id": file_id, "meta": meta, "profile": _profile_dataframe(df)}


@app.get("/api/data/preview/{file_id}")
async def preview_dataset(file_id: str, rows: int = 12):
    idx = _dataset_index()
    meta = idx.get(file_id)
    if not meta or not Path(abs_path(meta["path"])).exists():
        raise HTTPException(status_code=404, detail="未找到该数据集")
    df = _read_any(Path(abs_path(meta["path"]))).head(max(1, min(rows, 200)))
    return {
        "status": "success",
        "columns": [str(c) for c in df.columns],
        "rows": df.where(df.notna(), None).values.tolist(),
    }


# -------------------------------------------------------------
# EconLit 文献检索工作台独立检索 API (Part 1 专属面板接口)
# -------------------------------------------------------------
class DirectSearchRequest(BaseModel):
    research_question: str
    working_query: Optional[str] = None
    start_year: int = 2015
    end_year: int = 2026
    limit_per_source: int = 10
    search_mode: str = "exploratory"
    ranking_mode: str = "relevance"


@app.post("/api/literature/direct_search")
async def direct_literature_search(req: DirectSearchRequest):
    """供弹出的 EconLit 文献检索面板直接执行多源检索"""
    logger.info("EconLit 检索面板发起检索: %s", req.research_question)
    search_output = coordinator.search_agent.plan_and_search(
        research_question=req.research_question,
        start_year=req.start_year,
        end_year=req.end_year,
        max_records=req.limit_per_source,
    )
    return search_output


# -------------------------------------------------------------
# Part 1 文献检索工作台（原 :8765 独立前端，现统一进 :8088）
# -------------------------------------------------------------

class LitProtocolRequest(BaseModel):
    research_question: str


class LitSearchRequest(BaseModel):
    payload: Dict[str, Any]


class LitExportRequest(BaseModel):
    records: List[Dict[str, Any]]
    format: str = "ris"


class LitZoteroSaveRequest(BaseModel):
    records: List[Dict[str, Any]]
    collection_key: str = ""


class LitScreenRequest(BaseModel):
    session_id: str
    record_id: str
    status: str
    reason: Optional[str] = None


def _bridge_guard() -> None:
    """Part 1 不可用时给出明确错误，而不是返回假结果"""
    st = literature_bridge.status()
    if not st.get("available"):
        raise HTTPException(status_code=503, detail=st.get("error") or "Part 1 检索能力不可用")


@app.get("/api/lit/status")
async def lit_status():
    return literature_bridge.status()


@app.post("/api/lit/protocol")
async def lit_protocol(req: LitProtocolRequest):
    _bridge_guard()
    try:
        return literature_bridge.protocol(req.research_question)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"生成检索方案失败：{exc}")


@app.post("/api/lit/search")
async def lit_search(req: LitSearchRequest):
    _bridge_guard()
    try:
        return literature_bridge.search(req.payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"检索失败：{exc}")


@app.post("/api/lit/export")
async def lit_export(req: LitExportRequest):
    _bridge_guard()
    try:
        return literature_bridge.export(req.records, req.format or "ris")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"导出失败：{exc}")


@app.post("/api/lit/screen")
async def lit_screen(req: LitScreenRequest):
    _bridge_guard()
    try:
        return literature_bridge.screening(req.session_id, req.record_id, req.status, req.reason)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"筛选记录失败：{exc}")


@app.get("/api/lit/sessions")
async def lit_sessions():
    _bridge_guard()
    return {"sessions": literature_bridge.sessions()}


class ZoteroConfigRequest(BaseModel):
    api_key: str = ""
    default_collection: str = ""


@app.get("/api/lit/zotero/status")
async def lit_zotero_status():
    """同时探测 Connector 通道与 Local API 通道，并给出开启指引"""
    import zotero_bridge
    return zotero_bridge.status()


@app.post("/api/lit/zotero/config")
async def lit_zotero_config(req: ZoteroConfigRequest):
    """保存 Zotero API key（写入 ~/.aca/secrets.json，600 权限）"""
    import zotero_bridge
    return zotero_bridge.set_config(req.api_key, req.default_collection)


@app.get("/api/lit/zotero/collections")
async def lit_zotero_collections():
    """列出本机 Zotero 分类库"""
    import zotero_bridge
    data = zotero_bridge.collections()
    if data.get("error"):
        # 未配置 key 属正常状态，不该报 5xx
        return data
    return data


@app.post("/api/lit/zotero/save")
async def lit_zotero_save(req: LitZoteroSaveRequest):
    _bridge_guard()
    import zotero_bridge
    try:
        return zotero_bridge.save(req.records, req.collection_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        # 典型：本机 Zotero 未启动或未开启"允许本机其他应用与 Zotero 通信"
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"写入 Zotero 失败：{exc}")


# -------------------------------------------------------------
# 期刊格式档案（写作目标期刊下拉的数据来源）
# -------------------------------------------------------------

@app.get("/api/journals")
async def list_journals():
    from core.journal_profiles import journal_catalog
    return {"journals": journal_catalog()}

# -------------------------------------------------------------
# 中文文献通道：真检索 + 中文库直达 + 题录回导
# -------------------------------------------------------------

class CnSearchRequest(BaseModel):
    query: str
    limit: int = 20
    sources: List[str] = []


@app.post("/api/lit/cn/search")
async def lit_cn_search(req: CnSearchRequest):
    """
    中文检索。走 OpenAlex / Crossref（真实返回），并如实附带覆盖边界说明与
    CNKI/万方/维普/国家哲社文献中心的直达链接（这些库有登录墙，程序化抓取不可靠）。
    """
    import cn_lit
    try:
        return cn_lit.search_cn(req.query, req.limit, req.sources or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"中文检索失败：{exc}")


@app.get("/api/lit/cn/manual")
async def lit_cn_manual(query: str = ""):
    """生成带预填检索式的中文库直达链接"""
    import cn_lit
    return {"links": cn_lit.manual_links(query)}


class LitImportRequest(BaseModel):
    content: str
    format: str = "auto"


@app.post("/api/lit/import")
async def lit_import(req: LitImportRequest):
    """回导 CNKI / 万方 / 维普 导出的 .ris / .bib / .enw 题录文件"""
    import cn_lit
    try:
        records = cn_lit.parse_import(req.content, req.format or "auto")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"records": records, "n_records": len(records), "format": req.format or "auto"}


# -------------------------------------------------------------
# Word 导出（CSSCI 取向：三线表 + 参考文献悬挂缩进）
# -------------------------------------------------------------

class DocxExportRequest(BaseModel):
    session_id: Optional[str] = None
    title: str = ""
    journal: str = ""
    sections: Dict[str, str] = {}
    references: List[Dict[str, Any]] = []
    deliverables: Dict[str, Any] = {}


@app.post("/api/export/docx")
async def export_docx(req: DocxExportRequest):
    """
    导出 Word。带 session_id 时自动从会话中取论文分节、文献与实证表格；
    也可直接传 sections/references 做临时导出。
    """
    try:
        from core.docx_export import build_extra_tables, export_paper_docx
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"缺少 Word 导出依赖 python-docx：{exc}")

    sections = dict(req.sections or {})
    references = list(req.references or [])
    deliverables = dict(req.deliverables or {})
    title = req.title or ""
    journal = req.journal or ""

    if req.session_id:
        sess = active_sessions.get(req.session_id) or {}
        ctx = sess.get("context_data") or {}
        res = sess.get("result") or {}
        if not sections:
            sections = ctx.get("paper_sections") or {}
        if not sections and ctx.get("full_paper_text"):
            sections = {"正文": ctx["full_paper_text"]}
        if not references:
            references = ctx.get("literature") or []
        if not deliverables:
            deliverables = res.get("deliverables") or {}
        if not title:
            title = res.get("research_topic") or sess.get("task_input", {}).get("research_topic") or ""
        if not journal:
            journal = ctx.get("target_journal") or ""

    if not sections:
        raise HTTPException(status_code=400, detail="没有可导出的论文内容：请先跑一次写作，或直接传入 sections")

    out_name = f"paper_{req.session_id or 'adhoc'}_{datetime.now().strftime('%H%M%S')}.docx"
    out_path = DELIVERABLES_DIR / out_name
    try:
        info = export_paper_docx(
            title=title,
            sections=sections,
            out_path=str(out_path),
            journal=journal,
            references=references,
            extra_tables=build_extra_tables(deliverables),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("导出 Word 失败")
        raise HTTPException(status_code=500, detail=f"导出 Word 失败：{exc}")

    return {"status": "success", "url": f"/deliverables/{out_name}", **info}


# -------------------------------------------------------------
# 对话交互与工作流调度 API
# -------------------------------------------------------------
def _ensure_session(session_id: str) -> Dict[str, Any]:
    """确保 session 存在，若服务重启导致内存丢失则自动自愈初始化"""
    if session_id not in active_sessions:
        matched_pid = "proj-default-001"
        topic = "国家碳排放权交易试点(ETS)对企业数字化转型的政策效应——兼论管理层短视的调节作用"
        for pid, pdata in projects_store.items():
            if pdata.get("active_session_id") == session_id:
                matched_pid = pid
                topic = pdata.get("topic") or pdata.get("name")
                break
        
        active_sessions[session_id] = {
            "session_id": session_id,
            "project_id": matched_pid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "idle",
            "progress": 0,
            "logs": [],
            "chat_history": [],
            "context_data": {
                "literature": [],
                "empirical": {},
                "hypotheses": [],
                "full_paper_text": None,
            },
            "task_input": {
                "research_topic": topic,
            },
            "result": None,
        }
        if session_id not in session_event_queues:
            session_event_queues[session_id] = asyncio.Queue()
        logger.info("已自动自愈恢复学术会话: %s (关联项目: %s)", session_id, matched_pid)
    return active_sessions[session_id]


@app.post("/api/chat/send")
async def send_chat_message(req: ChatMessageRequest):
    session_id = req.session_id
    sess = _ensure_session(session_id)

    user_msg_entry = {
        "sender": "user",
        "sender_name": "研究者 (您)",
        "message": req.message,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    sess["chat_history"].append(user_msg_entry)

    # 优先获取当前所属项目资料库中的文献
    pid = sess.get("project_id")
    library_records = projects_store.get(pid, {}).get("library_items", []) if pid else []
    
    # 转换为 literature records 格式
    formatted_lit = []
    for it in library_records:
        formatted_lit.append({
            "title": it.get("title"),
            "authors": [{"family": it.get("authors", "Scholar"), "given": ""}],
            "year": it.get("year", "2023"),
            "venue": it.get("venue", "Journal"),
            "screening_reason": it.get("abstract", ""),
        })

    context = {
        "task_input": sess.get("task_input", {}) or {},
        "literature": formatted_lit or sess.get("context_data", {}).get("literature", []),
        "empirical": sess.get("context_data", {}).get("empirical", {}),
        "hypotheses": sess.get("context_data", {}).get("hypotheses", []),
        "deliverables": (sess.get("result") or {}).get("deliverables", {}),
    }

    agent_reply = coordinator.dispatch_chat(
        session_id=session_id,
        target_agent=req.target_agent,
        user_message=req.message,
        session_context=context,
    )

    agent_names = {
        "coordinator": "编排总控智能体",
        "literature_search": "文献检索智能体 (Part 1)",
        "empirical_research": "因果实证分析智能体 (Part 2)",
        "academic_writing": "学术综述与全文写作智能体 (Part 3)",
    }

    reply_entry = {
        "sender": req.target_agent,
        "sender_name": agent_names.get(req.target_agent, "学术助手"),
        "message": agent_reply,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    sess["chat_history"].append(reply_entry)
    token_tracker.record_usage(session_id, req.message, agent_reply)

    await _push_event(session_id, "chat_message", agent_reply, sess.get("progress", 0), {
        "reply": reply_entry,
    })

    return {"status": "success", "reply": reply_entry}


@app.post("/api/chat/stream")
async def stream_chat_message(req: ChatMessageRequest):
    """
    单智能体流式对话 SSE 接口 (Server-Sent Events)
    实时推流思考链 (Thinking Process)、秒表耗时 (Thinking Time) 与正文打字机流式输出
    """
    session_id = req.session_id
    sess = _ensure_session(session_id)

    user_msg_entry = {
        "sender": "user",
        "sender_name": "研究者 (您)",
        "message": req.message,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    sess["chat_history"].append(user_msg_entry)


    # 优先获取当前所属项目资料库中的文献
    pid = sess.get("project_id")
    library_records = projects_store.get(pid, {}).get("library_items", []) if pid else []

    formatted_lit = []
    for it in library_records:
        formatted_lit.append({
            "title": it.get("title"),
            "authors": [{"family": it.get("authors", "Scholar"), "given": ""}],
            "year": it.get("year", "2023"),
            "venue": it.get("venue", "Journal"),
            "screening_reason": it.get("abstract", ""),
        })

    context = {
        "task_input": sess.get("task_input", {}) or {},
        "literature": formatted_lit or sess.get("context_data", {}).get("literature", []),
        "empirical": sess.get("context_data", {}).get("empirical", {}),
        "hypotheses": sess.get("context_data", {}).get("hypotheses", []),
        "deliverables": (sess.get("result") or {}).get("deliverables", {}),
        "chat_history": sess.get("chat_history", []),
    }

    agent_names = {
        "coordinator": "编排总控智能体",
        "literature_search": "文献检索智能体 (Part 1)",
        "empirical_research": "因果实证分析智能体 (Part 2)",
        "academic_writing": "学术综述与全文写作智能体 (Part 3)",
    }
    sender_name = agent_names.get(req.target_agent, "学术助手")

    async def event_generator():
        # 首先推送一条元数据帧，告知智能体身份
        init_frame = {
            "type": "init",
            "sender": req.target_agent,
            "sender_name": sender_name,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        yield f"data: {json.dumps(init_frame, ensure_ascii=False)}\n\n"

        full_content = ""
        full_thought = ""
        thought_time = 0.0

        for frame in coordinator.dispatch_chat_stream(
            session_id=session_id,
            target_agent=req.target_agent,
            user_message=req.message,
            session_context=context,
        ):
            ftype = frame.get("type")
            if ftype == "content":
                full_content += frame.get("delta", "")
            elif ftype == "thought":
                full_thought += frame.get("delta", "")
                thought_time = frame.get("thought_time", thought_time)
            elif ftype == "thought_end":
                thought_time = frame.get("thought_time", thought_time)
            elif ftype == "done":
                full_content = frame.get("full_content", full_content)
                full_thought = frame.get("full_thought", full_thought)
                thought_time = frame.get("thought_time", thought_time)

            yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.001)

        # 录入会话全局历史
        reply_entry = {
            "sender": req.target_agent,
            "sender_name": sender_name,
            "message": full_content,
            "thought_process": full_thought,
            "thought_time": thought_time,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        sess["chat_history"].append(reply_entry)
        token_tracker.record_usage(session_id, req.message, full_content)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



def _run_custom_pipeline_background(session_id: str, req: ResearchTaskRequest, custom_data_path: Optional[str] = None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def execute():
        try:
            active_sessions[session_id]["status"] = "running"
            await _push_event(session_id, "start", f"课题已立项: 《{req.research_topic}》", 5)

            pid = active_sessions[session_id].get("project_id") or req.project_id
            proj = projects_store.get(pid, {})

            search_output = {}
            if req.enable_search:
                await _push_event(session_id, "agent_step", "【文献检索智能体 (Part 1)】启动多源检索与期刊定级...", 20)
                await asyncio.sleep(0.5)
                search_output = coordinator.search_agent.plan_and_search(
                    research_question=req.research_topic,
                    max_records=8,
                )
                
                # 检索完成后自动将精选文献存入项目资料库
                if proj and "library_items" in proj:
                    for r in search_output.get("records", []):
                        authors = r.get("authors", [])
                        author_str = ", ".join([f"{a.get('family', '')} {a.get('given', '')}".strip() for a in authors if isinstance(a, dict)]) if authors else "Unknown"
                        proj["library_items"].append({
                            "item_id": r.get("record_id", f"rec-{uuid.uuid4().hex[:6]}"),
                            "title": r.get("title", ""),
                            "authors": author_str,
                            "year": str(r.get("year", "n.d.")),
                            "venue": r.get("venue", "Working Paper"),
                            "journal_tier": r.get("journal_ranking", {}).get("tier", "Regular"),
                            "source_type": "search_saved",
                            "abstract": r.get("abstract", "")[:300],
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "raw_record": r,
                        })

                active_sessions[session_id]["context_data"]["literature"] = search_output.get("records", [])
                await _push_event(
                    session_id,
                    "agent_step",
                    f"【文献检索智能体】检索完成，已纳入 {len(search_output.get('records', []))} 篇权威核心文献并同步注入资料库",
                    35,
                    {"records": search_output.get("records", [])},
                )

            empirical_output: Dict[str, Any] = {}
            # 实证 + 写作：交给带回环的编排中枢，同步任务在线程池执行以免阻塞事件循环
            loop_ref = asyncio.get_event_loop()

            def on_event(etype: str, msg: str, progress: int):
                try:
                    asyncio.run_coroutine_threadsafe(
                        _push_event(session_id, etype, msg, progress), loop_ref
                    )
                except Exception:
                    pass

            task = req.to_task_spec()
            # 把本次检索到的真实文献交给写作智能体（检索阶段已在上方完成）
            task.literature_records = search_output.get("records", [])

            result = await loop.run_in_executor(
                None,
                functools.partial(
                    coordinator.run_pipeline,
                    task=task,
                    enable_search=False,  # 检索已在上方完成，避免重复调用
                    enable_empirical=req.enable_empirical,
                    enable_writing=req.enable_writing,
                    max_attempts=req.max_strategy_attempts,
                    session_id=session_id,
                    on_event=on_event,
                ),
            )
            if req.enable_empirical:
                empirical_output = result.get("empirical") or {}
                active_sessions[session_id]["context_data"]["empirical"] = empirical_output
                att = (empirical_output.get("att") or {}).get("coef")
                if empirical_output.get("status") == "failed":
                    await _push_event(
                        session_id, "agent_step",
                        "【因果实证智能体】未能执行：" + "；".join(empirical_output.get("errors", [])), 70,
                    )
                else:
                    verdict = (empirical_output.get("review") or {}).get("verdict")
                    await _push_event(
                        session_id, "agent_step",
                        f"【因果实证智能体】ATT = {att if att is None else round(att, 4)}，"
                        f"审稿人判定 {verdict}，尝试策略 {', '.join(empirical_output.get('attempted_strategies', []))}",
                        75,
                    )

            review_output = {}
            full_paper_path = None
            if req.enable_writing:
                paper = result.get("paper") or {}
                review_output = paper
                full_text = paper.get("full_text") or ""
                if full_text:
                    full_paper_file = coordinator.output_dir / f"academic_full_paper_{session_id}.md"
                    with open(full_paper_file, "w", encoding="utf-8") as f:
                        f.write(full_text)
                    full_paper_path = f"/deliverables/academic_full_paper_{session_id}.md"
                    active_sessions[session_id]["context_data"]["full_paper_text"] = full_text
                    # 保留分节结构，供 Word 导出按章节排版用（否则只能整篇塞进一个块）
                    active_sessions[session_id]["context_data"]["paper_sections"] = paper.get("sections", {})
                    active_sessions[session_id]["context_data"]["target_journal"] = req.target_journal
                    await _push_event(
                        session_id, "agent_step",
                        f"【学术写作智能体】已生成 {len(paper.get('sections', {}))} 个章节的论文正文", 95,
                    )
                else:
                    await _push_event(
                        session_id, "agent_step",
                        "【学术写作智能体】未产出正文：" + "；".join(paper.get("warnings", ["未知原因"])), 95,
                    )

            synthesis_report = coordinator._assemble_synthesis_report(
                session_id=session_id,
                research_topic=req.research_topic,
                search_result=search_output,
                review_result=review_output,
                empirical_output=empirical_output,
            )
            report_file = coordinator.output_dir / f"academic_synthesis_report_{session_id}.md"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(synthesis_report)

            deliverables = empirical_output.get("deliverables") or {}
            tables = deliverables.get("tables") or {}
            figs = deliverables.get("figures") or {}
            final_package = {
                "session_id": session_id,
                "project_id": pid,
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "research_topic": req.research_topic,
                "methodology": empirical_output.get("strategy_used") or req.methodology,
                "deliverables": {
                    "synthesis_report_markdown": f"/deliverables/academic_synthesis_report_{session_id}.md",
                    "academic_full_paper_markdown": full_paper_path,
                    "table1_descriptive_stats_markdown": _to_web_url((tables.get("table1_descriptive_stats") or {}).get("markdown")),
                    "table2_baseline_markdown": _to_web_url((tables.get("table2_baseline_regression") or {}).get("markdown")),
                    "table2_baseline_latex": _to_web_url((tables.get("table2_baseline_regression") or {}).get("latex")),
                    "figures": {k: _to_web_url(v.get("png")) for k, v in figs.items()},
                    "writing_narrative": _to_web_url(deliverables.get("narrative_for_writing")),
                },
                "literature_count": len(search_output.get("records", [])),
                "att": empirical_output.get("att"),
                "review_verdict": (empirical_output.get("review") or {}).get("verdict"),
                "attempted_strategies": empirical_output.get("attempted_strategies", []),
                "carried_concerns": empirical_output.get("carried_concerns", []),
                "run_id": empirical_output.get("run_id"),
                "skill_trace": empirical_output.get("skill_trace", []),
                "provenance": empirical_output.get("provenance"),
                "warnings": empirical_output.get("warnings", []),
            }

            active_sessions[session_id]["status"] = "completed"
            active_sessions[session_id]["result"] = final_package

            await _push_event(
                session_id,
                "finished",
                "🎉 所选学术智能体协同任务圆满完成！已更新全部学术资产、资料库与完整论文初稿。",
                100,
                final_package,
            )
            _persist_session(session_id)

        except Exception as e:
            logger.exception("执行工作流异常: %s", e)
            active_sessions[session_id]["status"] = "failed"
            await _push_event(session_id, "error", f"执行异常中断: {str(e)}", 100)
            _persist_session(session_id)

    loop.run_until_complete(execute())
    loop.close()


@app.post("/api/workflow/submit")
async def submit_workflow(
    req: ResearchTaskRequest,
    background_tasks: BackgroundTasks,
):
    session_id = req.session_id
    if not session_id or session_id not in active_sessions:
        session_id = f"session-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        active_sessions[session_id] = {
            "session_id": session_id,
            "project_id": req.project_id or "proj-default-001",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "queued",
            "progress": 0,
            "logs": [],
            "chat_history": [],
            "context_data": {"literature": [], "empirical": {}, "hypotheses": []},
            "result": None,
        }
        session_event_queues[session_id] = asyncio.Queue()

    active_sessions[session_id]["task_input"] = req.dict()
    background_tasks.add_task(_run_custom_pipeline_background, session_id, req, None)
    return {
        "status": "accepted",
        "session_id": session_id,
        "message": "学术研究任务已接受调度",
    }


@app.get("/api/workflow/stream/{session_id}")
async def stream_workflow_progress(session_id: str):
    if session_id not in session_event_queues:
        session_event_queues[session_id] = asyncio.Queue()

    queue = session_event_queues[session_id]

    async def event_generator():
        if session_id in active_sessions:
            for log in active_sessions[session_id].get("logs", []):
                yield f"data: {json.dumps({'event_type': log['event_type'], 'message': log['message'], 'timestamp': log['timestamp']}, ensure_ascii=False)}\n\n"

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield f": ping {datetime.now().strftime('%H:%M:%S')}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# -------------------------------------------------------------
# 技能管理与 Token 监控 API
# -------------------------------------------------------------
@app.get("/api/skills/tree")
async def get_skills_tree():
    return skills_manager.scan_all_skills()


@app.get("/api/skills/content")
async def get_skill_content(path: str):
    try:
        content = skills_manager.get_skill_content(path)
        return {"status": "success", "path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


class SaveSkillRequest(BaseModel):
    path: str
    content: str


@app.post("/api/skills/save")
async def save_skill_content(req: SaveSkillRequest):
    try:
        skills_manager.update_skill_content(req.path, req.content)
        return {"status": "success", "message": "技能规则已成功更新并落盘！"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ResetSkillRequest(BaseModel):
    skill_id: str
    path: str


@app.post("/api/skills/reset")
async def reset_skill_content(req: ResetSkillRequest):
    try:
        restored = skills_manager.reset_skill_to_default(req.skill_id, req.path)
        return {"status": "success", "message": "已成功恢复至出厂默认版本！", "content": restored}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UploadSkillRequest(BaseModel):
    category_folder: str = "03_identification"
    skill_name: str
    content: str


@app.post("/api/skills/upload")
async def upload_new_skill(req: UploadSkillRequest):
    try:
        new_path = skills_manager.upload_new_skill(req.category_folder, req.skill_name, req.content)
        return {"status": "success", "message": f"新技能【{req.skill_name}】已成功注入！", "path": new_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/list")
async def list_runs(session_id: Optional[str] = None, limit: int = 50):
    """列出历史运行记录（重启后仍可回溯）"""
    return {"status": "success", "runs": store.list_runs(session_id=session_id, limit=limit)}


@app.get("/api/runs/{run_id}")
async def get_run_detail(run_id: str):
    """查看单次运行的完整留痕：每次策略尝试、审稿判定、产出物索引"""
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="未找到该运行记录")

    # 结果摘要：解析 result_json 中的关键字段，让前端无需二次解析
    try:
        result = json.loads(run.get("result_json") or "{}")
    except Exception:
        result = {}
    run["carried_concerns"] = result.get("carried_concerns", []) or []
    run["warnings"] = result.get("warnings", []) or []
    run["provenance"] = result.get("provenance")
    run["review_reasons"] = (result.get("review") or {}).get("reasons", [])

    # 产出物补上前端可直接打开的 URL
    artifacts = []
    for a in store.list_artifacts(run_id):
        a = dict(a)
        a["web_url"] = _to_web_url(a.get("path"))
        artifacts.append(a)

    # 留痕步骤：reasons 在库中以 JSON 字符串存储，反序列化为数组便于前端渲染
    steps = []
    for s in store.list_steps(run_id):
        s = dict(s)
        raw = s.get("reasons")
        if isinstance(raw, str):
            try:
                s["reasons"] = json.loads(raw)
            except Exception:
                s["reasons"] = [raw] if raw else []
        steps.append(s)

    return {
        "status": "success",
        "run": run,
        "steps": steps,
        "artifacts": artifacts,
    }


@app.get("/api/tokens/stats")
async def get_token_stats(session_id: str = "default"):
    return token_tracker.get_session_stats(session_id)


from orchestrator.llm_client import academic_llm_client


class LLMConfigRequest(BaseModel):
    provider: str = "deepseek"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model_name: str = "deepseek-chat"
    is_custom_enabled: bool = True


@app.get("/api/tokens/config")
async def get_llm_config():
    """获取当前生效的大模型配置（api_key 一律脱敏回显，不外泄明文）"""
    token_tracker.llm_config = token_tracker._load_config()
    return {"status": "success", "config": token_tracker.public_config()}


@app.post("/api/tokens/config")
@app.post("/api/tokens/config_llm")
async def save_llm_config(req: LLMConfigRequest):
    """保存大模型 API 配置并即时重载生效（密钥写入用户级密钥库，不落项目目录）"""
    cfg_dict = req.dict(exclude_none=False)
    token_tracker.save_config(cfg_dict)
    academic_llm_client.reload_config()
    logger.info("已热重载学术大模型客户端配置: provider=%s, model=%s", req.provider, req.model_name)
    return {
        "status": "success",
        "message": f"大模型配置（{req.provider} · {req.model_name}）已成功保存并即刻生效！",
        "config": token_tracker.public_config(),
    }


@app.post("/api/tokens/test_connection")
async def test_llm_connection(req: LLMConfigRequest):
    """在线测试大模型 API 连通性"""
    res = academic_llm_client.test_connection(req.dict())
    return res


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)

# -------------------------------------------------------------
# 数据搜集：公开数据源直接拉取 → 登记为可分析数据集
# -------------------------------------------------------------
class CollectRequest(BaseModel):
    provider: str
    indicator: str = ""
    start: int = 2000
    end: int = 2024
    countries: List[str] = []
    url: str = ""


@app.get("/api/data/collect/catalog")
async def data_collect_catalog():
    import data_providers as dp
    return dp.catalog()


@app.post("/api/data/collect/run")
async def data_collect_run(req: CollectRequest):
    import data_providers as dp
    try:
        df = dp.collect(req.provider, req.indicator, req.start, req.end, req.countries, req.url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"抓取失败：{exc}")
    if df is None or len(df) == 0:
        raise HTTPException(status_code=400, detail="抓取结果为空")

    file_id = f"ds-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    target = UPLOAD_DATASETS_DIR / f"{file_id}.csv"
    df.to_csv(target, index=False, encoding="utf-8-sig")

    profile = _profile_dataframe(df)
    idx = _dataset_index()
    idx[file_id] = {
        "file_id": file_id,
        "original_name": f"{dp.suggested_filename(req.provider, req.indicator)}_{req.start}-{req.end}.csv",
        "path": to_rel(target),
        "project_id": "proj-default-001",
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_rows": profile["n_rows"],
        "n_cols": profile["n_cols"],
        "source": req.provider,
        "indicator": req.indicator,
    }
    _write_dataset_index(idx)
    logger.info("数据搜集入库: %s (%s/%s) %s 行", file_id, req.provider, req.indicator, profile["n_rows"])
    return {
        "status": "success",
        "file_id": file_id,
        "original_name": idx[file_id]["original_name"],
        "profile": profile,
        "source": req.provider,
        "indicator": req.indicator,
    }


@app.delete("/api/data/dataset/{file_id}")
async def delete_dataset(file_id: str):
    """删除数据集：同时清理磁盘文件与索引"""
    idx = _dataset_index()
    meta = idx.get(file_id)
    if not meta:
        raise HTTPException(status_code=404, detail="未找到该数据集")
    try:
        p = Path(abs_path(meta.get("path", "")))
        if p.exists():
            p.unlink()
    except Exception as exc:  # noqa: BLE001
        logger.warning("删除数据集文件失败 %s: %s", file_id, exc)
    idx.pop(file_id, None)
    _write_dataset_index(idx)
    return {"status": "success", "deleted": file_id}
