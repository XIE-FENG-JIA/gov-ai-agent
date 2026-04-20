import importlib


def _runtime():
    return importlib.import_module("src.cli.generate")


def _load_batch_csv(batch_file: str) -> list[dict]:
    """讀取 CSV 批次檔案，欄位須包含 input，output 為選填。"""
    runtime = _runtime()
    with open(batch_file, "r", encoding="utf-8-sig") as handle:
        reader = runtime.csv.DictReader(handle)
        if reader.fieldnames is None or "input" not in reader.fieldnames:
            runtime.console.print("[red]錯誤：CSV 檔案必須包含 input 欄位。[/red]")
            runtime.console.print("[dim]格式：input,output[/dim]")
            raise runtime.typer.Exit(1)
        items = []
        for row in reader:
            if not row.get("input", "").strip():
                continue
            items.append({"input": row["input"], "output": row.get("output", "").strip() or None})
        return items
