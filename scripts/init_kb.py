#!/usr/bin/env python3
"""知識庫全量初始化腳本。

自動執行所有 fetcher（bulk 模式優先），將法規、公報、開放資料等
全量匯入 ChromaDB 知識庫，並執行驗證檢查。

用法：
    python scripts/init_kb.py                   # 完整初始化（fetch + ingest + 驗證）
    python scripts/init_kb.py --fetch-only       # 僅擷取，不匯入
    python scripts/init_kb.py --ingest-only      # 僅匯入已擷取的檔案
    python scripts/init_kb.py --validate-only    # 僅驗證現有知識庫
    python scripts/init_kb.py --reset            # 重設知識庫後重新匯入
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# 確保專案根目錄在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.core.config import ConfigManager
from src.core.llm import get_llm_factory
from src.knowledge.manager import KnowledgeBaseManager
from src.knowledge.fetchers.base import FetchResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("init_kb")

# ========== 驗證用的測試查詢 ==========
VALIDATION_QUERIES = [
    ("公文程式條例", "regulations"),
    ("行政程序法", "regulations"),
    ("行政院公報", "examples"),
    ("政府採購法", "regulations"),
    ("個人資料保護", "regulations"),
    ("勞動基準法", "regulations"),
    ("環境保護", "policies"),
    ("治安維護", "policies"),
    ("預算編列", "policies"),
    ("公務人員任用", "regulations"),
]


@dataclass
class PhaseResult:
    """單一階段的執行結果。"""
    name: str
    fetched: int = 0
    ingested: int = 0
    failed: int = 0
    elapsed_sec: float = 0.0
    error: str | None = None


@dataclass
class InitReport:
    """全量初始化報告。"""
    phases: list[PhaseResult] = field(default_factory=list)
    total_fetched: int = 0
    total_ingested: int = 0
    db_size_mb: float = 0.0
    search_hit_rate: float = 0.0
    embedding_consistent: bool = False
    validation_details: list[dict] = field(default_factory=list)


# ------------------------------------------------------------------
# 工具函式
# ------------------------------------------------------------------

def _init_kb() -> tuple[KnowledgeBaseManager, dict]:
    """初始化知識庫管理器，回傳 (kb, config)。"""
    config_manager = ConfigManager()
    config = config_manager.config
    llm_config = config.get("llm")
    if not llm_config:
        raise RuntimeError("設定檔缺少 'llm' 區塊，請檢查 config.yaml")
    llm = get_llm_factory(llm_config, full_config=config)
    kb_path = config.get("knowledge_base", {}).get("path", "./kb_data")
    kb = KnowledgeBaseManager(persist_path=kb_path, llm_provider=llm)
    return kb, config


def _parse_and_ingest(results: list[FetchResult], kb: KnowledgeBaseManager) -> tuple[int, int]:
    """解析 FetchResult 並匯入知識庫，回傳 (成功, 失敗)。"""
    from src.cli.kb import parse_markdown_with_metadata, _sanitize_metadata

    success = 0
    failed = 0
    for r in results:
        try:
            metadata, content = parse_markdown_with_metadata(r.file_path)
            clean = _sanitize_metadata(metadata)
            doc_id = kb.add_document(content, clean, collection_name=r.collection)
            if doc_id:
                success += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning("匯入失敗 %s: %s", r.file_path.name, e)
            failed += 1
    return success, failed


def _get_db_size_mb(kb_path: str) -> float:
    """計算知識庫目錄總大小（MB）。"""
    total = 0
    for root, dirs, files in os.walk(kb_path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total / (1024 * 1024)


# ------------------------------------------------------------------
# Phase 1: Fetch — 擷取所有來源
# ------------------------------------------------------------------

def phase_fetch_laws_bulk() -> PhaseResult:
    """Phase 1a: 全國法規資料庫（bulk XML 全量下載）。"""
    result = PhaseResult(name="法規 (bulk)")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.law_fetcher import LawFetcher
        # pcodes={} → 不篩選，下載全部法規
        fetcher = LawFetcher(
            output_dir=Path("kb_data/regulations/laws"),
            pcodes={},
            rate_limit=0.5,
        )
        logger.info("開始從全國法規資料庫 bulk 下載...")
        results = fetcher.fetch_bulk()
        result.fetched = len(results)
        logger.info("法規 bulk 擷取完成：%d 個檔案", len(results))
    except Exception as e:
        result.error = str(e)
        logger.error("法規 bulk 擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_laws_default() -> PhaseResult:
    """Phase 1a-fallback: 擷取預設法規清單（若 bulk 失敗可用此替代）。"""
    result = PhaseResult(name="法規 (預設清單)")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.law_fetcher import LawFetcher
        from src.knowledge.fetchers.constants import DEFAULT_LAW_PCODES
        fetcher = LawFetcher(
            output_dir=Path("kb_data/regulations/laws"),
            pcodes=DEFAULT_LAW_PCODES,
            rate_limit=1.0,
        )
        logger.info("開始擷取 %d 部預設法規...", len(DEFAULT_LAW_PCODES))
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("預設法規擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_gazette_bulk() -> PhaseResult:
    """Phase 1b: 行政院公報（bulk ZIP 下載）。"""
    result = PhaseResult(name="公報 (bulk)")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher
        fetcher = GazetteFetcher(
            output_dir=Path("kb_data/examples/gazette"),
            days=365,  # 取近一年
            rate_limit=0.5,
        )
        logger.info("開始從行政院公報 bulk 下載...")
        results = fetcher.fetch_bulk(extract_pdf=False)  # 跳過 PDF 加速
        result.fetched = len(results)
        logger.info("公報 bulk 擷取完成：%d 個檔案", len(results))
    except Exception as e:
        result.error = str(e)
        logger.error("公報 bulk 擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_gazette_default() -> PhaseResult:
    """Phase 1b-fallback: 行政院公報（XML API，近 90 天）。"""
    result = PhaseResult(name="公報 (API 90天)")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher
        fetcher = GazetteFetcher(
            output_dir=Path("kb_data/examples/gazette"),
            days=90,
            rate_limit=1.0,
        )
        logger.info("開始擷取近 90 天公報...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("公報 API 擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_opendata() -> PhaseResult:
    """Phase 1c: 政府資料開放平臺。"""
    result = PhaseResult(name="開放資料")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher
        keywords = ["警政署", "環保署", "勞動部", "衛福部", "教育部", "財政部", "交通部"]
        all_results: list[FetchResult] = []
        for kw in keywords:
            fetcher = OpenDataFetcher(
                output_dir=Path("kb_data/policies/opendata"),
                keyword=kw,
                limit=50,
            )
            logger.info("搜尋開放資料：%s", kw)
            all_results.extend(fetcher.fetch())
        result.fetched = len(all_results)
    except Exception as e:
        result.error = str(e)
        logger.error("開放資料擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_npa() -> PhaseResult:
    """Phase 1d: 警政署 OPEN DATA。"""
    result = PhaseResult(name="警政署")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.npa_fetcher import NpaFetcher
        fetcher = NpaFetcher(output_dir=Path("kb_data/policies/npa"))
        logger.info("開始擷取警政署資料...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("警政署擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_interpretations() -> PhaseResult:
    """Phase 1e: 法務部行政函釋。"""
    result = PhaseResult(name="行政函釋")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher
        fetcher = InterpretationFetcher(
            output_dir=Path("kb_data/regulations/interpretations"),
            limit=100,
        )
        logger.info("開始擷取行政函釋...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("行政函釋擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_judicial() -> PhaseResult:
    """Phase 1f: 司法院裁判書。"""
    result = PhaseResult(name="裁判書")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.judicial_fetcher import JudicialFetcher
        fetcher = JudicialFetcher(
            output_dir=Path("kb_data/regulations/judicial"),
            limit=50,
        )
        logger.info("開始擷取裁判書...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("裁判書擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_local() -> PhaseResult:
    """Phase 1g: 地方自治法規。"""
    result = PhaseResult(name="地方法規")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.local_regulation_fetcher import LocalRegulationFetcher
        fetcher = LocalRegulationFetcher(
            output_dir=Path("kb_data/regulations/local"),
            city="taipei",
            limit=50,
        )
        logger.info("開始擷取地方法規...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("地方法規擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_examyuan() -> PhaseResult:
    """Phase 1h: 考試院法規。"""
    result = PhaseResult(name="考試院法規")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.exam_yuan_fetcher import ExamYuanFetcher
        fetcher = ExamYuanFetcher(
            output_dir=Path("kb_data/regulations/exam_yuan"),
            limit=50,
        )
        logger.info("開始擷取考試院法規...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("考試院法規擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_legislative() -> PhaseResult:
    """Phase 1i: 立法院議案。"""
    result = PhaseResult(name="立法院議案")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.legislative_fetcher import LegislativeFetcher
        fetcher = LegislativeFetcher(
            output_dir=Path("kb_data/policies/legislative"),
            term="all",
            limit=100,
        )
        logger.info("開始擷取立法院議案...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("立法院議案擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_debates() -> PhaseResult:
    """Phase 1j: 立法院質詢紀錄。"""
    result = PhaseResult(name="質詢紀錄")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.legislative_debate_fetcher import LegislativeDebateFetcher
        fetcher = LegislativeDebateFetcher(
            output_dir=Path("kb_data/policies/legislative_debates"),
            limit=50,
        )
        logger.info("開始擷取質詢紀錄...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("質詢紀錄擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_procurement() -> PhaseResult:
    """Phase 1k: 政府採購公告。"""
    result = PhaseResult(name="採購公告")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.procurement_fetcher import ProcurementFetcher
        fetcher = ProcurementFetcher(
            output_dir=Path("kb_data/policies/procurement"),
            days=90,
            limit=100,
        )
        logger.info("開始擷取採購公告...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("採購公告擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_statistics() -> PhaseResult:
    """Phase 1l: 主計總處統計。"""
    result = PhaseResult(name="統計通報")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.statistics_fetcher import StatisticsFetcher
        fetcher = StatisticsFetcher(
            output_dir=Path("kb_data/policies/statistics"),
            limit=30,
        )
        logger.info("開始擷取統計通報...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("統計通報擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


def phase_fetch_controlyuan() -> PhaseResult:
    """Phase 1m: 監察院糾正案。"""
    result = PhaseResult(name="監察院")
    t0 = time.time()
    try:
        from src.knowledge.fetchers.control_yuan_fetcher import ControlYuanFetcher
        fetcher = ControlYuanFetcher(
            output_dir=Path("kb_data/policies/control_yuan"),
            limit=30,
        )
        logger.info("開始擷取監察院糾正案...")
        results = fetcher.fetch()
        result.fetched = len(results)
    except Exception as e:
        result.error = str(e)
        logger.error("監察院擷取失敗：%s", e)
    result.elapsed_sec = time.time() - t0
    return result


# ------------------------------------------------------------------
# Phase 2: Ingest — 將已擷取的 Markdown 匯入 ChromaDB
# ------------------------------------------------------------------

def phase_ingest_all(kb: KnowledgeBaseManager, reset: bool = False) -> list[PhaseResult]:
    """掃描 kb_data 下所有 Markdown 並匯入知識庫。"""
    if reset:
        logger.info("正在重設知識庫...")
        kb.reset_db()

    from src.cli.kb import parse_markdown_with_metadata, _sanitize_metadata

    # 目錄 → 集合名稱 對照表
    dir_collection_map = {
        "examples": "examples",
        "regulations": "regulations",
        "policies": "policies",
    }

    results: list[PhaseResult] = []
    kb_path = Path(kb.persist_path)

    for subdir_name, collection in dir_collection_map.items():
        subdir = kb_path / subdir_name
        if not subdir.exists():
            continue

        phase = PhaseResult(name=f"ingest:{subdir_name}")
        t0 = time.time()

        md_files = list(subdir.rglob("*.md"))
        logger.info("匯入 %s：找到 %d 個 Markdown 檔案", subdir_name, len(md_files))

        for i, fp in enumerate(md_files, 1):
            try:
                metadata, content = parse_markdown_with_metadata(fp)
                if not content or not content.strip():
                    continue
                if metadata.get("deprecated"):
                    continue
                if "title" not in metadata:
                    metadata["title"] = fp.stem
                if "doc_type" not in metadata:
                    metadata["doc_type"] = "unknown"
                clean = _sanitize_metadata(metadata)
                doc_id = kb.add_document(content, clean, collection_name=collection)
                if doc_id:
                    phase.ingested += 1
                else:
                    phase.failed += 1
            except Exception as e:
                logger.warning("匯入 %s 失敗：%s", fp.name, e)
                phase.failed += 1

            # 每 100 筆顯示進度
            if i % 100 == 0:
                logger.info("  %s 進度：%d/%d", subdir_name, i, len(md_files))

        phase.elapsed_sec = time.time() - t0
        results.append(phase)
        logger.info(
            "%s 匯入完成：成功 %d / 失敗 %d（耗時 %.1f 秒）",
            subdir_name, phase.ingested, phase.failed, phase.elapsed_sec,
        )

    return results


# ------------------------------------------------------------------
# Phase 3: Validate — 驗證知識庫品質
# ------------------------------------------------------------------

def phase_validate(kb: KnowledgeBaseManager) -> dict:
    """驗證知識庫品質，回傳驗證結果。"""
    validation = {
        "stats": {},
        "db_size_mb": 0.0,
        "search_hit_rate": 0.0,
        "embedding_consistent": False,
        "details": [],
    }

    # 3.1 統計
    stats = kb.get_stats()
    validation["stats"] = stats
    total_docs = sum(stats.values())
    logger.info("知識庫統計：%s（共 %d 筆）", stats, total_docs)

    # 3.2 DB 大小
    db_size = _get_db_size_mb(kb.persist_path)
    validation["db_size_mb"] = db_size
    logger.info("知識庫大小：%.2f MB", db_size)

    # 3.3 搜尋命中率測試
    hits = 0
    total_queries = len(VALIDATION_QUERIES)
    for query, expected_collection in VALIDATION_QUERIES:
        try:
            results = kb.search_hybrid(query, n_results=3)
            if results and len(results) > 0:
                hits += 1
                top = results[0]
                distance = top.get("distance", 1.0)
                title = top.get("metadata", {}).get("title", "?")
                validation["details"].append({
                    "query": query,
                    "hit": True,
                    "top_title": title,
                    "distance": distance,
                })
                logger.info(
                    "  搜尋 '%s' → 命中 '%s'（距離 %.3f）",
                    query, title, distance,
                )
            else:
                validation["details"].append({
                    "query": query,
                    "hit": False,
                })
                logger.warning("  搜尋 '%s' → 無結果", query)
        except Exception as e:
            validation["details"].append({
                "query": query,
                "hit": False,
                "error": str(e),
            })
            logger.warning("  搜尋 '%s' 失敗：%s", query, e)

    hit_rate = hits / total_queries if total_queries > 0 else 0
    validation["search_hit_rate"] = hit_rate
    logger.info("搜尋命中率：%.0f%%（%d/%d）", hit_rate * 100, hits, total_queries)

    # 3.4 Embedding 一致性測試
    # 驗證 ingest 和 query 使用相同的 embedding 模型
    try:
        test_text = "行政程序法第一條"
        emb1 = kb.llm_provider.embed(test_text)
        emb2 = kb.llm_provider.embed(test_text)
        if emb1 and emb2 and len(emb1) == len(emb2):
            # 計算兩次 embedding 的餘弦相似度
            dot = sum(a * b for a, b in zip(emb1, emb2))
            norm1 = sum(a * a for a in emb1) ** 0.5
            norm2 = sum(b * b for b in emb2) ** 0.5
            if norm1 > 0 and norm2 > 0:
                cos_sim = dot / (norm1 * norm2)
                # 相同模型、相同輸入的 embedding 應該完全一致（或極接近）
                validation["embedding_consistent"] = cos_sim > 0.99
                logger.info(
                    "Embedding 一致性：cosine=%.6f（%s）",
                    cos_sim,
                    "通過" if cos_sim > 0.99 else "不一致！",
                )
    except Exception as e:
        logger.warning("Embedding 一致性測試失敗：%s", e)

    return validation


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------

def run_full_init(
    *,
    fetch: bool = True,
    ingest: bool = True,
    validate: bool = True,
    reset: bool = False,
) -> InitReport:
    """執行完整初始化流程。"""
    report = InitReport()
    t_start = time.time()

    # Phase 1: Fetch
    if fetch:
        logger.info("=" * 60)
        logger.info("Phase 1: 擷取資料")
        logger.info("=" * 60)

        fetch_phases = [
            ("法規 bulk", phase_fetch_laws_bulk),
            ("公報 bulk", phase_fetch_gazette_bulk),
            ("開放資料", phase_fetch_opendata),
            ("警政署", phase_fetch_npa),
            ("行政函釋", phase_fetch_interpretations),
            ("裁判書", phase_fetch_judicial),
            ("地方法規", phase_fetch_local),
            ("考試院", phase_fetch_examyuan),
            ("立法院議案", phase_fetch_legislative),
            ("質詢紀錄", phase_fetch_debates),
            ("採購公告", phase_fetch_procurement),
            ("統計通報", phase_fetch_statistics),
            ("監察院", phase_fetch_controlyuan),
        ]

        for name, fn in fetch_phases:
            logger.info("-" * 40)
            logger.info("擷取：%s", name)
            result = fn()
            report.phases.append(result)
            report.total_fetched += result.fetched
            if result.error:
                logger.warning("  %s 失敗：%s", name, result.error)
            else:
                logger.info(
                    "  %s 完成：%d 筆（%.1f 秒）",
                    name, result.fetched, result.elapsed_sec,
                )

        # 若 bulk 法規擷取為 0，fallback 到預設清單
        laws_phase = report.phases[0]
        if laws_phase.fetched == 0:
            logger.info("法規 bulk 無結果，嘗試預設法規清單 fallback...")
            fallback = phase_fetch_laws_default()
            report.phases.append(fallback)
            report.total_fetched += fallback.fetched

        # 若 bulk 公報擷取為 0，fallback 到 API
        gazette_phase = report.phases[1]
        if gazette_phase.fetched == 0:
            logger.info("公報 bulk 無結果，嘗試 API fallback...")
            fallback = phase_fetch_gazette_default()
            report.phases.append(fallback)
            report.total_fetched += fallback.fetched

        logger.info("Phase 1 小結：共擷取 %d 個檔案", report.total_fetched)

    # Phase 2: Ingest
    if ingest:
        logger.info("=" * 60)
        logger.info("Phase 2: 匯入知識庫")
        logger.info("=" * 60)

        kb, config = _init_kb()
        ingest_results = phase_ingest_all(kb, reset=reset)
        for ir in ingest_results:
            report.phases.append(ir)
            report.total_ingested += ir.ingested

        logger.info("Phase 2 小結：共匯入 %d 筆", report.total_ingested)

    # Phase 3: Validate
    if validate:
        logger.info("=" * 60)
        logger.info("Phase 3: 驗證知識庫")
        logger.info("=" * 60)

        if not ingest:
            kb, config = _init_kb()

        v = phase_validate(kb)
        report.db_size_mb = v["db_size_mb"]
        report.search_hit_rate = v["search_hit_rate"]
        report.embedding_consistent = v["embedding_consistent"]
        report.validation_details = v["details"]

    # 總結報告
    elapsed_total = time.time() - t_start
    logger.info("=" * 60)
    logger.info("初始化完成（總耗時 %.1f 秒）", elapsed_total)
    logger.info("  擷取檔案數：%d", report.total_fetched)
    logger.info("  匯入文件數：%d", report.total_ingested)
    logger.info("  知識庫大小：%.2f MB", report.db_size_mb)
    logger.info("  搜尋命中率：%.0f%%", report.search_hit_rate * 100)
    logger.info("  Embedding 一致性：%s", "通過" if report.embedding_consistent else "未通過/未測試")
    logger.info("=" * 60)

    # 寫出報告 JSON
    report_path = PROJECT_ROOT / "kb_init_report.json"
    report_dict = {
        "total_fetched": report.total_fetched,
        "total_ingested": report.total_ingested,
        "db_size_mb": report.db_size_mb,
        "search_hit_rate": report.search_hit_rate,
        "embedding_consistent": report.embedding_consistent,
        "phases": [
            {
                "name": p.name,
                "fetched": p.fetched,
                "ingested": p.ingested,
                "failed": p.failed,
                "elapsed_sec": round(p.elapsed_sec, 1),
                "error": p.error,
            }
            for p in report.phases
        ],
        "validation_details": report.validation_details,
    }
    report_path.write_text(
        json.dumps(report_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("報告已寫入：%s", report_path)

    return report


def main():
    parser = argparse.ArgumentParser(
        description="知識庫全量初始化腳本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--fetch-only", action="store_true", help="僅擷取，不匯入")
    parser.add_argument("--ingest-only", action="store_true", help="僅匯入已擷取的檔案")
    parser.add_argument("--validate-only", action="store_true", help="僅驗證現有知識庫")
    parser.add_argument("--reset", action="store_true", help="重設知識庫後重新匯入")

    args = parser.parse_args()

    if args.fetch_only:
        run_full_init(fetch=True, ingest=False, validate=False)
    elif args.ingest_only:
        run_full_init(fetch=False, ingest=True, validate=True, reset=args.reset)
    elif args.validate_only:
        run_full_init(fetch=False, ingest=False, validate=True)
    else:
        run_full_init(fetch=True, ingest=True, validate=True, reset=args.reset)


if __name__ == "__main__":
    main()
