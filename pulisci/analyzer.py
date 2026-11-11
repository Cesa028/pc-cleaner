"""Analisi dello spazio: dimensione di ogni cartella e file più grandi."""
from __future__ import annotations

import ctypes
import heapq
import os
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Callable

from .cleaner import _is_link, is_cloud_only

_GetCompressedFileSizeW = ctypes.windll.kernel32.GetCompressedFileSizeW
_GetCompressedFileSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
_GetCompressedFileSizeW.restype = wintypes.DWORD
SPARSE_OR_COMPRESSED = 0x200 | 0x800


def disk_size(path: str, st: os.stat_result) -> int:
    """Spazio realmente occupato: i file sparsi/compressi (dischi virtuali di Docker/WSL,
    cartelle compresse NTFS) dichiarano una dimensione più grande di quella reale."""
    if getattr(st, "st_file_attributes", 0) & SPARSE_OR_COMPRESSED:
        high = wintypes.DWORD(0)
        low = _GetCompressedFileSizeW(path, ctypes.byref(high))
        if low != 0xFFFFFFFF or ctypes.GetLastError() == 0:
            return (high.value << 32) | low
    return st.st_size


@dataclass
class DirNode:
    path: str
    size: int = 0
    files: int = 0
    children: list["DirNode"] = field(default_factory=list)
    own_files_size: int = 0
    denied: bool = False


@dataclass
class AnalysisResult:
    root: DirNode
    index: dict[str, DirNode]
    biggest: list[tuple[int, str, float]]   # (size, path, mtime) ordinati dal più grande
    total_files: int
    denied_dirs: int


def analyze(root: str, progress: Callable[[str, int], None] | None = None,
            cancel: Callable[[], bool] = lambda: False, top_n: int = 1000) -> AnalysisResult | None:
    root = os.path.normpath(root)
    heap: list[tuple[int, str, float]] = []
    index: dict[str, DirNode] = {}
    counters = {"files": 0, "denied": 0}
    last = 0.0
    # gli hardlink (molto usati da Windows in WinSxS) vanno contati una volta sola;
    # scandir non fornisce il numero di link, quindi lo leggiamo solo dentro la cartella di Windows
    win_dir = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows")) + "\\"
    seen_links: set[tuple[int, int]] = set()

    # visita iterativa post-ordine (evita il limite di ricorsione su alberi profondi)
    root_node = DirNode(root)
    index[os.path.normcase(root)] = root_node
    stack: list[tuple[DirNode, bool]] = [(root_node, False)]
    while stack:
        if cancel():
            return None
        node, done = stack.pop()
        if done:
            node.size = node.own_files_size + sum(c.size for c in node.children)
            node.files += sum(c.files for c in node.children)
            continue
        stack.append((node, True))
        try:
            it = os.scandir(node.path)
        except OSError:
            node.denied = True
            counters["denied"] += 1
            continue
        with it:
            for e in it:
                try:
                    if _is_link(e):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        child = DirNode(e.path)
                        node.children.append(child)
                        index[os.path.normcase(e.path)] = child
                        stack.append((child, False))
                    elif e.is_file(follow_symlinks=False):
                        st = e.stat(follow_symlinks=False)
                        if is_cloud_only(st):
                            continue
                        size = disk_size(e.path, st)
                        if os.path.normcase(e.path).startswith(win_dir):
                            full = os.stat(e.path, follow_symlinks=False)
                            if full.st_nlink > 1:
                                key = (full.st_dev, full.st_ino)
                                if key in seen_links:
                                    size = 0
                                seen_links.add(key)
                        node.own_files_size += size
                        node.files += 1
                        counters["files"] += 1
                        item = (size, e.path, st.st_mtime)
                        if len(heap) < top_n:
                            heapq.heappush(heap, item)
                        elif size > heap[0][0]:
                            heapq.heapreplace(heap, item)
                except OSError:
                    continue
        if progress and time.monotonic() - last > 0.15:
            last = time.monotonic()
            progress(node.path, counters["files"])
    biggest = sorted(heap, reverse=True)
    return AnalysisResult(root_node, index, biggest, counters["files"], counters["denied"])


def list_dir_entries(node: DirNode) -> list[dict]:
    """Elementi diretti di una cartella: sottocartelle (dai dati dell'analisi) e file letti al volo.
    Ogni elemento ha name, path, size, dir, files, denied, mtime."""
    sub = {os.path.normcase(c.path): c for c in node.children}
    out: list[dict] = []
    try:
        with os.scandir(node.path) as it:
            for e in it:
                try:
                    if _is_link(e):
                        continue
                    st = e.stat(follow_symlinks=False)
                    if e.is_dir(follow_symlinks=False):
                        c = sub.get(os.path.normcase(e.path))
                        if c is None:
                            continue
                        out.append({"path": c.path, "name": e.name, "size": c.size, "dir": True,
                                    "files": c.files, "denied": c.denied, "mtime": st.st_mtime})
                    elif e.is_file(follow_symlinks=False) and not is_cloud_only(st):
                        out.append({"path": e.path, "name": e.name, "size": disk_size(e.path, st),
                                    "dir": False, "files": 1, "denied": False, "mtime": st.st_mtime})
                except OSError:
                    continue
    except OSError:
        pass
    return out


def remove_from_tree(result: AnalysisResult, path: str, size: int, is_dir: bool) -> None:
    """Aggiorna le dimensioni dopo che un elemento è stato spostato nel cestino."""
    key = os.path.normcase(os.path.normpath(path))
    parent_key = os.path.normcase(os.path.dirname(os.path.normpath(path)))
    parent = result.index.get(parent_key)
    if is_dir:
        node = result.index.pop(key, None)
        if parent and node in parent.children:
            parent.children.remove(node)
    elif parent:
        parent.own_files_size -= size
    p = parent_key
    while p in result.index:
        result.index[p].size -= size
        if p == os.path.normcase(result.root.path):
            break
        np_ = os.path.normcase(os.path.dirname(p))
        if np_ == p:
            break
        p = np_
    result.biggest = [b for b in result.biggest
                      if not (os.path.normcase(b[1]) == key or os.path.normcase(b[1]).startswith(key + "\\"))]
