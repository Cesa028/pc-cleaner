# PC Cleaner

**Libera spazio su disco in modo sicuro: pulizia, analisi dello spazio, duplicati e avvio automatico in un'unica app per Windows.**

PC Cleaner (nel progetto: *PulisciPC*) ti aiuta a recuperare spazio su Windows 10/11 (64 bit) senza rischi inutili: analizza prima di eliminare, chiede sempre conferma e, dove possibile, sposta i file nel Cestino invece di cancellarli. Funziona anche senza diritti di amministratore.

![Licenza MIT](https://img.shields.io/badge/licenza-MIT-green) ![Piattaforma](https://img.shields.io/badge/piattaforma-Windows%2010%2F11-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)

---

## Indice

- [Download](#download)
- [Funzionalità](#funzionalità)
- [Sicurezza](#sicurezza)
- [Eseguire dal codice sorgente](#eseguire-dal-codice-sorgente)
- [Creare l'installer](#creare-linstaller)
- [Struttura del progetto](#struttura-del-progetto)
- [Documentazione](#documentazione)
- [Licenza](#licenza)
- [English summary](#english-summary)

---

## Download

L'installer per Windows è nella sezione **[Releases](../../releases/latest)**: scarica `PCCleaner-Setup-1.2.0.exe` ed eseguilo.

Per Windows a 32 bit (x86) c'è `PCCleaner-Setup-1.2.0-32bit.exe`: stesse funzioni, stessa licenza. PC Cleaner usa CustomTkinter/tkinter, che esistono anche a 32 bit; Prisma e Audio Extractor usano Qt 6, che non ha build a 32 bit per Windows, quindi per loro esiste solo la versione a 64 bit.

## Funzionalità

- **Panoramica**: spazio occupato da ogni disco con barre colorate, contenuto del Cestino e accesso rapido alle altre sezioni.
- **Pulizia**: elimina file temporanei, cache e rifiuti di sistema, con analisi preventiva dello spazio recuperabile.
  - *Sistema*: temp utente e di Windows, miniature, cache Internet, dump e segnalazioni errori, Windows Update, log.
  - *Browser*: solo la cache di Chrome, Edge, Brave, Vivaldi, Opera/GX e Firefox (cronologia, password e cookie restano intatti).
  - *Applicazioni*: Discord, Spotify, Steam, Teams, VS Code, Office.
  - *Giochi e grafica*: cache shader DirectX, NVIDIA, AMD e Intel.
  - *Sviluppo*: cache di pip, npm/pnpm/yarn e NuGet.
- **Analisi spazio**: dimensione di ogni cartella, navigabile con doppio clic, e classifica dei 1.000 file più grandi.
- **Filtri avanzati** (analisi e duplicati): nome con caratteri jolly (ad esempio `*.pdf`), estensioni, tipo, data di modifica, dimensione minima e ordinamento.
- **Duplicati**: confronto per contenuto tramite hash (BLAKE2b) in tre passaggi progressivi; almeno una copia di ogni file resta sempre al suo posto.
- **Avvio automatico**: elenco dei programmi che partono con Windows, con attivazione e disattivazione reversibili, come in Gestione attività.
- **Riavvio come amministratore** con un clic, per sbloccare le pulizie delle cartelle di sistema.

### Novità della versione 1.2.0

- **Tema Chiaro / Scuro / Sistema**: di default segue il tema di Windows (anche mentre l'app è aperta); la scelta è salvata.
- **Impostazioni persistenti** in `%LOCALAPPDATA%\PC Cleaner\impostazioni.json`: tema, dimensione e posizione della finestra (ripristinata dentro lo schermo), barra laterale compressa, ultima pagina e ultimo disco analizzato.
- **Contrasto WCAG AA** (almeno 4,5:1) per tutti i testi, anche sui pulsanti verdi e rossi (verifica con `contrast_check.py`).
- **Finestra Informazioni** (pulsante nella barra laterale o `F1`) con versione, licenza MIT, componenti di terze parti, sito del progetto e cartella dei dati.
- **Tastiera e focus visibile**: `Tab` raggiunge tutti i controlli, con un anello blu sul controllo attivo; `Spazio` e `Invio` li attivano.
- **Suggerimenti (tooltip)** con la scorciatoia e il motivo per cui un pulsante è disattivato.
- **Stati vuoti** con spiegazione e pulsante d'azione nelle liste di Analisi spazio, Duplicati e Avvio automatico; **progresso reale** nella Pulizia (barra determinata) e testo di ciò che sta facendo nelle altre scansioni.
- **Errori in italiano comprensibile**; il dettaglio tecnico finisce nel registro attività.

### Scorciatoie da tastiera

| Tasto | Azione |
|---|---|
| `Ctrl+1` … `Ctrl+5` | Panoramica, Pulizia, Analisi spazio, Duplicati, Avvio automatico |
| `F5` | Analizza / Aggiorna nella pagina corrente |
| `Esc` | Annulla l'operazione in corso |
| `Ctrl+B` | Comprimi / espandi la barra laterale |
| `F1` | Informazioni |

## Sicurezza

- Prima si **analizza**, poi si elimina solo ciò che hai selezionato e confermato.
- Analisi spazio e duplicati spostano i file nel **Cestino**, quindi sono recuperabili.
- I collegamenti simbolici e le junction non vengono seguiti; i file presenti solo nel cloud (OneDrive e simili) non vengono letti.
- Cartelle di sistema e radici dei dischi sono protette.
- Ogni operazione è registrata in `%LOCALAPPDATA%\PC Cleaner\registro.txt`.

## Eseguire dal codice sorgente

Requisiti: **Python 3.10 o superiore**.

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

## Creare l'installer

```bat
build.bat             :: genera le icone e compila dist\PCCleaner\ con PyInstaller
build_installer.bat   :: crea installer\PCCleaner-Setup-<versione>.exe (richiede Inno Setup 6)
build_installer_x86.bat :: versione a 32 bit: serve un Python a 32 bit con tkinter, indicato con `set PY32=C:\...\python.exe`;
                         usa build_x86\ e dist_x86\ e crea installer\PCCleaner-Setup-<versione>-32bit.exe (ISCC /DX86=1)
```

Le icone dell'interfaccia (`assets\icons`) si rigenerano con `make_icons.py`, che usa il font di sistema *Segoe MDL2 Assets*.

## Struttura del progetto

```
PulisciPC/
├─ main.py               avvio: DPI awareness e lancio dell'interfaccia
├─ pulisci/
│  ├─ app.py             finestra principale e pagine
│  ├─ ui.py              componenti grafici condivisi (colori, tooltip, focus, stati vuoti)
│  ├─ settings.py        impostazioni persistenti (JSON)
│  ├─ dialogs.py         finestra Informazioni e visualizzatore di testo
│  ├─ utils.py           formattazione, amministratore/UAC, dischi, Cestino, percorsi protetti, log
│  ├─ cleaner.py         categorie di pulizia, scansione, cancellazione
│  ├─ analyzer.py        albero delle dimensioni e file più grandi
│  ├─ filters.py         filtri e ordinamento
│  ├─ duplicates.py      ricerca dei duplicati
│  └─ startup.py         gestione dell'avvio automatico
├─ assets/               icone dell'applicazione
├─ installer.iss         script Inno Setup
└─ licenses/             licenze dei componenti di terze parti
```

## Documentazione

La guida completa all'uso e al funzionamento interno è in [`DOCUMENTAZIONE.md`](DOCUMENTAZIONE.md).

## Licenza

Il codice di PC Cleaner è rilasciato con licenza **MIT** (vedi [`LICENSE.txt`](LICENSE.txt)), © 2026 Cesa028. I componenti di terze parti (customtkinter, send2trash, Pillow, PyInstaller, Python) e le relative licenze sono elencati in [`licenses/THIRD-PARTY-NOTICES.txt`](licenses/THIRD-PARTY-NOTICES.txt).

---

## English summary

**PC Cleaner** is a Windows 10/11 (64-bit) disk-space utility: it cleans temp files and browser/app/GPU/dev caches (analyze first, then delete), shows folder sizes and the 1,000 largest files, finds duplicate files by content hash, and manages startup programs reversibly. Destructive actions ask for confirmation and file-level operations go to the Recycle Bin. Run from source with Python 3.10+: `pip install -r requirements.txt`, then `python main.py`. Released under the MIT license.
