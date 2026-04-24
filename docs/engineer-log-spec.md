# engineer-log.md — Format & Lifecycle Spec (T7.3)

> 2026-04-24 — pua-loop 第二輪規範收官

## Why

`engineer-log.md` 是逐輪反思的事實帳，不是寫週報。auto-engineer / pua-loop
每輪都會 append；缺規範就會：

- 反思爆 1000+ 行，主檔失序
- 同一份事故被重複寫
- 缺三證自審 → 沒人看出 sensor 漏項
- archive 不及時 → context 撐爆 main file

## Format Contract

### 每輪一個 section

```markdown
## v<verison> 第<n>輪 — <關鍵主題>（<YYYY-MM-DD HH:MM>）

### 三證自審（sensor 含 git status）
- `git status --short | wc -l` = <number>
- `wc -l <關鍵檔案>` = <number>
- `<其他關鍵指標>` = <value>

### 本輪事故 + 處置
1. **<事故 1>** — <根因 + 處置>
2. **<事故 2>** — <同上>
3. **<新發現>** — <說明 + backlog 標記>

### 下一輪錨點
- <下輪要做什麼>
- <風險 / 依賴 / blocker>

> [PUA生效 🔥] **底層邏輯**：<本輪心得>。**抓手**：<關鍵作法>。**對齊**：<與大圖對齊>。**因為信任所以簡單** — <收尾>。
```

### 必含元素

| 元素 | 必填 | 說明 |
|---|---|---|
| 三證自審 | ✅ | 至少 3 條可機器查的指標（不寫主觀感受） |
| 事故 + 處置 | ✅ | 實際做了什麼、為什麼這麼做 |
| 下一輪錨點 | ✅ | 給未來的自己（或下個 agent）讀 |
| PUA 旁白 | ✅ | 阿里味四要素：底層邏輯 / 抓手 / 對齊 / 因為信任所以簡單 |

### 禁忌

- ❌ 不寫 trivia（"我點了 enter"）
- ❌ 不複述 git diff（git log 已是事實帳）
- ❌ 不灌水超過 30 行（hard cap，主檔守 300 行）
- ❌ 不裝勝利（沒驗證的不算閉環）

## Lifecycle

### Append-Only

每輪 append 在檔案結尾。**禁止改動歷史輪 section**（除非修筆誤）。

### Soft Cap

主檔 ≤ **300 行**。超過即下輪做 archive：

```bash
# Archive 前 N 輪到月檔
mv engineer-log.md docs/archive/engineer-log-202604g.md
# 重啟主檔，留鏈接和最近 1 輪
cat > engineer-log.md <<EOF
> 歷史輪反思已歸檔到 [docs/archive/engineer-log-202604g.md](docs/archive/engineer-log-202604g.md)
> ...
EOF
```

### Hard Cap

300 行容忍上限是 **400 行**。觸到即同輪 inline rotate（不能拖到下輪）。

## Archive Index

歷史月檔放在 `docs/archive/engineer-log-YYYYMM<letter>.md`，後綴
`a` / `b` / ... 防同月多次 rotation 衝突。最新 archive 索引維護在
`docs/archive/README.md`（新項目首輪建立）。

## 與 program.md 的分工

| 檔案 | 角色 |
|---|---|
| `program.md` | 「現況 + 活任務」清單；只列 P0/P1/P2 backlog 與最近輪硬指標 |
| `engineer-log.md` | 「逐輪事實帳」append-only；驗證證據 + 反思 |
| `results.log` | 機器寫的 raw run log（auto-engineer 產出，非人工） |

不混用。要追完整脈絡：先讀 archive，再看 `engineer-log.md`，最後 git log。

## 驗證

每輪 commit 前：

```bash
wc -l engineer-log.md       # ≤ 300（軟 cap）/ ≤ 400（硬 cap）
grep -c '^## v' engineer-log.md    # 輪數連續，不跳號
```

T9.6-REOPEN-v5 已落地對應的 archive 操作（`docs/archive/engineer-log-202604g.md`）。
