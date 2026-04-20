from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.e2e_rewrite import run_rewrite_e2e


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic rewrite E2E and emit report.")
    parser.add_argument(
        "--output-dir",
        default="output/e2e-rewrite",
        help="Directory for generated docx artifacts.",
    )
    parser.add_argument(
        "--report",
        "--report-path",
        default="docs/e2e-report.md",
        help="Markdown report output path.",
    )
    args = parser.parse_args()

    results = run_rewrite_e2e(
        output_dir=Path(args.output_dir),
        report_path=Path(args.report),
    )

    for item in results:
        print(
            f"{item['doc_type']}: docx={item['output_path']} "
            f"citation_count={item['citation_count']} "
            f"source_doc_ids={','.join(item['source_doc_ids'])}"
        )


if __name__ == "__main__":
    main()
