"""Ricerca di file duplicati: stessa dimensione -> hash parziale -> hash completo."""
from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from .cleaner import _walk_files
from .filters import Filters

CHUNK = 1024 * 1024
PARTIAL = 64 * 1024


@dataclass
class DupGroup:
    size: int
    files: list[tuple[str, float]]   # (percorso, data modifica)

    @property
    def wasted(self) -> int:
        return self.size * (len(self.files) - 1)


def _hash(path: str, limit: int | None, cancel: Callable[[], bool]) -> bytes | None:
    h = hashlib.blake2b(digest_size=20)
    try:
        with open(path, "rb") as f:
            if limit:
                h.update(f.read(limit))
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size > limit * 2:  # anche la coda, per distinguere file con lo stesso inizio
                    f.seek(-limit, os.SEEK_END)
                    h.update(f.read(limit))
            else:
                while chunk := f.read(CHUNK):
                    if cancel():
                        return None
                    h.update(chunk)
    except OSError:
        return None
    return h.digest()


def find_duplicates(roots: list[str], flt: Filters, progress: Callable[[str], None] | None = None,
                    cancel: Callable[[], bool] = lambda: False) -> list[DupGroup] | None:
    """Cerca i duplicati solo tra i file che superano il filtro (nome, estensione, data, dimensione)."""
    by_size: dict[int, list[tuple[str, float]]] = defaultdict(list)
    seen: set[str] = set()
    n = 0
    last = 0.0
    for root in roots:
        for path, size, mtime in _walk_files(root, True, cancel):
            if not flt.match(os.path.basename(path), False, size, mtime):
                continue
            key = os.path.normcase(path)
            if key in seen:
                continue
            seen.add(key)
            by_size[size].append((path, mtime))
            n += 1
            if progress and time.monotonic() - last > 0.2:
                last = time.monotonic()
                progress(f"Elenco file… {n} trovati")
    if cancel():
        return None

    candidates = [(s, fl) for s, fl in by_size.items() if len(fl) > 1]
    total = sum(len(fl) for _, fl in candidates)
    done = 0
    groups: list[DupGroup] = []
    for size, files in candidates:
        by_partial: dict[bytes, list] = defaultdict(list)
        for f in files:
            if cancel():
                return None
            h = _hash(f[0], PARTIAL, cancel)
            done += 1
            if h is not None:
                by_partial[h].append(f)
            if progress and time.monotonic() - last > 0.2:
                last = time.monotonic()
                progress(f"Confronto contenuti… {done}/{total}")
        for same in by_partial.values():
            if len(same) < 2:
                continue
            if size <= PARTIAL * 2:  # già letto per intero
                groups.append(DupGroup(size, same))
                continue
            by_full: dict[bytes, list] = defaultdict(list)
            for f in same:
                h = _hash(f[0], None, cancel)
                if cancel():
                    return None
                if h is not None:
                    by_full[h].append(f)
            groups += [DupGroup(size, g) for g in by_full.values() if len(g) > 1]
    groups.sort(key=lambda g: g.wasted, reverse=True)
    return groups
