"""Pulizia di file temporanei e cache.

Ogni categoria produce una lista di "bersagli" (cartelle o file con pattern).
La scansione non cancella nulla: calcola solo cosa verrebbe rimosso.
La pulizia elimina solo i file trovati in scansione, saltando quelli in uso.
"""
from __future__ import annotations

import fnmatch
import os
import stat
import time
import winreg
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .utils import empty_recycle_bin, env, expand, log, recycle_bin_info


@dataclass
class Target:
    path: str
    pattern: str | None = None   # se presente: solo i file che combaciano, non ricorsivo
    recursive: bool = True


@dataclass
class Category:
    id: str
    group: str
    name: str
    desc: str
    targets: Callable[[], list[Target]]
    admin: bool = False
    default: bool = True
    min_age_h: float = 0
    procs: tuple[str, ...] = ()
    special: str | None = None   # "recycle" per il cestino


@dataclass
class ScanResult:
    cat: Category
    files: list[tuple[str, int]] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)
    size: int = 0
    count: int = 0
    note: str = ""


# ------------------------------------------------------------------ helper percorsi
def _p(*parts: str) -> str:
    return expand(os.path.join(*parts))


def _dirs(*paths: str) -> list[Target]:
    return [Target(p) for p in paths if p and os.path.isdir(p)]


def _chromium(user_data: str, extra_dirs: Iterable[str] = ()) -> list[Target]:
    """Cache di un browser basato su Chromium (tutti i profili)."""
    out: list[Target] = []
    if not os.path.isdir(user_data):
        return out
    try:
        entries = list(os.scandir(user_data))
    except OSError:
        return out
    for e in entries:
        if not e.is_dir(follow_symlinks=False):
            continue
        n = e.name
        if n == "Default" or n.startswith("Profile ") or n in ("Guest Profile", "System Profile"):
            for sub in ("Cache", "Code Cache", "GPUCache", "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache",
                        os.path.join("Service Worker", "CacheStorage"), os.path.join("Service Worker", "ScriptCache")):
                out += _dirs(os.path.join(e.path, sub))
    for sub in ("ShaderCache", "GrShaderCache", "GraphiteDawnCache", *extra_dirs):
        out += _dirs(os.path.join(user_data, sub))
    return out


def _firefox() -> list[Target]:
    out: list[Target] = []
    for base in (_p("%LOCALAPPDATA%", "Mozilla", "Firefox", "Profiles"),
                 _p("%LOCALAPPDATA%", "Waterfox", "Profiles"),
                 _p("%LOCALAPPDATA%", "zen", "Profiles")):
        if os.path.isdir(base):
            for e in os.scandir(base):
                if e.is_dir(follow_symlinks=False):
                    out += _dirs(os.path.join(e.path, "cache2"), os.path.join(e.path, "startupCache"),
                                 os.path.join(e.path, "thumbnails"))
    return out


def _opera() -> list[Target]:
    out: list[Target] = []
    for name in ("Opera Stable", "Opera GX Stable", "Opera Air Stable"):
        local = _p("%LOCALAPPDATA%", "Opera Software", name)
        roam = _p("%APPDATA%", "Opera Software", name)
        out += _dirs(os.path.join(local, "Cache"), os.path.join(roam, "Code Cache"), os.path.join(roam, "GPUCache"),
                     os.path.join(roam, "ShaderCache"))
        out += _chromium(roam)
    return out


def _electron(base: str) -> list[Target]:
    return _dirs(*(os.path.join(base, s) for s in ("Cache", "Code Cache", "GPUCache", "DawnCache",
                                                   "DawnGraphiteCache", "DawnWebGPUCache")))


def _steam() -> list[Target]:
    paths = []
    for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),):
        try:
            with winreg.OpenKey(hive, key) as k:
                sp = winreg.QueryValueEx(k, "SteamPath")[0]
                paths.append(os.path.normpath(sp))
        except OSError:
            pass
    out = _dirs(_p("%LOCALAPPDATA%", "Steam", "htmlcache"))
    for sp in paths:
        out += _dirs(os.path.join(sp, "appcache", "httpcache"), os.path.join(sp, "logs"),
                     os.path.join(sp, "dumps"))
    return out


