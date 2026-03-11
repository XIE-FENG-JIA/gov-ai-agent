"""政府 API 資料擷取模組。"""
from src.knowledge.fetchers.base import BaseFetcher, FetchResult, html_to_markdown
from src.knowledge.fetchers.constants import SOURCE_LEVEL_A, SOURCE_LEVEL_B
from src.knowledge.fetchers.law_fetcher import LawFetcher
from src.knowledge.fetchers.gazette_fetcher import GazetteFetcher
from src.knowledge.fetchers.opendata_fetcher import OpenDataFetcher
from src.knowledge.fetchers.npa_fetcher import NpaFetcher
from src.knowledge.fetchers.legislative_fetcher import LegislativeFetcher
from src.knowledge.fetchers.legislative_debate_fetcher import LegislativeDebateFetcher
from src.knowledge.fetchers.procurement_fetcher import ProcurementFetcher
from src.knowledge.fetchers.judicial_fetcher import JudicialFetcher
from src.knowledge.fetchers.interpretation_fetcher import InterpretationFetcher
from src.knowledge.fetchers.local_regulation_fetcher import LocalRegulationFetcher
from src.knowledge.fetchers.exam_yuan_fetcher import ExamYuanFetcher
from src.knowledge.fetchers.statistics_fetcher import StatisticsFetcher
from src.knowledge.fetchers.control_yuan_fetcher import ControlYuanFetcher

__all__ = [
    "BaseFetcher",
    "FetchResult",
    "html_to_markdown",
    "LawFetcher",
    "GazetteFetcher",
    "OpenDataFetcher",
    "NpaFetcher",
    "LegislativeFetcher",
    "LegislativeDebateFetcher",
    "ProcurementFetcher",
    "JudicialFetcher",
    "InterpretationFetcher",
    "LocalRegulationFetcher",
    "ExamYuanFetcher",
    "StatisticsFetcher",
    "ControlYuanFetcher",
    "SOURCE_LEVEL_A",
    "SOURCE_LEVEL_B",
]
