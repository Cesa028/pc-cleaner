import ctypes
import sys

if sys.platform != "win32":
    sys.exit("PC Cleaner funziona solo su Windows.")

try:  # nitidezza su schermi ad alta risoluzione
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

from pulisci.app import main  # noqa: E402

if __name__ == "__main__":
    main()
