"""政府 API 端點常數與預設法規清單。"""

# ========== API 端點 ==========
LAW_API_URL = "https://law.moj.gov.tw/api/Ch/Law/json"
GAZETTE_API_URL = "https://gazette.nat.gov.tw/egFront/OpenData/downloadXML.jsp"
# v2 REST API 已需 API Key（2026-03），改用前端端點（見 opendata_fetcher.py）
OPENDATA_API_URL = "https://data.gov.tw/api/v2/rest/dataset"  # 保留供參考

# ========== 公文撰寫常用法規 PCode 清單 ==========
# 已於 2026-03 與全國法規資料庫 API 實際回傳比對校正
DEFAULT_LAW_PCODES: dict[str, str] = {
    "A0030018": "公文程式條例",
    "A0030055": "行政程序法",
    "A0030133": "中央法規標準法",
    "I0050021": "個人資料保護法",
    "I0020026": "政府資訊公開法",
    "S0020001": "公務人員任用法",
    "S0020038": "公務員服務法",
    "A0030210": "行政罰法",
    "A0030154": "行政訴訟法",
    "A0030057": "政府採購法",
    "N0030001": "勞動基準法",
    "I0020004": "國家賠償法",
    "A0030011": "印信條例",
    "A0030020": "訴願法",
    "A0030134": "檔案法",
}

# ========== 預設搜尋參數 ==========
DEFAULT_GAZETTE_DAYS = 7
DEFAULT_OPENDATA_KEYWORD = "警政署"
DEFAULT_OPENDATA_LIMIT = 10

# ========== 來源等級定義 ==========
SOURCE_LEVEL_A = "A"  # 權威來源：行政院公報、全國法規資料庫
SOURCE_LEVEL_B = "B"  # 輔助來源：政府開放資料平臺等

# 公報詳情頁 URL 模板
GAZETTE_DETAIL_URL = "https://gazette.nat.gov.tw/egFront/detail.do?metaid={meta_id}&log=detailLog"
# 法規全文頁 URL 模板
LAW_DETAIL_URL = "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode={pcode}"
# 開放資料集頁面 URL 模板
OPENDATA_DETAIL_URL = "https://data.gov.tw/dataset/{dataset_id}"

# ========== Bulk 下載端點 ==========
GAZETTE_BULK_ZIP_URL = "https://gazette.nat.gov.tw/egFront/OpenData/download.jsp"
LAW_BULK_XML_URL = "http://law.moj.gov.tw/PublicData/GetFile.ashx"

# ========== 警政署 OPEN DATA ==========
NPA_API_BASE = "https://www.npa.gov.tw/ch/app/openData/data/list"
NPA_API_URL = f"{NPA_API_BASE}?module=wg051&mserno=0&type=xml"
NPA_DETAIL_URL = "https://data.gov.tw/dataset/{dataset_id}"
# 可用模組清單（2026-03 實測確認）
NPA_MODULES: list[str] = [
    "wg051",  # 警政開放資料集（100 項）
    "wg054",  # 警政分析文章（38 項，含詳細內容）
    "wg057",  # 犯罪統計週報（100 項）
]

# ========== 立法院 ==========
LY_API_URL = "http://data.ly.gov.tw/odw/openDatasetJson.action"
LY_GOVAPI_URL = "https://v2.ly.govapi.tw"
DEFAULT_LY_TERM = "all"
DEFAULT_LY_LIMIT = 50

# ========== 政府採購 ==========
PCC_API_URL = "https://pcc-api.openfun.app"
DEFAULT_PCC_DAYS = 7
DEFAULT_PCC_LIMIT = 50

# ========== 司法院 ==========
JUDICIAL_AUTH_URL = "https://data.judicial.gov.tw/jdg/api/Auth"
JUDICIAL_JLIST_URL = "https://data.judicial.gov.tw/jdg/api/JList"
JUDICIAL_JDOC_URL = "https://data.judicial.gov.tw/jdg/api/JDoc"
DEFAULT_JUDICIAL_LIMIT = 20

# ========== 法務部行政函釋 ==========
MOJLAW_BASE_URL = "https://mojlaw.moj.gov.tw"
DEFAULT_INTERPRETATION_LIMIT = 30

# ========== 地方法規 ==========
LOCAL_LAW_URLS: dict[str, str] = {
    "taipei": "https://www.laws.taipei.gov.tw",
}
DEFAULT_LOCAL_LIMIT = 30

# ========== 考試院 ==========
EXAMYUAN_BASE_URL = "https://law.exam.gov.tw"
DEFAULT_EXAMYUAN_LIMIT = 30

# ========== 主計總處 ==========
DGBAS_API_URL = "https://nstatdb.dgbas.gov.tw"

# ========== 監察院 ==========
CONTROLYUAN_BASE_URL = "https://www.cy.gov.tw"
CONTROLYUAN_CORRECTION_URL = "https://www.cy.gov.tw/CyBsBox.aspx?CSN=2&n=134"
DEFAULT_CONTROLYUAN_LIMIT = 20
