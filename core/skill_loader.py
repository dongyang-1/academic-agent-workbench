# -*- coding: utf-8 -*-
"""
技能加载与注入层 (Skill Loader)

解决的问题：
    整改前三个 part 下的 28 个 SKILL.md + 两份期刊格式包（28 个章节技能）
    只被前端当作"文本文件"浏览，执行链路完全没有加载它们——改 SKILL.md
    对最终产出零影响。

设计原则（重要）：
    ┌ 确定性计算（估计量、标准误、检验统计量）**不受** SKILL.md 影响，
    │  以保证结果可复现、可复核。
    └ LLM 生成部分（论文正文、对话答复、审稿意见措辞、文献筛选理由）
       **受** SKILL.md 影响，这才是"改技能即改行为"的落点。

能力：
    1. 扫描全部 SKILL.md（part1 / part2 / part3 / 两份期刊格式包），解析 frontmatter
    2. 按智能体 + 上下文（识别策略、目标期刊、阶段）路由出应生效的技能
    3. 把技能正文拼装成可注入系统提示的文本（带长度预算与截断保护）
    4. 记录每次调用实际生效的技能清单，供运行留痕与前端展示
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("aca.skill_loader")

INTEGRATED_ROOT = Path(__file__).resolve().parents[1]

PART1_SKILLS = INTEGRATED_ROOT / "part1-paper" / "skills"
PART2_SKILLS = INTEGRATED_ROOT / "part2-empirical-research" / "skills"
PART3_SKILL = INTEGRATED_ROOT / "part3-文献综述" / "zotero-literature-review" / "SKILL.md"
FORMATS_DIR = INTEGRATED_ROOT / "part3-文献综述" / "formats"
SKILL_REGISTRY = INTEGRATED_ROOT / "part2-empirical-research" / "skills" / "skill-registry.yaml"

# 识别策略 → part2 技能 id（确定性估计器之外的"规范来源"）
STRATEGY_TO_SKILL: Dict[str, List[str]] = {
    "cs_did": ["staggered-did", "did"],
    "staggered_did": ["staggered-did", "did"],
    "twfe": ["did"],
    "did": ["did"],
    "iv": ["iv"],
    "rdd": ["rdd"],
    "scm": ["synthetic-control"],
    "synthetic_control": ["synthetic-control"],
    "psm": ["matching"],
    "matching": ["matching"],
    "dml": ["double-machine-learning"],
    "event_study": ["local-projections", "staggered-did"],
    "shift_share": ["shift-share"],
    "bunching": ["bunching-design"],
    "rkd": ["regression-kink-design"],
}

# 实证智能体始终生效的通用技能
EMPIRICAL_COMMON_SKILLS = ["data-audit", "econometric-reviewer"]
# 产出阶段生效
OUTPUT_SKILLS = ["tables-and-figures"]

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# 章节规范名 → 各期刊包可能的目录名后缀（命名不统一，注入前先归一）
SECTION_ALIASES: Dict[str, Tuple[str, ...]] = {
    "results": ("results", "tables-figures", "tables", "figures"),
    "robustness": ("robustness", "inference"),
    "identification": ("identification", "did-identification", "modern-did"),
    "abstract": ("abstract", "abstract-english"),
    "mechanism": ("mechanism", "mechanism-heterogeneity"),
    "heterogeneity": ("heterogeneity", "mechanism-heterogeneity"),
    "data_sample": ("data-sample", "data-availability"),
    "literature_review": ("literature-review",),
    "theory_hypotheses": ("theory-hypotheses", "theory"),
    "policy": ("policy-implication", "policy"),
}


def _parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """解析 SKILL.md 的 YAML frontmatter；无 frontmatter 时返回空元数据。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("-"):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, text[m.end():]


