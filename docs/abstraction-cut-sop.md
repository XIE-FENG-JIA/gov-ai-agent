# Abstraction Cut SOP

## `inspect.getsource` 型測試同步檢

- 抽出模組時，先搜尋相關測試是否用 `inspect.getsource()` 斷言實作細節。
- 若安全或治理邏輯被搬到 helper/parser 模組，測試要改成 import-graph 斷言：外層模組必須明確匯入 helper/parser，helper/parser 必須保留原安全實作。
- 不要只把關鍵字複製到外層模組註解或 docstring；測試應檢查實際承載邏輯的模組。
- XXE 類 XML 測試必須同時斷言沒有 `import xml.etree.ElementTree`，並確認最終 parser 使用 `defusedxml.ElementTree`。
