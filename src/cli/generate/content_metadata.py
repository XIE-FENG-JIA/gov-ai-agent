import importlib


def _runtime():
    return importlib.import_module("src.cli.generate")


def _apply_content_metadata(
    draft: str,
    *,
    priority_tag: str,
    cc: str,
    receiver_title: str,
    ref_number: str,
    date: str,
    header: str,
    classification: str,
    watermark: str,
    footnote: str,
    sign: str,
    attachment: str,
    page_break: bool,
    disclaimer: str,
) -> str:
    """將使用者指定的元資料（優先標記、副本、發文字號等）注入草稿。"""
    runtime = _runtime()
    console = runtime.console

    if priority_tag:
        tag_map = {"urgent": "【急件】", "confidential": "【密】", "normal": ""}
        tag_text = tag_map.get(priority_tag.lower(), "")
        if tag_text and "主旨" in draft:
            draft = draft.replace("主旨", f"{tag_text}主旨", 1)
            console.print(f"  [dim]已加入優先標記：{tag_text}[/dim]")
        elif priority_tag.lower() not in tag_map:
            console.print(f"[yellow]未知的優先標記：{priority_tag}（可用：urgent, confidential, normal）[/yellow]")

    if cc:
        cc_list = [c.strip() for c in cc.split(",") if c.strip()]
        if cc_list:
            cc_text = f"副本：{'、'.join(cc_list)}"
            if "副本" in draft:
                draft = runtime.re.sub(r"副本[：:].*", cc_text, draft, count=1)
            elif "正本" in draft:
                lines = draft.split("\n")
                new_lines = []
                inserted = False
                for line in lines:
                    new_lines.append(line)
                    if not inserted and line.strip().startswith("正本"):
                        new_lines.append(cc_text)
                        inserted = True
                if not inserted:
                    new_lines.append(cc_text)
                draft = "\n".join(new_lines)
            else:
                draft = draft.rstrip() + f"\n{cc_text}"
            console.print(f"  [dim]已加入副本：{'、'.join(cc_list)}[/dim]")

    if receiver_title:
        if "正本" in draft:
            lines = draft.split("\n")
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if line.strip().startswith("正本"):
                    new_lines.append(f"  敬稱：{receiver_title}")
            draft = "\n".join(new_lines)
        else:
            draft = draft.rstrip() + f"\n敬稱：{receiver_title}"
        console.print(f"  [dim]已加入敬稱：{receiver_title}[/dim]")

    if ref_number:
        if "主旨" in draft:
            draft = draft.replace("主旨", f"發文字號：{ref_number}\n主旨", 1)
        else:
            draft = f"發文字號：{ref_number}\n{draft}"
        console.print(f"  [dim]已加入發文字號：{ref_number}[/dim]")

    if date:
        date_text = f"發文日期：{date}"
        if "主旨" in draft:
            draft = draft.replace("主旨", f"{date_text}\n主旨", 1)
        else:
            draft = f"{date_text}\n{draft}"
        console.print(f"  [dim]已加入發文日期：{date}[/dim]")

    if header:
        draft = f"{header}\n\n{draft}"
        console.print(f"  [dim]已加入頁首：{header}[/dim]")

    if classification:
        valid = {"密", "機密", "極機密", "限閱"}
        if classification in valid:
            cls_text = f"【{classification}】"
            draft = f"{cls_text}\n{draft}"
            console.print(f"  [dim]已加入密等標記：{cls_text}[/dim]")
        else:
            console.print(f"[yellow]未知的密等：{classification}（可用：{'、'.join(sorted(valid))}）[/yellow]")

    if watermark:
        wm_text = f"【{watermark}】"
        draft = f"{wm_text}\n{draft}"
        console.print(f"  [dim]已加入浮水印：{wm_text}[/dim]")

    if footnote:
        draft = draft.rstrip() + f"\n附註：{footnote}"
        console.print(f"  [dim]已加入附註：{footnote}[/dim]")

    if sign:
        if "正本" in draft:
            draft = draft.replace("正本", f"\n{sign}\n\n正本", 1)
        else:
            draft = draft.rstrip() + f"\n\n{sign}"
        console.print(f"  [dim]已加入署名：{sign}[/dim]")

    if attachment:
        att_list = [a.strip() for a in attachment.split(",") if a.strip()]
        if att_list:
            att_lines = "\n".join(f"  {i}. {a}" for i, a in enumerate(att_list, 1))
            draft = draft.rstrip() + f"\n附件：\n{att_lines}"
            console.print(f"  [dim]已加入附件清單（{len(att_list)} 項）[/dim]")

    if page_break:
        if "說明" in draft and "辦法" in draft:
            draft = draft.replace("辦法", "--- 分頁 ---\n辦法", 1)
            console.print("  [dim]已在說明與辦法之間插入分頁標記。[/dim]")
        else:
            console.print("  [yellow]找不到「說明」及「辦法」段落，無法插入分頁標記。[/yellow]")

    if disclaimer:
        disclaimer_text = disclaimer.strip()
        if disclaimer_text:
            draft = draft.rstrip() + f"\n\n免責聲明：{disclaimer_text}"
            console.print("  [dim]已加入免責聲明[/dim]")

    return draft


def _display_format_options(
    *,
    speed: str,
    margin: str,
    line_spacing: str,
    font_size: str,
    duplex: str,
    orientation: str,
    paper_size: str,
    columns: str,
    seal: str,
    copy_count: str,
    draft_mark: str,
    urgency_label: str,
    lang: str,
    header_logo: str,
) -> None:
    """顯示排版與格式設定（不修改草稿內容）。"""
    runtime = _runtime()
    console = runtime.console
    values = {
        "speed": speed,
        "margin": margin,
        "line_spacing": line_spacing,
        "font_size": font_size,
        "duplex": duplex,
        "orientation": orientation,
        "paper_size": paper_size,
        "columns": columns,
        "seal": seal,
        "draft_mark": draft_mark,
        "urgency_label": urgency_label,
        "lang": lang,
    }
    for key, label, choices, skip_val, hint in runtime._FORMAT_OPTION_DEFS:
        normalised = values[key].strip().lower()
        display = choices.get(normalised)
        if display:
            if skip_val is None or normalised != skip_val:
                console.print(f"  [dim]{label}：{display}[/dim]")
        else:
            opts = hint or "/".join(choices)
            console.print(f"[yellow]未知的{label}：{values[key]}（可用：{opts}）[/yellow]")

    try:
        cc_val = int(copy_count.strip())
    except ValueError:
        cc_val = 0
    if 1 <= cc_val <= 10:
        if cc_val > 1:
            console.print(f"  [dim]輸出份數：{cc_val} 份[/dim]")
        else:
            console.print("  [dim]輸出份數：1 份（預設）[/dim]")
    else:
        console.print(f"[yellow]無效的份數設定：{copy_count}（可用：1-10）[/yellow]")

    if header_logo:
        if runtime.os.path.isfile(header_logo):
            console.print(f"  [dim]頁首 Logo：{runtime.os.path.basename(header_logo)}[/dim]")
        else:
            console.print(f"[yellow]找不到 logo 檔案：{header_logo}[/yellow]")
