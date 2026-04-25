"""AST-based import graph analysis for src/cli/ modules."""
import ast
import json
import sys
from pathlib import Path
from collections import defaultdict

CLI_DIR = Path(__file__).parent.parent / "src" / "cli"


def get_all_py_files():
    files = []
    for p in sorted(CLI_DIR.rglob("*.py")):
        rel = p.relative_to(CLI_DIR)
        lines = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        files.append((str(rel), p, lines))
    return files


def module_key(rel_path: str) -> str:
    parts = Path(rel_path).parts
    m = ".".join(parts)
    if m.endswith(".py"):
        m = m[:-3]
    return m


def parse_imports(filepath: Path):
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(("import", alias.name, None))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            level = node.level
            imports.append(("from", module, names, level))
    return imports


def normalize_to_cli_module(module_str: str, level: int, src_key: str) -> str | None:
    """Return a cli sub-module key if the import is from src.cli.*"""
    if module_str.startswith("src.cli."):
        rest = module_str[len("src.cli."):]
        return rest if rest else None
    if module_str == "src.cli":
        return None  # importing the package itself, not a submodule
    # Relative imports within src.cli
    if level > 0:
        parts = src_key.split(".")
        # For __init__ files, they represent the package itself, not a file
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        # level 1 = current package, level 2 = parent package, etc.
        base_parts = parts[: max(0, len(parts) - (level - 1))]
        if module_str:
            target = ".".join(base_parts + [module_str])
        else:
            # from . import X — target is the base package itself
            # We can't determine specific sub-module without names context
            target = ".".join(base_parts) if base_parts else None
        return target if target else None
    return None


files = get_all_py_files()

data = {}
for rel, path, lines in files:
    key = module_key(rel)
    imps = parse_imports(path)
    data[key] = {"path": rel, "lines": lines, "imports": imps}

cli_modules = set(data.keys())

dep_matrix = defaultdict(set)
external_deps = defaultdict(set)

for src_key, info in data.items():
    for imp_tuple in info["imports"]:
        imp_type = imp_tuple[0]
        module = imp_tuple[1]
        names = imp_tuple[2]
        level = imp_tuple[3] if len(imp_tuple) > 3 else 0

        if imp_type == "from":
            if level > 0 and not module:
                # from . import X, Y — each name could be a sub-module
                # Resolve the base package
                parts = src_key.split(".")
                if parts and parts[-1] == "__init__":
                    parts = parts[:-1]
                base_parts = parts[: max(0, len(parts) - (level - 1))]
                if names:
                    for name in names:
                        candidate = ".".join(base_parts + [name]) if base_parts else name
                        if candidate in cli_modules:
                            dep_matrix[src_key].add(candidate)
            else:
                cli_mod = normalize_to_cli_module(module, level, src_key)
                if cli_mod:
                    dep_matrix[src_key].add(cli_mod)
                elif module.startswith("src."):
                    external_deps[src_key].add(module)
        elif imp_type == "import":
            if module.startswith("src.cli."):
                rest = module[len("src.cli."):]
                if rest:
                    dep_matrix[src_key].add(rest)
            elif module.startswith("src."):
                external_deps[src_key].add(module)

result = {
    "files": [{"key": k, "path": v["path"], "lines": v["lines"]} for k, v in data.items()],
    "dep_matrix": {k: sorted(v) for k, v in dep_matrix.items()},
    "external_deps": {k: sorted(v) for k, v in external_deps.items()},
}
print(json.dumps(result, ensure_ascii=False, indent=2))