class Skill:
    """单个技能"""

    __slots__ = ("skill_id", "path", "_meta", "_body", "_hash")

    def __init__(self, skill_id: str, path: Path):
        self.skill_id = skill_id
        self.path = path
        self._meta: Dict[str, str] = {}
        self._body: str = ""
        self._hash: str = ""

    def load(self) -> "Skill":
        try:
            text = self.path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取技能失败 %s: %s", self.path, exc)
            text = ""
        self._meta, self._body = _parse_frontmatter(text)
        self._hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
        return self

    def _ensure(self) -> None:
        if not self._hash:
            self.load()

    @property
    def name(self) -> str:
        self._ensure()
        return self._meta.get("name") or self.path.parent.name

    @property
    def name_zh(self) -> str:
        self._ensure()
        return self._meta.get("name_zh") or self.name

    @property
    def category(self) -> str:
        self._ensure()
        return self._meta.get("category", "")

    @property
    def meta(self) -> Dict[str, str]:
        self._ensure()
        return self._meta

    @property
    def body(self) -> str:
        self._ensure()
        return self._body

    @property
    def content_hash(self) -> str:
        self._ensure()
        return self._hash

    @property
    def size(self) -> int:
        try:
            return self.path.stat().st_size
        except Exception:  # noqa: BLE001
            return 0

    def summary(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "name_zh": self.name_zh,
            "category": self.category,
            "path": str(self.path),
            "size": self.size,
            "hash": self.content_hash,
        }


class SkillRegistry:
    """
    skill-registry.yaml 的依赖图。

    用途：让 depends_on / can_invoke 真正参与路由——
      · depends_on：被选中的技能，其前置技能也要生效（前置在前）；
      · can_invoke：某阶段要追加的技能，必须在上游技能许可的调用范围内，
        不在这张图里的技能不会被凭空塞进提示词。
    YAML 缺失或解析失败时退化为"无图"，不影响主流程。
    """

    def __init__(self, path: Path):
        self.path = path
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.loaded = False

    def load(self) -> "SkillRegistry":
        if self.loaded:
            return self
        self.loaded = True
        if not self.path.exists():
            logger.warning("未找到技能注册表: %s（路由退化为无依赖图）", self.path)
            return self
        try:
            import yaml  # 延迟导入：只在需要时依赖 PyYAML
        except Exception:  # noqa: BLE001
            logger.warning("缺少 PyYAML，无法解析技能注册表")
            return self
        try:
            data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("技能注册表解析失败: %s", exc)
            return self
        for item in data.get("skills", []) or []:
            sid = str(item.get("id") or "").strip()
            if not sid:
                continue
            self.nodes[sid] = {
                "id": sid,
                "name_zh": item.get("name_zh") or sid,
                "layer": item.get("layer") or "",
                "role": item.get("role") or "",
                "depends_on": [str(x) for x in (item.get("depends_on") or [])],
                "can_invoke": [str(x) for x in (item.get("can_invoke") or [])],
                "gate_authority": item.get("gate_authority") or "none",
                "status": item.get("status") or "active",
            }
        logger.debug("技能注册表载入 %d 个节点", len(self.nodes))
        return self

    def depends_on(self, skill_id: str) -> List[str]:
        return list(self.nodes.get(skill_id, {}).get("depends_on", []))

    def can_invoke(self, skill_id: str) -> List[str]:
        return list(self.nodes.get(skill_id, {}).get("can_invoke", []))

    def is_active(self, skill_id: str) -> bool:
        node = self.nodes.get(skill_id)
        return bool(node) and node.get("status") == "active"

    def closure_with_dependencies(self, skill_ids: Iterable[str]) -> List[str]:
        """按依赖顺序展开：前置技能排在被依赖技能之前（深度优先后序）"""
        self.load()
        ordered: List[str] = []
        seen: set = set()

        def visit(sid: str) -> None:
            if sid in seen:
                return
            seen.add(sid)
            for dep in self.depends_on(sid):
                if dep in self.nodes:
                    visit(dep)
            ordered.append(sid)

        for sid in skill_ids:
            visit(sid)
        return ordered

    def allowed_invocations(self, from_ids: Iterable[str]) -> set:
        """上游技能允许调用的下游技能集合"""
        self.load()
        allowed: set = set()
        for sid in from_ids:
            allowed.update(self.can_invoke(sid))
        return allowed


