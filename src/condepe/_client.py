"""HTTP layer: the canonical Observatory endpoint, with the Hugging Face
mirror as fallback, and a disk cache keyed by catalogue version.

Both backends serve the *same relative paths* (``catalogo.json``,
``<source>/<source>.parquet``, ``MANIFESTO.sha256``), so a file is always
addressed by its path in the catalogue. The mirror exists for availability:
the canonical server is a single machine in Pernambuco, and its network may
one day restrict access from outside Brazil.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from platformdirs import user_cache_dir

from . import _msg

CANONICAL_URL = "https://cf.pe.gov.br/observatorio/dados/atual"
MIRROR_URL = "https://huggingface.co/datasets/mlkwy/observatorio-pernambuco/resolve/main"
USER_AGENT = "condepe Python package (https://github.com/StrategicProjects/condepe-py)"

_TIMEOUT = 60.0
_CATALOG_MAX_AGE = 6 * 3600  # seconds a cached catalogue is trusted without asking
_TRANSIENT = {429, 500, 502, 503, 504}


class CondepeError(RuntimeError):
    """Classe base dos erros do condepe."""


class HttpError(CondepeError):
    """Nem o endereço canônico nem o espelho responderam."""


class IntegrityError(CondepeError):
    """Um arquivo baixado não confere com o SHA-256 do catálogo."""


def set_timeout(seconds: float = 60.0) -> None:
    """Define o tempo limite, em segundos, de cada requisição HTTP."""
    global _TIMEOUT
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0:
        raise ValueError("`seconds` must be a positive number.")
    _TIMEOUT = float(seconds)


def base_urls() -> list[str]:
    """Backends in the order they are tried: canonical, then mirror.

    ``CONDEPE_URL`` and ``CONDEPE_MIRROR_URL`` override them (an empty
    ``CONDEPE_MIRROR_URL`` disables the fallback).
    """
    canonical = os.environ.get("CONDEPE_URL", CANONICAL_URL).rstrip("/")
    mirror = os.environ.get("CONDEPE_MIRROR_URL", MIRROR_URL).rstrip("/")
    return [u for u in (canonical, mirror) if u]


def cache_dir() -> Path:
    """Pasta do cache em disco (``CONDEPE_CACHE_DIR`` a substitui)."""
    return Path(os.environ.get("CONDEPE_CACHE_DIR") or user_cache_dir("condepe"))


def clear_cache() -> Path:
    """Apaga todo o cache e devolve a pasta."""
    d = cache_dir()
    if d.exists():
        shutil.rmtree(d)
        _msg.success(f"Cleared condepe cache at {d}.")
    else:
        _msg.inform(f"No condepe cache found at {d}.")
    return d


def _get(url: str) -> bytes:
    """One GET with up to three tries on transient failures."""
    last: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": USER_AGENT})
        except requests.RequestException as exc:  # connection, DNS, timeout
            last = exc
        else:
            if resp.status_code == 200:
                return resp.content
            last = HttpError(f"HTTP {resp.status_code} from {url}")
            if resp.status_code not in _TRANSIENT:
                break
        if attempt < 2:
            time.sleep(2**attempt)
    raise HttpError(str(last))


def versioned_base(base: str, version: str) -> str:
    """The backend address of one published *version* (immutable), not of ``atual``.

    The canonical server keeps the last versions beside ``atual/``; the
    Hugging Face mirror tags each version, so ``resolve/main`` becomes
    ``resolve/<version>``. Any other base is assumed to keep ``<version>/``
    next to the current tree.
    """
    if base.endswith("/resolve/main"):
        return f"{base[: -len('main')]}{version}"
    if base.endswith("/atual"):
        return f"{base[: -len('atual')]}{version}"
    return f"{base}/{version}"


def fetch(path: str, version: str | None = None) -> bytes:
    """Fetch a relative path from the first backend that answers.

    With ``version``, the path is read from that version's immutable tree
    instead of the current one.
    """
    errors = []
    for base in base_urls():
        root = versioned_base(base, version) if version else base
        url = f"{root}/{quote(path)}"
        try:
            return _get(url)
        except HttpError as exc:
            errors.append(f"{base}: {exc}")
            if base != base_urls()[-1]:
                _msg.step("Canonical endpoint unavailable; trying the mirror.")
    raise HttpError("Could not reach the Observatory data. " + "; ".join(errors))


def catalog_json(refresh: bool = False) -> dict[str, Any]:
    """The published catalogue, from the disk cache when recent enough."""
    path = cache_dir() / "catalogo.json"
    if not refresh and path.exists() and time.time() - path.stat().st_mtime < _CATALOG_MAX_AGE:
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        raw = fetch("catalogo.json")
    except HttpError:
        # A stale catalogue is better than none: the files it lists are
        # immutable per version and stay valid in the cache.
        if path.exists():
            _msg.step("Using the cached catalogue; the Observatory could not be reached.")
            return json.loads(path.read_text(encoding="utf-8"))
        raise
    data = json.loads(raw)
    if "versao" not in data or "fontes" not in data:
        raise CondepeError("Unexpected catalogue format (no `versao`/`fontes`).")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return data


def cached_file(path: str, sha256: str, version: str, refresh: bool = False) -> Path:
    """Path to a verified local copy of a catalogue file, downloading if needed."""
    dest = cache_dir() / version / path
    if not refresh and dest.exists() and _sha256(dest.read_bytes()) == sha256:
        return dest
    raw = fetch(path)
    got = _sha256(raw)
    if got != sha256:
        # The current tree moved on since this catalogue was cached (a new
        # version was published): the version's own tree is immutable.
        try:
            raw = fetch(path, version=version)
            got = _sha256(raw)
        except HttpError:
            pass
    if got != sha256:
        raise IntegrityError(
            f"{path}: sha256 {got[:12]}… differs from the catalogue ({sha256[:12]}…). "
            "The publication may be in progress; try again in a few minutes, "
            "or pass refresh=True to re-read the catalogue."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(raw)
    tmp.replace(dest)
    _prune_old_versions(version)
    return dest


def _prune_old_versions(keep: str) -> None:
    """Drop cached files of other catalogue versions (they are superseded).

    ``malha/`` holds the municipal meshes, versioned on their own.
    """
    root = cache_dir()
    for child in root.iterdir():
        if child.is_dir() and child.name not in (keep, "malha"):
            shutil.rmtree(child, ignore_errors=True)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
