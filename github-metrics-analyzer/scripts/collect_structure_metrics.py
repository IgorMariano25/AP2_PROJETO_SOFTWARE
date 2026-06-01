"""Phase 7 - Java structural metrics using `javalang` (pure Python).

Parser decision (see README): we use ``javalang`` instead of JavaParser to keep
the whole pipeline in a single language and avoid a JVM/Maven build step. It
parses Java source into an AST from which we extract classes, interfaces,
abstract classes, methods, fields, ``extends`` and ``implements``.

Writes data/structure.csv (one row per top-level/nested type).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from common import DATA_DIR, folder_to_repo, get_logger, iter_repo_dirs

log = get_logger("structure")

# javalang walks the AST recursively; deeply nested Java files can exceed the
# default CPython recursion limit (1000). Raise it for this phase.
sys.setrecursionlimit(20000)

try:
    import javalang
except ImportError:  # pragma: no cover
    javalang = None


def _extends(node) -> str:
    ext = getattr(node, "extends", None)
    if ext is None:
        return ""
    if isinstance(ext, list):  # interfaces can extend many
        return ";".join(getattr(e, "name", "") for e in ext)
    return getattr(ext, "name", "")


def _implements(node) -> str:
    impl = getattr(node, "implements", None) or []
    return ";".join(getattr(i, "name", "") for i in impl)


def analyze_file(path: Path, repo_name: str, rel: str) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        tree = javalang.parse.parse(text)
    except Exception:  # noqa: BLE001 - skip unparsable files
        return []

    rows = []
    try:
        for _, node in tree.filter(javalang.tree.TypeDeclaration):
            is_interface = isinstance(node, javalang.tree.InterfaceDeclaration)
            is_enum = isinstance(node, javalang.tree.EnumDeclaration)
            modifiers = getattr(node, "modifiers", set()) or set()
            methods = [m for m in getattr(node, "methods", [])]
            fields = getattr(node, "fields", []) or []
            field_count = sum(len(f.declarators) for f in fields)

            kind = "interface" if is_interface else "enum" if is_enum else "class"
            rows.append({
                "repository": repo_name,
                "file": rel,
                "type_name": node.name,
                "kind": kind,
                "is_abstract": "abstract" in modifiers,
                "is_interface": is_interface,
                "methods": len(methods),
                "attributes": field_count,
                "extends": _extends(node),
                "implements": _implements(node),
            })
    except RecursionError:
        log.warning("Skipping %s (AST too deeply nested)", rel)
        return rows
    except Exception as exc:  # noqa: BLE001 - keep the phase alive
        log.warning("Skipping %s (%s)", rel, exc)
        return rows
    return rows


def main() -> None:
    if javalang is None:
        log.error("javalang not installed. Run: pip install javalang")
        _write([])
        return

    all_rows = []
    for repo in iter_repo_dirs():
        log.info("Structure for %s ...", repo.name)
        name = folder_to_repo(repo.name)
        try:
            for path in repo.rglob("*.java"):
                if "/.git/" in path.as_posix():
                    continue
                rel = path.relative_to(repo).as_posix()
                all_rows.extend(analyze_file(path, name, rel))
        except Exception as exc:  # noqa: BLE001
            log.warning("Structure failed for %s: %s", repo.name, exc)
    _write(all_rows)


def _write(rows: list[dict]) -> None:
    out = DATA_DIR / "structure.csv"
    fields = ["repository", "file", "type_name", "kind", "is_abstract",
              "is_interface", "methods", "attributes", "extends", "implements"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d type rows to %s", len(rows), out.name)


if __name__ == "__main__":
    main()
