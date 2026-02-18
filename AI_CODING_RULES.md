# AI Vibe Coding 專用規範 (Spec Kit Context)

此文件由 Spec Kit 自動生成。**作為 AI Agent，你在編寫代碼時必須嚴格遵守以下規範，禁止 Hard-code 任何數值。**

---

## 1. Python CLI 開發規範
**檔案位置**: `src/theme/cli_colors.py`
**使用規則**:
- 禁止直接使用 HEX 顏色碼（如 '#ff0000'）。
- 必須從 `src.theme.cli_colors` 匯入 `CLI_THEME`。
- 使用範例: `console.print("Error", style=CLI_THEME["CLI_ERROR"])`

**可用變數 (Python Dictionary Keys)**:
- `CLI_INFO`: #3498db (CLI 提示訊息)
- `CLI_SUCCESS`: #2ecc71 (CLI 成功訊息)
- `CLI_WARNING`: #f1c40f (CLI 警告訊息)
- `CLI_ERROR`: #e74c3c (CLI 錯誤訊息)

---

## 2. 公文生成 (Word/PDF) 規範
**檔案位置**: `src/assets/document_standards.json`
**使用規則**:
- 所有排版參數（字體、邊界、行距）必須動態讀取此 JSON。
- 單位必須嚴格保留 (pt, cm)，**不可**擅自轉換為 px。
- 使用範例:
  ```python
  import json
  standards = json.load(open('src/assets/document_standards.json'))
  font_size = standards['typography']['fontSize']['title_main']['value'] # "16"
  ```

**核心標準值 (Reference)**:
- `standards['typography']['fontFamily']['official_serif']`: MingLiU (細明體 - 用於一般公文說明)
- `standards['typography']['fontFamily']['official_kai']`: DFKai-SB (標楷體 - 用於標題與署名)
- `standards['typography']['fontSize']['title_main']`: 16pt (大標題字級)
- `standards['typography']['fontSize']['title_sub']`: 14pt (次標題字級)
- `standards['typography']['fontSize']['body_standard']`: 12pt (內文標準字級)
- `standards['typography']['fontSize']['annotation']`: 10pt (註解或頁碼)
- `standards['typography']['lineHeight']['standard']`: 20pt (標準行距 (固定行高))
- `standards['typography']['lineHeight']['relaxed']`: 25pt (寬鬆行距)
- `standards['spacing']['margin']['page_top']`: 2.54cm (頁面邊界-上)
- `standards['spacing']['margin']['page_bottom']`: 2.54cm (頁面邊界-下)
- `standards['spacing']['margin']['page_left']`: 3.17cm (頁面邊界-左)
- `standards['spacing']['margin']['page_right']`: 3.17cm (頁面邊界-右)
- `standards['spacing']['indent']['paragraph']`: 2em (段落縮排 (2字元))

---

## 3. Web/Frontend 規範
**檔案位置**: `src/web_preview/styles/tokens.css`
**使用規則**:
- 使用 CSS Variables，禁止 Hard-code。
- 變數命名規則為 Kebab-case。

**CSS 變數清單**:
- `--typography-fontFamily-official_serif`: MingLiU
- `--typography-fontFamily-official_kai`: DFKai-SB
- `--typography-fontSize-title_main`: 16pt
- `--typography-fontSize-title_sub`: 14pt
- `--typography-fontSize-body_standard`: 12pt
- `--typography-fontSize-annotation`: 10pt
- `--typography-lineHeight-standard`: 20pt
- `--typography-lineHeight-relaxed`: 25pt
- `--color-text-primary`: #000000
- `--color-text-seal`: #FF0000
- `--color-cli-info`: #3498db
- `--color-cli-success`: #2ecc71
- `--color-cli-warning`: #f1c40f
- `--color-cli-error`: #e74c3c
