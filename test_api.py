#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""API 測試腳本"""

import requests

BASE_URL = "http://localhost:8000/api/v1"

def test_requirement():
    print("=" * 50)
    print("測試 1: 需求分析 Agent")
    print("=" * 50)

    resp = requests.post(f"{BASE_URL}/agent/requirement", json={
        "user_input": "幫我寫一份函，台北市環保局發給各學校，關於加強資源回收"
    })
    result = resp.json()

    print(f"成功: {result['success']}")
    if result['requirement']:
        req = result['requirement']
        print(f"公文類型: {req['doc_type']}")
        print(f"發文機關: {req['sender']}")
        print(f"受文者: {req['receiver']}")
        print(f"主旨: {req['subject']}")

    return result['requirement']

def test_writer(requirement):
    print("\n" + "=" * 50)
    print("測試 2: 撰寫 Agent")
    print("=" * 50)

    resp = requests.post(f"{BASE_URL}/agent/writer", json={
        "requirement": requirement
    })
    result = resp.json()

    print(f"成功: {result['success']}")
    if result['formatted_draft']:
        draft = result['formatted_draft']
        print(f"草稿長度: {len(draft)} 字元")
        print("\n--- 草稿預覽 (前 800 字) ---")
        print(draft[:800])

    return result['formatted_draft']

def test_parallel_review(draft, doc_type="函"):
    print("\n" + "=" * 50)
    print("測試 3: 並行審查 Agent")
    print("=" * 50)

    resp = requests.post(f"{BASE_URL}/agent/review/parallel", json={
        "draft": draft,
        "doc_type": doc_type,
        "agents": ["format", "style", "fact", "consistency", "compliance"]
    })
    result = resp.json()

    print(f"成功: {result['success']}")
    print(f"綜合分數: {result['aggregated_score']}")
    print(f"風險等級: {result['risk_summary']}")

    print("\n各 Agent 結果:")
    for name, res in result['results'].items():
        issues_count = len(res['issues'])
        print(f"  - {name}: 分數 {res['score']:.2f}, 問題數 {issues_count}")

    return result

def test_full_meeting():
    print("\n" + "=" * 50)
    print("測試 4: 完整開會流程")
    print("=" * 50)

    resp = requests.post(f"{BASE_URL}/meeting", json={
        "user_input": "幫我寫一份公告，臺北市政府要公告垃圾清運時間調整，從明年一月起每週二、四改為週一、三、五",
        "max_rounds": 2,
        "skip_review": False,
        "output_docx": False
    })
    result = resp.json()

    print(f"成功: {result['success']}")
    print(f"Session ID: {result['session_id']}")
    print(f"審查輪數: {result['rounds_used']}")

    if result['qa_report']:
        print(f"最終風險: {result['qa_report']['risk_summary']}")
        print(f"最終分數: {result['qa_report']['overall_score']:.2f}")

    if result['final_draft']:
        print(f"\n最終草稿長度: {len(result['final_draft'])} 字元")
        print("\n--- 最終草稿預覽 (前 600 字) ---")
        print(result['final_draft'][:600])

    return result

if __name__ == "__main__":
    print("\n🚀 開始 API 測試...\n")

    # 測試 1: 需求分析
    requirement = test_requirement()

    # 測試 2: 撰寫
    if requirement:
        draft = test_writer(requirement)

        # 測試 3: 並行審查
        if draft:
            review_result = test_parallel_review(draft, requirement.get('doc_type', '函'))

    # 測試 4: 完整流程
    print("\n" + "🔄 測試完整開會流程（這可能需要 1-2 分鐘）...")
    meeting_result = test_full_meeting()

    print("\n" + "=" * 50)
    print("✅ 所有測試完成！")
    print("=" * 50)