# ------------------------------------------------------------------ categorie
def build_categories() -> list[Category]:
    W = env("SystemRoot") or r"C:\Windows"
    PD = env("ProgramData") or r"C:\ProgramData"
    LA = "%LOCALAPPDATA%"
    RA = "%APPDATA%"
    cats = [
        # ---------------- Sistema
        Category("user_temp", "Sistema", "File temporanei utente",
                 "Cartella %TEMP%. Salta i file usati nelle ultime 24 ore.",
                 lambda: _dirs(expand("%TEMP%")), min_age_h=24),
        Category("win_temp", "Sistema", "File temporanei di Windows",
                 "C:\\Windows\\Temp. Salta i file usati nelle ultime 24 ore.",
                 lambda: _dirs(os.path.join(W, "Temp")), admin=True, min_age_h=24),
        Category("recycle", "Sistema", "Cestino",
                 "Svuota il cestino di tutti i dischi.", lambda: [], special="recycle"),
        Category("thumbs", "Sistema", "Cache miniature",
                 "Anteprime delle immagini in Esplora file: vengono rigenerate.",
                 lambda: [Target(_p(LA, "Microsoft", "Windows", "Explorer"), "thumbcache_*.db"),
                          Target(_p(LA, "Microsoft", "Windows", "Explorer"), "iconcache_*.db")]),
        Category("inetcache", "Sistema", "Cache Internet di Windows",
                 "INetCache usata da componenti di sistema e app vecchie.",
                 lambda: _dirs(_p(LA, "Microsoft", "Windows", "INetCache"))),
        Category("dumps", "Sistema", "Dump di arresti anomali dei programmi",
                 "File creati quando un programma va in crash.",
                 lambda: _dirs(_p(LA, "CrashDumps"))),
        Category("sysdumps", "Sistema", "Dump di arresti anomali di Windows",
                 "File creati dalle schermate blu e dai blocchi dei driver.",
                 lambda: _dirs(os.path.join(W, "Minidump"), os.path.join(W, "LiveKernelReports"))
                 + ([Target(W, "MEMORY.DMP")] if os.path.isfile(os.path.join(W, "MEMORY.DMP")) else []),
                 admin=True),
        Category("wer", "Sistema", "Segnalazione errori di Windows",
                 "Rapporti di errore già inviati o in coda.",
                 lambda: _dirs(_p(LA, "Microsoft", "Windows", "WER", "ReportArchive"),
                               _p(LA, "Microsoft", "Windows", "WER", "ReportQueue"),
                               os.path.join(PD, "Microsoft", "Windows", "WER", "ReportArchive"),
                               os.path.join(PD, "Microsoft", "Windows", "WER", "ReportQueue"),
                               os.path.join(PD, "Microsoft", "Windows", "WER", "Temp"))),
        Category("winupdate", "Sistema", "Download di Windows Update",
                 "Pacchetti di aggiornamento già installati. Sicuro, ma esegui dopo aver riavviato il PC.",
                 lambda: _dirs(os.path.join(W, "SoftwareDistribution", "Download")), admin=True, default=False,
                 min_age_h=72),
        Category("delivery", "Sistema", "Ottimizzazione recapito",
                 "Cache dei download di aggiornamenti condivisi.",
                 lambda: _dirs(os.path.join(W, "ServiceProfiles", "NetworkService", "AppData", "Local",
                                            "Microsoft", "Windows", "DeliveryOptimization", "Cache")),
                 admin=True),
        Category("winlogs", "Sistema", "Log di Windows",
                 "File di log di installazioni e componenti (più vecchi di 7 giorni).",
                 lambda: [Target(os.path.join(W, "Logs", "CBS"), "*.log"), Target(os.path.join(W, "Logs", "CBS"), "*.cab"),
                          Target(os.path.join(W, "Logs", "DISM"), "*.log"),
                          Target(os.path.join(W, "Panther"), "*.log")],
                 admin=True, default=False, min_age_h=24 * 7),

        # ---------------- Browser
        Category("chrome", "Browser", "Google Chrome", "Cache (cronologia, password e cookie restano).",
                 lambda: _chromium(_p(LA, "Google", "Chrome", "User Data")), procs=("chrome.exe",)),
        Category("edge", "Browser", "Microsoft Edge", "Cache (cronologia, password e cookie restano).",
                 lambda: _chromium(_p(LA, "Microsoft", "Edge", "User Data")), procs=("msedge.exe",)),
        Category("brave", "Browser", "Brave", "Cache (cronologia, password e cookie restano).",
                 lambda: _chromium(_p(LA, "BraveSoftware", "Brave-Browser", "User Data")), procs=("brave.exe",)),
        Category("vivaldi", "Browser", "Vivaldi", "Cache (cronologia, password e cookie restano).",
                 lambda: _chromium(_p(LA, "Vivaldi", "User Data")), procs=("vivaldi.exe",)),
        Category("opera", "Browser", "Opera / Opera GX", "Cache (cronologia, password e cookie restano).",
                 _opera, procs=("opera.exe",)),
        Category("firefox", "Browser", "Firefox", "Cache (cronologia, password e cookie restano).",
                 _firefox, procs=("firefox.exe",)),

        # ---------------- Applicazioni
        Category("discord", "Applicazioni", "Discord", "Cache di immagini e video.",
                 lambda: _electron(_p(RA, "discord")) + _electron(_p(RA, "discordptb")) + _electron(_p(RA, "discordcanary")),
                 procs=("discord.exe",)),
        Category("spotify", "Applicazioni", "Spotify", "Brani in cache per l'ascolto (non quelli scaricati offline).",
                 lambda: _dirs(_p(LA, "Spotify", "Data"), _p(LA, "Spotify", "Browser", "Cache")),
                 procs=("spotify.exe",)),
        Category("steam", "Applicazioni", "Steam", "Cache web del client, log e dump.",
                 _steam, procs=("steam.exe", "steamwebhelper.exe")),
        Category("teams", "Applicazioni", "Microsoft Teams", "Cache del client.",
                 lambda: _electron(_p(RA, "Microsoft", "Teams"))
                 + _dirs(_p(LA, "Packages", "MSTeams_8wekyb3d8bbwe", "LocalCache", "Microsoft", "MSTeams", "EBWebView",
                            "Default", "Cache")),
                 procs=("ms-teams.exe", "teams.exe")),
        Category("vscode", "Applicazioni", "Visual Studio Code", "Cache dell'editor.",
                 lambda: _electron(_p(RA, "Code")) + _dirs(_p(RA, "Code", "CachedData"), _p(RA, "Code", "CachedExtensionVSIXs")),
                 procs=("code.exe",)),
        Category("office", "Applicazioni", "Microsoft Office", "Cache dei documenti di Office.",
                 lambda: _dirs(_p(LA, "Microsoft", "Office", "16.0", "OfficeFileCache"),
                               _p(LA, "Microsoft", "Office", "OTele")),
                 procs=("winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe")),

        # ---------------- Giochi e grafica
        Category("dxcache", "Giochi e grafica", "Cache shader DirectX",
                 "Si ricrea da sola; il primo avvio dei giochi può essere più lento.",
                 lambda: _dirs(_p(LA, "D3DSCache")), default=False),
        Category("nvidia", "Giochi e grafica", "Cache shader NVIDIA",
                 "Si ricrea da sola; il primo avvio dei giochi può essere più lento.",
                 lambda: _dirs(_p(LA, "NVIDIA", "DXCache"), _p(LA, "NVIDIA", "GLCache"), _p(LA, "NVIDIA", "OptixCache"),
                               os.path.join(PD, "NVIDIA Corporation", "NV_Cache")), default=False),
        Category("amd", "Giochi e grafica", "Cache shader AMD",
                 "Si ricrea da sola; il primo avvio dei giochi può essere più lento.",
                 lambda: _dirs(_p(LA, "AMD", "DxCache"), _p(LA, "AMD", "DxcCache"), _p(LA, "AMD", "VkCache"),
                               _p(LA, "AMD", "GLCache")), default=False),
        Category("intelgfx", "Giochi e grafica", "Cache shader Intel",
                 "Si ricrea da sola.",
                 lambda: _dirs(_p(LA, "Intel", "ShaderCache"), _p("%USERPROFILE%", "AppData", "LocalLow", "Intel", "ShaderCache")),
                 default=False),

        # ---------------- Sviluppo
        Category("pip", "Sviluppo", "Cache di pip (Python)", "Pacchetti scaricati: verranno riscaricati se servono.",
                 lambda: _dirs(_p(LA, "pip", "cache"), _p(LA, "pip", "Cache")), default=False),
        Category("npm", "Sviluppo", "Cache di npm / pnpm / yarn", "Pacchetti scaricati: verranno riscaricati se servono.",
                 lambda: _dirs(_p(LA, "npm-cache"), _p(LA, "pnpm-cache"), _p(LA, "Yarn", "Cache")), default=False),
        Category("nuget", "Sviluppo", "Cache HTTP di NuGet", "Download temporanei di pacchetti .NET.",
                 lambda: _dirs(_p(LA, "NuGet", "v3-cache"), _p(LA, "NuGet", "plugins-cache")), default=False),
    ]
    return cats


