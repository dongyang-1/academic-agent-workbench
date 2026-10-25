# -*- coding: utf-8 -*-
"""数据搜集：把公开数据源拉成 DataFrame，交给工作台登记为可分析的数据集。

设计原则：
- 只用免 key、可直连的公开源（世界银行 API、akshare 中国宏观、任意 CSV 直链）；
- 每个源都容错：某个源报错不影响其它源，前端会显示具体原因；
- 返回统一的长表结构（country/series, date, value），便于后续做面板。
"""

from __future__ import annotations

import io
import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

import pandas as pd

_TIMEOUT = 25
_UA = {"User-Agent": "Mozilla/5.0 (compatible; ACA-DataCollector/1.0)"}

# ---------------------------------------------------------------- 指标目录
WORLD_BANK_INDICATORS = [
    {"id": "NY.GDP.MKTP.CD", "label": "GDP（现价美元）"},
    {"id": "NY.GDP.PCAP.CD", "label": "人均 GDP（现价美元）"},
    {"id": "SP.POP.TOTL", "label": "总人口"},
    {"id": "SP.URB.TOTL.IN.ZS", "label": "城镇化率（%）"},
    {"id": "GC.XPN.TOTL.GD.ZS", "label": "政府消费支出占 GDP（%）"},
    {"id": "NE.GDI.TOTL.ZS", "label": "资本形成总额占 GDP（%）"},
    {"id": "BX.KLT.DINV.CD.WD", "label": "外商直接投资净流入（美元）"},
    {"id": "GB.XPD.RSDV.GD.ZS", "label": "研发支出占 GDP（%）"},
]

AKSHARE_INDICATORS = [
    {"id": "macro_china_cpi_yearly", "label": "中国 CPI（年度同比）"},
    {"id": "macro_china_ppi_yearly", "label": "中国 PPI（年度同比）"},
    {"id": "macro_china_gdp_yearly", "label": "中国 GDP（年度）"},
    {"id": "macro_china_money_supply", "label": "中国货币供应量 M0/M1/M2"},
    {"id": "macro_china_shrzgm", "label": "中国社会融资规模"},
    {"id": "macro_china_fx_gold", "label": "中国外汇储备与黄金储备"},
]

COUNTRIES = [
    {"code": "CHN", "label": "中国"},
    {"code": "USA", "label": "美国"},
    {"code": "JPN", "label": "日本"},
    {"code": "DEU", "label": "德国"},
    {"code": "IND", "label": "印度"},
    {"code": "GBR", "label": "英国"},
]


def catalog() -> Dict[str, Any]:
    akshare_ok = True
    try:
        import akshare  # noqa: F401
    except Exception:
        akshare_ok = False
    return {
        "providers": [
            {
                "id": "worldbank",
                "label": "世界银行开放数据",
                "note": "跨国面板，免费无需 key，海外服务器",
                "indicators": WORLD_BANK_INDICATORS,
                "supports_country": True,
                "available": True,
            },
            {
                "id": "akshare",
                "label": "AKShare 中国宏观",
                "note": "国内宏观时间序列，需已安装 akshare",
                "indicators": AKSHARE_INDICATORS,
                "supports_country": False,
                "available": akshare_ok,
            },
            {
                "id": "csv_url",
                "label": "CSV 直链",
                "note": "给一个可下载的 CSV / TSV 链接，直接入库",
                "indicators": [{"id": "custom", "label": "自定义链接"}],
                "supports_country": False,
                "available": True,
            },
        ],
        "countries": COUNTRIES,
    }


# ---------------------------------------------------------------- 抓取实现
def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read()


def _fetch_worldbank(indicator: str, start: int, end: int, countries: List[str]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for code in countries:
        url = (
            f"https://api.worldbank.org/v2/country/{code}/indicator/{indicator}"
            f"?format=json&per_page=2000&date={start}:{end}"
        )
        payload = json.loads(_get(url).decode("utf-8", "ignore"))
        if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
            continue
        for item in payload[1]:
            if item.get("value") is None:
                continue
            rows.append({
                "country": code,
                "country_name": (item.get("country") or {}).get("value", code),
                "year": int(item["date"]),
                "indicator": indicator,
                "value": float(item["value"]),
            })
    if not rows:
        raise RuntimeError("世界银行没有返回数据（可能年份区间内无观测）")
    df = pd.DataFrame(rows).sort_values(["country", "year"]).reset_index(drop=True)
    return df


def _fetch_akshare(func_name: str) -> pd.DataFrame:
    try:
        import akshare as ak
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("未安装 akshare，无法使用该数据源（pip install akshare）") from exc

    fn = getattr(ak, func_name, None)
    if fn is None:
        raise RuntimeError(f"当前 akshare 版本没有 {func_name} 这个接口")
    df = fn()
    if df is None or len(df) == 0:
        raise RuntimeError("接口返回空表")
    # 统一列名首列/日期列，保留原始列
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _fetch_csv_url(url: str) -> pd.DataFrame:
    if not url or not url.lower().startswith(("http://", "https://")):
        raise RuntimeError("请填写以 http(s):// 开头的 CSV 直链")
    raw = _get(url)
    for enc in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    else:
        raise RuntimeError("无法识别文件编码")
    sep = "\t" if text.count("\t") > text.count(",") else ","
    df = pd.read_csv(io.StringIO(text), sep=sep)
    if df.empty:
        raise RuntimeError("链接内容为空表")
    return df


def collect(provider: str, indicator: str, start: int, end: int,
            countries: Optional[List[str]] = None, url: str = "") -> pd.DataFrame:
    if provider == "worldbank":
        codes = countries or ["CHN"]
        return _fetch_worldbank(indicator, start, end, codes)
    if provider == "akshare":
        return _fetch_akshare(indicator)
    if provider == "csv_url":
        return _fetch_csv_url(url)
    raise RuntimeError(f"未知数据源：{provider}")


def suggested_filename(provider: str, indicator: str) -> str:
    if provider == "worldbank":
        return f"worldbank_{indicator}"
    if provider == "akshare":
        return indicator
    return "custom_csv"
