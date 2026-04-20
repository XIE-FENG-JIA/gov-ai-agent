from __future__ import annotations

import argparse
import copy
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PureWindowsPath
from typing import Iterable

import yaml


@dataclass(frozen=True)
class ArchivedFixture:
    corpus_source: Path
    corpus_target: Path
    raw_source: Path | None
    raw_target: Path | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive fixture-backed corpus/raw files out of kb_data.")
    parser.add_argument("--base-dir", type=Path, default=Path("kb_data"))
    parser.add_argument(
        "--storage-name",
        action="append",
        default=None,
        help="Optional source storage name to restrict archival, e.g. mojlaw",
    )
    parser.add_argument(
        "--archive-label",
        default=f"fixture_{date.today():%Y%m%d}",
        help="Archive folder label under kb_data/archive/",
    )
    return parser


def archive_fixture_corpus(
    *,
    base_dir: Path,
    storage_names: Iterable[str] | None = None,
    archive_label: str | None = None,
) -> list[ArchivedFixture]:
    archive_root = base_dir / "archive" / (archive_label or f"fixture_{date.today():%Y%m%d}")
    allowed = {name.lower() for name in storage_names or []}
    archived: list[ArchivedFixture] = []

    for corpus_path in sorted((base_dir / "corpus").rglob("*.md")):
        if allowed and corpus_path.parent.name.lower() not in allowed:
            continue

        metadata = _read_metadata(corpus_path)
        if not metadata.get("fixture_fallback"):
            continue

        corpus_target = archive_root / corpus_path.relative_to(base_dir)
        raw_source = _resolve_raw_path(base_dir=base_dir, raw_snapshot_path=metadata.get("raw_snapshot_path"))
        raw_target = archive_root / raw_source.relative_to(base_dir) if raw_source and raw_source.exists() else None

        try:
            _move_within_base(base_dir, corpus_path, corpus_target)
            if raw_source and raw_target:
                _move_within_base(base_dir, raw_source, raw_target)
        except PermissionError:
            _copy_within_base(base_dir, corpus_path, corpus_target)
            if raw_source and raw_target:
                _copy_within_base(base_dir, raw_source, raw_target)
            _write_archived_fixture_stub(
                corpus_path=corpus_path,
                metadata=metadata,
                archive_target=corpus_target,
                raw_target=raw_target,
            )

        archived.append(
            ArchivedFixture(
                corpus_source=corpus_path,
                corpus_target=corpus_target,
                raw_source=raw_source,
                raw_target=raw_target,
            )
        )

    return archived


def _move_within_base(base_dir: Path, source: Path, target: Path) -> None:
    source = source.resolve()
    base_resolved = base_dir.resolve()
    try:
        source.relative_to(base_resolved)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"refusing to move path outside base_dir: {source}") from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if source.read_bytes() != target.read_bytes():
            raise FileExistsError(f"archive target already exists with different content: {target}")
        source.unlink(missing_ok=True)
        return
    shutil.move(str(source), str(target))


def _copy_within_base(base_dir: Path, source: Path, target: Path) -> None:
    source = source.resolve()
    base_resolved = base_dir.resolve()
    try:
        source.relative_to(base_resolved)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"refusing to copy path outside base_dir: {source}") from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and source.read_bytes() == target.read_bytes():
        return
    shutil.copy2(str(source), str(target))


def _read_metadata(corpus_path: Path) -> dict[str, object]:
    text = corpus_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}
    metadata = yaml.safe_load(parts[1])
    return metadata if isinstance(metadata, dict) else {}


def _write_archived_fixture_stub(
    *,
    corpus_path: Path,
    metadata: dict[str, object],
    archive_target: Path,
    raw_target: Path | None,
) -> None:
    replacement = copy.deepcopy(metadata)
    replacement["deprecated"] = True
    replacement["archived_fixture"] = True
    replacement["fixture_fallback"] = False
    replacement["archive_target_path"] = archive_target.as_posix()
    if raw_target is not None:
        replacement["archived_raw_snapshot_path"] = raw_target.as_posix()
    frontmatter = yaml.dump(replacement, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
    body = "\n".join(
        [
            "# Archived fixture corpus",
            "",
            "This fixture-backed corpus file has been retired from active ingestion.",
            f"- archive_target_path: {archive_target.as_posix()}",
            f"- original_fixture_fallback: {bool(metadata.get('fixture_fallback'))}",
        ]
    )
    corpus_path.write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")


def _resolve_raw_path(*, base_dir: Path, raw_snapshot_path: object) -> Path | None:
    if not isinstance(raw_snapshot_path, str) or not raw_snapshot_path.strip():
        return None

    normalized = Path(*PureWindowsPath(raw_snapshot_path).parts)
    if normalized.is_absolute():
        return normalized
    if normalized.parts and normalized.parts[0].lower() == base_dir.name.lower():
        return base_dir.parent / normalized
    return base_dir / normalized


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    archive_dir = args.base_dir / "archive" / args.archive_label
    archived = archive_fixture_corpus(
        base_dir=args.base_dir,
        storage_names=args.storage_name,
        archive_label=args.archive_label,
    )
    print(f"archived={len(archived)} archive_dir={archive_dir.as_posix()}")
    for item in archived:
        print(item.corpus_target.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