registry = SkillRegistry(SKILL_REGISTRY)


class SkillLoader:
    """技能索引与注入器"""

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._scanned = False

    # ------------------------------------------------------------- 扫描
    def scan(self, force: bool = False) -> Dict[str, Skill]:
        if self._scanned and not force:
            return self._skills
        self._skills = {}

        # part1
        if PART1_SKILLS.exists():
            for d in sorted(p for p in PART1_SKILLS.iterdir() if p.is_dir()):
                f = d / "SKILL.md"
                if f.exists():
                    self._skills[f"part1:{d.name}"] = Skill(f"part1:{d.name}", f)

        # part2（按分类目录）
        if PART2_SKILLS.exists():
            for cat in sorted(p for p in PART2_SKILLS.iterdir() if p.is_dir()):
                for d in sorted(p for p in cat.iterdir() if p.is_dir()):
                    f = d / "SKILL.md"
                    if f.exists():
                        self._skills[f"part2:{d.name}"] = Skill(f"part2:{d.name}", f)

        # part3 主技能
        if PART3_SKILL.exists():
            self._skills["part3:zotero-literature-review"] = Skill(
                "part3:zotero-literature-review", PART3_SKILL
            )

        # 期刊格式包中的章节技能
        if FORMATS_DIR.exists():
            for journal_dir in sorted(p for p in FORMATS_DIR.iterdir() if p.is_dir()):
                skills_root = None
                for cand in journal_dir.rglob("skills"):
                    if cand.is_dir():
                        skills_root = cand
                        break
                if not skills_root:
                    continue
                for d in sorted(p for p in skills_root.iterdir() if p.is_dir()):
                    f = d / "SKILL.md"
                    if f.exists():
                        self._skills[f"journal:{journal_dir.name}:{d.name}"] = Skill(
                            f"journal:{journal_dir.name}:{d.name}", f
                        )

        self._scanned = True
        logger.debug("技能索引完成：%d 个", len(self._skills))
        return self._skills

    @property
    def skills(self) -> Dict[str, Skill]:
        return self.scan()

    def get(self, skill_id: str) -> Optional[Skill]:
        return self.skills.get(skill_id)

    def count(self) -> int:
        return len(self.skills)

    def inventory(self) -> List[Dict[str, Any]]:
        return [s.summary() for s in self.skills.values()]

    # ------------------------------------------------------------- 路由
    def for_empirical(
        self,
        strategy: str = "",
        stage: str = "",
        include_output: bool = False,
    ) -> List[Skill]:
        """实证智能体：按识别策略 + 阶段选出应生效的技能"""
        picked: List[str] = list(EMPIRICAL_COMMON_SKILLS)
        strat = (strategy or "").lower()
        for sid in STRATEGY_TO_SKILL.get(strat, []):
            picked.append(sid)
        stage_skills: List[str] = []
        if stage in ("robustness", "diagnostics"):
            stage_skills += ["sensitivity-bounds", "placebo", "clustering"]
        if stage == "further":
            stage_skills += ["heterogeneity", "mechanism"]
        if include_output or stage == "output":
            stage_skills += OUTPUT_SKILLS

        # 依赖图：阶段技能的许可范围要按"前置链路"算，
        # 例如 clustering 由 baseline-regression 许可、placebo 由 robustness-router 许可，
        # 而它们都是被依赖链带进来的，不能只看直接选中的策略技能。
        if stage_skills:
            base_closure = registry.closure_with_dependencies(picked)
            allowed = registry.allowed_invocations(base_closure)
            filtered = [s for s in stage_skills if (not allowed) or s in allowed]
            dropped = [s for s in stage_skills if s not in filtered]
            if dropped:
                logger.debug("阶段技能 %s 不在 can_invoke 范围内，已跳过", dropped)
            picked += filtered

        # 依赖图：把被选中技能的前置技能补进来，且排在其前面
        ordered_ids = registry.closure_with_dependencies(picked)

        out: List[Skill] = []
        seen = set()
        for sid in ordered_ids:
            key = f"part2:{sid}"
            if key in seen:
                continue
            seen.add(key)
            sk = self.get(key)
            if sk:
                out.append(sk)
        return out

    def for_writing(
        self,
        journal: str = "",
        section: str = "",
        extra_sections: Optional[List[str]] = None,
    ) -> List[Skill]:
        """
        写作智能体：part3 主技能 + 目标期刊的对应章节技能。

        章节匹配用“前缀/后缀归一”而非精确 id，因为各家期刊包的目录名并不统一
        （er-introduction / ceq-abstract-english / cie-did-identification …）。
        """
        out: List[Skill] = []
        main = self.get("part3:zotero-literature-review")
        if main:
            out.append(main)

        prefix = f"journal:{journal}:"
        wanted = {"workflow", "style"}
        if section:
            wanted.add(section)
        for s in (extra_sections or []):
            wanted.add(s)
        # 展开别名：不同期刊包对同一章节的目录名不同
        accepted = set()
        for w in wanted:
            accepted.add(w)
            accepted.update(SECTION_ALIASES.get(w, ()))

        for sid, sk in self.skills.items():
            if not sid.startswith(prefix):
                continue
            dir_name = sid[len(prefix):]                # e.g. ceq-abstract-english
            suffix = dir_name.split("-", 1)[-1] if "-" in dir_name else dir_name
            if suffix in accepted or dir_name in accepted:
                out.append(sk)
        return out

    def for_literature(self) -> List[Skill]:
        out: List[Skill] = []
        main = self.get("part1:literature-search")
        if main:
            out.append(main)
        return out

    # ------------------------------------------------------------- 注入
    def compose_injection(
        self,
        skills: Iterable[Skill],
        heading: str = "生效技能规范",
        max_chars: int = 12000,
        min_per_skill: int = 2500,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        把技能正文拼装成可注入系统提示的文本。

        预算分配：先按 min_per_skill 给每个技能保底额度，剩余预算再按
        "先到先得"补齐。这样避免第一个大技能独占预算、后续技能被整体截断——
        那会让"改了后面的 SKILL.md 却看不到效果"。

        :return: (注入文本, 实际生效技能清单)
        """
        pool = []
        for sk in skills:
            body = sk.body.strip()
            if body:
                pool.append((sk, body))
        if not pool:
            return "", []

        # 第一轮：保底额度
        quota: List[int] = []
        remaining = max_chars
        for _sk, body in pool:
            q = min(min_per_skill, len(body), remaining)
            quota.append(q)
            remaining -= q

        # 第二轮：把剩余预算补给还没写满的技能
        for i, (_sk, body) in enumerate(pool):
            if remaining <= 0:
                break
            want = len(body) - quota[i]
            if want <= 0:
                continue
            add = min(want, remaining)
            quota[i] += add
            remaining -= add

        blocks: List[str] = []
        trace: List[Dict[str, Any]] = []
        for (sk, body), q in zip(pool, quota):
            if q <= 0:
                continue
            if len(body) > q:
                piece = body[: max(0, q - 40)] + "\n\n…（技能正文超出预算，已截断）"
            else:
                piece = body
            block = f"## 技能：{sk.name_zh}（{sk.skill_id}）\n\n{piece}"
            blocks.append(block)
            trace.append({
                "skill_id": sk.skill_id,
                "name_zh": sk.name_zh,
                "hash": sk.content_hash,
                "path": str(sk.path),
                "used_chars": len(block),
                "truncated": len(body) > q,
            })

        if not blocks:
            return "", []
        text = f"# {heading}\n\n以下技能规范在当前环节强制生效：\n\n" + "\n\n---\n\n".join(blocks)
        return text, trace


# 全局单例
skill_loader = SkillLoader()
