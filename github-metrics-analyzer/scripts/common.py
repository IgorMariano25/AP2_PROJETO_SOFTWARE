"""Shared utilities for the GitHub Metrics Analyzer pipeline.

Centralizes paths, logging, subprocess execution and GitHub API access so that
every phase script behaves consistently (encoding, error handling, idempotency).
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Iterable, Optional

import requests

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
# scripts/ -> project root (github-metrics-analyzer/)
ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# Secrets / environment loading
# --------------------------------------------------------------------------- #
# Load a local .env (never committed) so the GitHub token stays out of code and
# shell history. python-dotenv is optional; if absent we parse .env manually.
def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass
    # Minimal fallback parser (KEY=VALUE, ignores blanks/comments).
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

REPOS_DIR = ROOT / "repos"
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"
REPOS_TXT = ROOT / "repos.txt"
DB_PATH = ROOT / "metrics.db"

# --------------------------------------------------------------------------- #
# Temp directory redirection
# --------------------------------------------------------------------------- #
# The pipeline processes large repos (e.g. ghidra: 15k+ Java files, deep git
# history). Tools like PyDriller (GitPython), Semgrep and git spawn subprocesses
# that write to the system TEMP dir. On Windows that defaults to C:, which may be
# small/full. We redirect TEMP/TMP to a project-local folder on the same volume
# as the data (lots of free space) so heavy runs don't exhaust the system drive.
# Subprocesses inherit os.environ, so git/semgrep/pydriller all follow suit.
TMP_DIR = ROOT / ".tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TMP"] = str(TMP_DIR)
os.environ["TEMP"] = str(TMP_DIR)
os.environ["TMPDIR"] = str(TMP_DIR)  # POSIX convention (Git Bash, etc.)
import tempfile as _tempfile  # noqa: E402
_tempfile.tempdir = str(TMP_DIR)

for _d in (REPOS_DIR, DATA_DIR, REPORTS_DIR, CHARTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                                "%H:%M:%S")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


log = get_logger("common")


# --------------------------------------------------------------------------- #
# Repository folder naming  (owner/repo  <->  owner__repo)
# --------------------------------------------------------------------------- #
def repo_to_folder(full_name: str) -> str:
    return full_name.replace("/", "__")


def folder_to_repo(folder_name: str) -> str:
    return folder_name.replace("__", "/")


def iter_repo_dirs() -> Iterable[Path]:
    """Yield every cloned repository directory inside repos/."""
    if not REPOS_DIR.exists():
        return
    for path in sorted(REPOS_DIR.iterdir()):
        if path.is_dir() and (path / ".git").exists():
            yield path


def read_repo_list() -> list[str]:
    """Read owner/repo entries from repos.txt (ignoring blanks/comments)."""
    if not REPOS_TXT.exists():
        return []
    lines = REPOS_TXT.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]


# --------------------------------------------------------------------------- #
# Subprocess helpers
# --------------------------------------------------------------------------- #
def run_command(command, cwd: Optional[Path] = None, shell: bool = True,
                timeout: Optional[int] = None) -> str:
    """Run a shell command and return stdout (utf-8, errors ignored)."""
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            shell=shell,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout,
        )
        return (result.stdout or "").strip()
    except subprocess.TimeoutExpired:
        log.warning("Command timed out: %s", command)
        return ""
    except Exception as exc:  # noqa: BLE001 - keep the pipeline alive
        log.warning("Command failed (%s): %s", command, exc)
        return ""


def command_exists(name: str) -> bool:
    """Check whether an executable is available on PATH."""
    from shutil import which
    return which(name) is not None


# --------------------------------------------------------------------------- #
# External heavy tools (not pip-installable, kept outside the repo)
# --------------------------------------------------------------------------- #
# Per the study prompt (§5-A), heavy binaries (CodeQL CLI, SonarScanner,
# Gitleaks) live in E:\developer-tools (overridable via DEVELOPER_TOOLS env),
# not versioned in Git. We resolve a tool by: explicit env override → PATH →
# a subfolder of the developer-tools root. Returns the absolute path string or
# None so collectors can skip gracefully when a tool is absent.
DEVELOPER_TOOLS = Path(os.getenv("DEVELOPER_TOOLS", r"E:\developer-tools"))


def find_external_tool(env_var: str, exe_names: Iterable[str],
                       subdirs: Iterable[str] = ()) -> Optional[str]:
    """Locate an external binary.

    Resolution order:
      1. ``$<env_var>`` if set and points to an existing file.
      2. Any of *exe_names* found on PATH.
      3. ``DEVELOPER_TOOLS/<subdir>/<exe>`` (and a direct child) for each combo.
    """
    from shutil import which

    override = os.getenv(env_var)
    if override and Path(override).exists():
        return override

    for exe in exe_names:
        hit = which(exe)
        if hit:
            return hit

    roots = [DEVELOPER_TOOLS, *(DEVELOPER_TOOLS / s for s in subdirs)]
    for root in roots:
        for exe in exe_names:
            for cand in (root / exe, root / "bin" / exe):
                if cand.exists():
                    return str(cand)
    return None


# --------------------------------------------------------------------------- #
# GitHub API
# --------------------------------------------------------------------------- #
GITHUB_API = "https://api.github.com"


def github_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # Accept either GITHUB_TOKEN or GH_TOKEN (gh CLI convention).
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_get(url: str, params: Optional[dict] = None, max_retries: int = 5):
    """GET a GitHub endpoint with rate-limit aware backoff.

    Handles 403/429 (primary & secondary rate limits) using the
    ``Retry-After`` and ``X-RateLimit-Reset`` headers.
    """
    headers = github_headers()
    for attempt in range(1, max_retries + 1):
        resp = requests.get(url, headers=headers, params=params, timeout=60)

        if resp.status_code == 200:
            return resp

        if resp.status_code in (403, 429):
            retry_after = resp.headers.get("Retry-After")
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if retry_after is not None:
                wait = int(retry_after)
            elif remaining == "0":
                reset = int(resp.headers.get("X-RateLimit-Reset", "0"))
                wait = max(reset - int(time.time()), 1)
            else:
                wait = min(2 ** attempt, 60)
            log.warning("Rate limited (%s). Waiting %ss (attempt %d/%d)",
                        resp.status_code, wait, attempt, max_retries)
            time.sleep(min(wait, 120))
            continue

        # Other errors: log and stop retrying
        log.error("GitHub API error %s for %s: %s",
                  resp.status_code, url, resp.text[:200])
        resp.raise_for_status()

    raise RuntimeError(f"Exceeded retries for {url}")


def github_paginate(url: str, params: Optional[dict] = None,
                    max_pages: int = 50):
    """Yield items from a paginated GitHub list endpoint (per_page=100)."""
    params = dict(params or {})
    params.setdefault("per_page", 100)
    page = 1
    while page <= max_pages:
        params["page"] = page
        resp = github_get(url, params=params)
        items = resp.json()
        if not isinstance(items, list) or not items:
            break
        yield from items
        if len(items) < params["per_page"]:
            break
        page += 1
