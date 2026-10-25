# -*- coding: utf-8 -*-
"""
学术全流程可视化 Skills 管理模块
提供三大板块（Part 1 文献检索、Part 2 因果实证 28 个技能、Part 3 文献综述与写作）的：
1. 树状层级扫描与元数据解析
2. 在线内容读取与修改保存
3. 原始版本自动镜像与一键安全重置 (Reset to Default)
4. 新 Skill 上传与注入
"""

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SkillsManager")

INTEGRATED_ROOT = Path(__file__).resolve().parents[1]
PART1_SKILLS = INTEGRATED_ROOT / "part1-paper" / "skills"
PART2_SKILLS = INTEGRATED_ROOT / "part2-empirical-research" / "skills"
PART3_SKILLS = INTEGRATED_ROOT / "part3-文献综述" / "zotero-literature-review"

BACKUP_DIR = INTEGRATED_ROOT / "_skills_backup"


class SkillsManager:
    """技能可视化管理器"""

    def __init__(self):
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_initial_backup()

    def _ensure_initial_backup(self):
        """若尚未做过初始备份，自动为原始技能制作出厂快照"""
        marker_file = self.backup_dir / ".initial_backup_done"
        if not marker_file.exists():
            try:
                if PART1_SKILLS.exists():
                    shutil.copytree(PART1_SKILLS, self.backup_dir / "part1_skills", dirs_exist_ok=True)
                if PART2_SKILLS.exists():
                    shutil.copytree(PART2_SKILLS, self.backup_dir / "part2_skills", dirs_exist_ok=True)
                if PART3_SKILLS.exists():
                    shutil.copytree(PART3_SKILLS, self.backup_dir / "part3_skills", dirs_exist_ok=True)
                with open(marker_file, "w", encoding="utf-8") as f:
                    f.write("backed_up")
                logger.info("已成功为全套内置 Skills 创建初始出厂快照。")
            except Exception as e:
                logger.warning("初始备份出现异常: %s", e)

    def scan_all_skills(self) -> Dict[str, Any]:
        """
        扫描三大板块的所有技能并返回结构化树
        """
        categories = []

        # 1. Part 1 文献检索
        p1_items = []
        if PART1_SKILLS.exists():
            for p in sorted(PART1_SKILLS.iterdir()):
                if p.is_dir() and (p / "SKILL.md").exists():
                    p1_items.append({
                        "id": f"part1:{p.name}",
                        "name": p.name,
                        "display_name": "多源学术文献智能检索协议",
                        "path": str(p / "SKILL.md"),
                        "part": "part1",
                        "size": (p / "SKILL.md").stat().st_size,
                    })
        categories.append({
            "category_id": "part1",
            "category_name": "Part 1 · 文献检索与定级",
            "skills": p1_items,
        })

        # 2. Part 2 实证分析 28 个技能体系
        p2_categories = [
            ("00_router", "全局路由与决策 (Router)"),
            ("01_data", "数据采集与审计 (Data Acquisition & Audit)"),
            ("02_model", "基准回归估计 (Baseline Regression)"),
            ("03_identification", "11大核心因果识别策略 (DID / IV / RDD / SCM 等)"),
            ("04_robustness", "稳健性与敏感性边界 (HonestDiD / Placebo)"),
            ("05_further-analysis", "机制检验与异质性分析 (Mechanism & Heterogeneity)"),
            ("06_diagnostics", "计量审稿人状态机 (Reviewer Gate)"),
            ("07_replication", "可复现性归档与代码封装 (Replication Package)"),
            ("08_output", "出版级三线表与矢量图导出 (Tables & Figures)"),
        ]

        for folder_name, cat_title in p2_categories:
            folder_path = PART2_SKILLS / folder_name
            skills_in_cat = []
            if folder_path.exists():
                for sub in sorted(folder_path.iterdir()):
                    skill_file = sub / "SKILL.md" if sub.is_dir() else None
                    if skill_file and skill_file.exists():
                        skills_in_cat.append({
                            "id": f"part2:{folder_name}:{sub.name}",
                            "name": sub.name,
                            "display_name": sub.name,
                            "path": str(skill_file),
                            "part": "part2",
                            "folder": folder_name,
                            "size": skill_file.stat().st_size,
                        })
            if skills_in_cat:
                categories.append({
                    "category_id": f"part2_{folder_name}",
                    "category_name": f"Part 2 · {cat_title}",
                    "skills": skills_in_cat,
                })

        # 3. Part 3 文献综述与全文写作
        p3_items = []
        if PART3_SKILLS.exists() and (PART3_SKILLS / "SKILL.md").exists():
            p3_items.append({
                "id": "part3:zotero-literature-review",
                "name": "zotero-literature-review",
                "display_name": "Zotero 综述溯源与期刊级论文全文写作规范",
                "path": str(PART3_SKILLS / "SKILL.md"),
                "part": "part3",
                "size": (PART3_SKILLS / "SKILL.md").stat().st_size,
            })
        categories.append({
            "category_id": "part3",
            "category_name": "Part 3 · 文献综述与全文写作",
            "skills": p3_items,
        })

        # 4. 期刊格式技能（六刊的章节写作规范，随 formats 目录自动扩展）
        fmt_root = INTEGRATED_ROOT / "part3-文献综述" / "formats"
        if fmt_root.exists():
            for jdir in sorted(p for p in fmt_root.iterdir() if p.is_dir()):
                journal_title = jdir.name
                entries = []
                for skill_file in sorted(jdir.rglob("SKILL.md")):
                    entries.append({
                        "id": f"journal:{journal_title}:{skill_file.parent.name}",
                        "name": skill_file.parent.name,
                        "display_name": skill_file.parent.name,
                        "path": str(skill_file),
                        "part": "journal",
                        "folder": journal_title,
                        "size": skill_file.stat().st_size,
                    })
                if entries:
                    categories.append({
                        "category_id": f"journal_{journal_title}",
                        "category_name": f"期刊格式 · {journal_title}（{len(entries)} 个章节技能）",
                        "skills": entries,
                    })

        # ---- 归并成三大部分，避免面板里平铺十几个分类 ----
        PART_META = {
            "part1": {"name": "Part 1 · 文献检索与定级", "order": 1},
            "part2": {"name": "Part 2 · 因果实证与计量", "order": 2},
            "part3": {"name": "Part 3 · 综述、写作与期刊格式", "order": 3},
        }

        def _part_key(cat_id: str) -> str:
            if cat_id.startswith("part1"):
                return "part1"
            if cat_id.startswith("part2"):
                return "part2"
            return "part3"   # part3 与 journal_* 都归到第三部分

        def _group_name(cat_id: str, cat_name: str) -> str:
            # 去掉旧的 "Part x: " 前缀，只保留组名
            name = cat_name
            for prefix in ("Part 1 · ", "Part 2 · ", "Part 3 · ", "Part 1: ", "Part 2: ", "Part 3: "):
                if name.startswith(prefix):
                    name = name[len(prefix):]
                    break
            if cat_id.startswith("journal_"):
                name = name.replace("期刊格式 · ", "")
                name = re.sub(r"（\d+ 个章节技能）", "", name).strip()
                name = "期刊格式 · " + name
            if cat_id == "part1":
                name = "检索协议与期刊定级"
            return name.strip()

        buckets = {"part1": [], "part2": [], "part3": []}
        for cat in categories:
            key = _part_key(cat["category_id"])
            if not cat.get("skills"):
                continue
            buckets[key].append({
                "id": cat["category_id"],
                "name": _group_name(cat["category_id"], cat["category_name"]),
                "count": len(cat["skills"]),
                "skills": cat["skills"],
            })

        parts = []
        for key in ("part1", "part2", "part3"):
            groups = buckets[key]
            if not groups:
                continue
            parts.append({
                "id": key,
                "name": PART_META[key]["name"],
                "count": sum(g["count"] for g in groups),
                "groups": groups,
            })

        return {"parts": parts, "total": sum(p["count"] for p in parts)}

    def get_skill_content(self, file_path: str) -> str:
        """获取指定 Skill 文件的内容"""
        target = Path(file_path)
        if not target.exists():
            raise FileNotFoundError(f"未找到技能文件: {file_path}")
        with open(target, "r", encoding="utf-8") as f:
            return f.read()

    def update_skill_content(self, file_path: str, new_content: str) -> bool:
        """修改保存指定 Skill 内容"""
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(new_content)
        logger.info("已成功保存修改后的 Skill: %s", file_path)
        return True

    def reset_skill_to_default(self, skill_id: str, file_path: str) -> str:
        """一键重置特定技能为默认出厂设置"""
        target = Path(file_path)
        
        # 根据技能归属寻找快照
        parts = skill_id.split(":")
        source_part = parts[0]
        backup_candidate = None

        if source_part == "part1":
            backup_candidate = self.backup_dir / "part1_skills" / parts[1] / "SKILL.md"
        elif source_part == "part2":
            backup_candidate = self.backup_dir / "part2_skills" / parts[1] / parts[2] / "SKILL.md"
        elif source_part == "part3":
            backup_candidate = self.backup_dir / "part3_skills" / "SKILL.md"

        if backup_candidate and backup_candidate.exists():
            with open(backup_candidate, "r", encoding="utf-8") as f:
                default_content = f.read()
            with open(target, "w", encoding="utf-8") as f:
                f.write(default_content)
            logger.info("技能已恢复至出厂默认版本: %s", skill_id)
            return default_content
        else:
            raise FileNotFoundError("未找到该技能的出厂备份镜像。")

    def upload_new_skill(self, category_folder: str, skill_name: str, content: str) -> str:
        """上传或新建一个自定义 Skill"""
        safe_name = skill_name.strip().replace(" ", "_")
        dest_dir = PART2_SKILLS / category_folder / safe_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        skill_file = dest_dir / "SKILL.md"
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("已成功创建并注入新 Skill: %s", skill_file)
        return str(skill_file)


# 全局单例
skills_manager = SkillsManager()
