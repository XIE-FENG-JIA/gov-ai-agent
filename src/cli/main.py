import typer
from typing import Optional
from rich.console import Console
from src import __version__
from src.cli import kb
from src.cli import generate
from src.cli import config_tools
from src.cli import switcher

app = typer.Typer(
    name="gov-ai",
    help="台灣政府公文 AI 智慧助理",
    no_args_is_help=True,
)
app.add_typer(kb.app, name="kb", help="知識庫管理指令")
app.add_typer(config_tools.app, name="config", help="組態設定工具")
app.command(name="generate")(generate.generate)
app.command(name="switch")(switcher.switch)

console = Console()

def version_callback(value: bool):
    """顯示版本號後結束程式。"""
    if value:
        console.print(f"公文 AI 助理 CLI 版本：[bold green]{__version__}[/bold green]")
        raise typer.Exit()

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="顯示版本資訊並結束。",
        callback=version_callback,
        is_eager=True,
    )
):
    """
    台灣政府公文 AI 智慧助理。

    使用此 CLI 工具依據公文規範產生、審查與匯出政府公文。
    """
    pass

if __name__ == "__main__":
    app()
