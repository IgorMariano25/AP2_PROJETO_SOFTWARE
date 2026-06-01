"""Phase 2 - Clone (or update) the selected repositories.

Idempotent: existing clones are fetched/updated instead of re-cloned. Uses a
shallow-ish full clone (needs full history for git metrics, so no --depth).
"""
from __future__ import annotations

from common import (REPOS_DIR, command_exists, get_logger, read_repo_list,
                    repo_to_folder, run_command)

log = get_logger("clone")


def clone_or_update(full_name: str) -> None:
    folder = REPOS_DIR / repo_to_folder(full_name)
    url = f"https://github.com/{full_name}.git"

    if (folder / ".git").exists():
        log.info("Updating %s ...", full_name)
        run_command("git fetch --all --quiet", cwd=folder, timeout=1800)
        return

    log.info("Cloning %s ...", full_name)
    if command_exists("gh"):
        out = run_command(f'gh repo clone "{full_name}" "{folder}"',
                          timeout=3600)
    else:
        out = run_command(f'git clone "{url}" "{folder}"', timeout=3600)
    if not (folder / ".git").exists():
        log.warning("Clone may have failed for %s: %s", full_name, out[:200])


def main() -> None:
    repos = read_repo_list()
    if not repos:
        log.error("repos.txt is empty. Run search_repositories.py first.")
        return
    for name in repos:
        try:
            clone_or_update(name)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to clone %s: %s", name, exc)
    log.info("Done. %d repositories processed.", len(repos))


if __name__ == "__main__":
    main()
