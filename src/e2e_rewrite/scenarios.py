from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RewriteScenario:
    slug: str
    user_input: str
    requirement: dict[str, Any]
    source_ids: tuple[str, ...]


SCENARIOS: tuple[RewriteScenario, ...] = (
    RewriteScenario(
        slug="han",
        user_input=(
            "請寫一份函，臺北市政府教育局發給各市立國民中學，"
            "主旨是辦理114年度校園資源回收宣導，並請各校於114年6月15日前回報成果。"
        ),
        requirement={
            "doc_type": "函",
            "urgency": "普通",
            "sender": "臺北市政府教育局",
            "receiver": "臺北市各市立國民中學",
            "subject": "有關辦理114年度校園資源回收宣導一案，請查照。",
            "reason": "為強化校園環境教育與資源回收執行成效。",
            "action_items": [
                "請於114年5月30日前完成校內宣導規劃",
                "請於114年6月15日前回報執行情形",
            ],
            "attachments": ["校園資源回收宣導表"],
        },
        source_ids=("A0000001", "162455"),
    ),
    RewriteScenario(
        slug="announcement",
        user_input=(
            "請寫一份公告，臺北市政府環境保護局公告114年端午節垃圾清運時間調整，"
            "並提醒市民依公告時段排出垃圾。"
        ),
        requirement={
            "doc_type": "公告",
            "urgency": "普通",
            "sender": "臺北市政府環境保護局",
            "receiver": "全體市民",
            "subject": "公告114年端午節期間垃圾清運時間調整事項。",
            "reason": "為維持節慶期間市容整潔並便利市民配合清運作業。",
            "action_items": [
                "114年6月8日停止夜間清運",
                "114年6月9日恢復正常清運",
            ],
            "attachments": ["端午節垃圾清運時程表"],
        },
        source_ids=("A0000002", "173524"),
    ),
    RewriteScenario(
        slug="sign",
        user_input=(
            "請寫一份簽，臺北市政府環境保護局要向局長簽報辦理114年度環保志工表揚活動，"
            "預算新臺幣30萬元，擬於114年8月15日舉行。"
        ),
        requirement={
            "doc_type": "簽",
            "urgency": "速件",
            "sender": "臺北市政府環境保護局",
            "receiver": "局長",
            "subject": "擬辦理114年度環保志工表揚活動一案，簽請核示。",
            "reason": "為肯定志工服務績效並強化環境保護政策推廣。",
            "action_items": [
                "活動日期定於114年8月15日",
                "所需經費新臺幣30萬元由相關預算支應",
            ],
            "attachments": ["活動規劃書", "經費概算表"],
        },
        source_ids=("A0000001", "30790"),
    ),
    RewriteScenario(
        slug="decree",
        user_input=(
            "請寫一份令，行政院命各部會於114年7月1日起配合重大緊急應變演練，"
            "並依規定完成內部通報機制整備。"
        ),
        requirement={
            "doc_type": "令",
            "urgency": "最速件",
            "sender": "行政院",
            "receiver": "各部會",
            "subject": "自114年7月1日起實施重大緊急應變演練整備事項。",
            "reason": "為強化跨機關緊急應變與通報協作機制。",
            "action_items": [
                "自114年7月1日起實施演練整備",
                "各部會應完成內部通報流程盤點",
            ],
            "attachments": ["演練整備重點表"],
        },
        source_ids=("A0000003", "5c4c4e1c-9f4f-4b75-a7d3-30be59522441"),
    ),
    RewriteScenario(
        slug="meeting-notice",
        user_input=(
            "請寫一份開會通知單，數位發展部邀集各部會在114年9月12日上午10時開會，"
            "討論跨機關資安聯防機制與演練分工。"
        ),
        requirement={
            "doc_type": "開會通知單",
            "urgency": "普通",
            "sender": "數位發展部",
            "receiver": "各部會資安聯絡窗口",
            "subject": "召開114年度跨機關資安聯防協調會議，請查照。",
            "reason": "為整合跨機關資安聯防機制與演練分工。",
            "action_items": [
                "114年9月12日上午10時出席會議",
                "會前彙整機關資安演練需求",
            ],
            "attachments": ["會議議程"],
        },
        source_ids=("A0000002", "6d5edda8-43b5-4e9a-84f8-c57798989ad0"),
    ),
)