# ------------------------------------------------------------------ scansione
def _is_link(entry: os.DirEntry) -> bool:
    try:
        if entry.is_symlink():
            return True
        is_junction = getattr(entry, "is_junction", None)
        return bool(is_junction and is_junction())
    except OSError:
        return True


CLOUD_ATTRS = 0x1000 | 0x40000 | 0x400000  # OFFLINE | RECALL_ON_OPEN | RECALL_ON_DATA_ACCESS


def is_cloud_only(st: os.stat_result) -> bool:
    """File segnaposto (OneDrive, Collegamento al telefono…): leggerli li scaricherebbe."""
    return bool(getattr(st, "st_file_attributes", 0) & CLOUD_ATTRS)


def _walk_files(root: str, recursive: bool, cancel: Callable[[], bool]):
    stack = [root]
    while stack:
        if cancel():
            return
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if _is_link(e):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        if recursive:
                            stack.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        st = e.stat(follow_symlinks=False)
                        if is_cloud_only(st):
                            continue
                        yield e.path, st.st_size, st.st_mtime
                except OSError:
                    continue


def scan_category(cat: Category, cancel: Callable[[], bool] = lambda: False) -> ScanResult:
    res = ScanResult(cat)
    if cat.special == "recycle":
        res.size, res.count = recycle_bin_info()
        return res
    try:
        targets = cat.targets()
    except Exception as ex:  # una categoria rotta non deve fermare le altre
        res.note = f"errore: {ex}"
        return res
    limit = time.time() - cat.min_age_h * 3600 if cat.min_age_h else None
    seen: set[str] = set()
    for t in targets:
        if not os.path.isdir(t.path):
            continue
        if t.pattern is None:
            res.roots.append(t.path)
        recursive = t.recursive and t.pattern is None
        for path, size, mtime in _walk_files(t.path, recursive, cancel):
            if t.pattern and not fnmatch.fnmatch(os.path.basename(path).lower(), t.pattern.lower()):
                continue
            if limit and mtime > limit:
                continue
            key = os.path.normcase(path)
            if key in seen:
                continue
            seen.add(key)
            res.files.append((path, size))
            res.size += size
    res.count = len(res.files)
    return res


# ------------------------------------------------------------------ pulizia
def _remove_file(path: str) -> bool:
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return True
    except PermissionError:
        try:
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)
            return True
        except OSError:
            return False
    except OSError:
        return False


def _prune_empty_dirs(root: str) -> None:
    """Rimuove le sottocartelle rimaste vuote, mai la cartella radice."""
    def visit(d: str, is_root: bool) -> None:
        try:
            subs = [e.path for e in os.scandir(d) if not _is_link(e) and e.is_dir(follow_symlinks=False)]
        except OSError:
            return
        for s in subs:
            visit(s, False)
        if not is_root:
            try:
                os.rmdir(d)  # fallisce se non è vuota: va bene così
            except OSError:
                pass

    visit(root, True)


def clean_result(res: ScanResult, cancel: Callable[[], bool] = lambda: False) -> tuple[int, int, int]:
    """Ritorna (byte liberati, file eliminati, file saltati)."""
    if res.cat.special == "recycle":
        size, count = recycle_bin_info()
        ok = empty_recycle_bin()
        after, _ = recycle_bin_info()
        freed = max(0, size - after) if ok else 0
        log(f"Cestino: liberati {freed} byte")
        return freed, count if ok else 0, 0 if ok else count
    freed = deleted = skipped = 0
    for path, size in res.files:
        if cancel():
            break
        if _remove_file(path):
            freed += size
            deleted += 1
        else:
            skipped += 1
    for r in res.roots:
        _prune_empty_dirs(r)
    log(f"{res.cat.name}: eliminati {deleted} file ({freed} byte), saltati {skipped}")
    return freed, deleted, skipped
