# PC Cleaner — Documentazione

Versione 1.2.2 · Windows 10/11 a 64 bit · Python 3.13 + customtkinter

---

## Novità

- **1.2.2** · Avvio automatico: la versione a 32 bit su Windows a 64 bit ora mostra lo stesso stato di Gestione attività; per i collegamenti mostra il programma vero e Apri posizione apre il suo file.

---

## 1. Cos'è

PC Cleaner è un'app per Windows che serve a liberare spazio su disco. È **portatile**: un solo file `PCCleaner.exe` da circa 21 MB, che non va installato e parte con un doppio clic su qualunque PC con Windows 10 o 11 a 64 bit.

Funziona anche senza diritti di amministratore. Con il pulsante **«Riavvia come amministratore»** si sbloccano le pulizie delle cartelle di sistema.

---

## 2. Come si usa

### 2.1 Panoramica
- Mostra ogni disco fisso o rimovibile con una barra di occupazione: verde se c'è spazio, arancione oltre il 75%, rossa oltre il 90%.
- Il riquadro **Cestino** mostra quanti elementi contiene e quanto pesano, con il pulsante «Svuota cestino» (chiede conferma).
- **Pulizia rapida** apre la pagina Pulizia e avvia subito l'analisi.
- Tre riquadri in fondo portano direttamente ad Analisi spazio, Duplicati e Avvio automatico.

### 2.2 Pulizia
1. Premi **Analizza**. L'app calcola quanto spazio occupa ogni categoria, **senza cancellare niente**.
2. Spunta le voci che vuoi pulire. «Consigliati» seleziona le voci sicure, mentre «Tutti» e «Nessuno» selezionano o tolgono tutto.
3. Premi **Pulisci**. Compare un riepilogo con il numero di file e lo spazio, e devi confermare.
4. Alla fine l'app dice quanto spazio ha liberato e quanti file ha saltato perché erano in uso, poi rifà l'analisi.

Le categorie:

| Gruppo | Voci | Note |
|---|---|---|
| Sistema | Temp utente, Temp Windows 🔑, Cestino, Cache miniature, Cache Internet, Dump dei programmi, Dump di Windows 🔑, Segnalazione errori, Windows Update 🔑, Ottimizzazione recapito 🔑, Log di Windows 🔑 | Per le cartelle Temp vengono saltati i file modificati nelle ultime 24 ore, per Windows Update quelli delle ultime 72 ore, per i log quelli degli ultimi 7 giorni |
| Browser | Chrome, Edge, Brave, Vivaldi, Opera/GX, Firefox | Solo la **cache**: cronologia, password e cookie restano. Vengono puliti tutti i profili |
| Applicazioni | Discord, Spotify, Steam, Teams, VS Code, Office | Se il programma è aperto compare l'avviso «Chiudi X per pulire tutto» |
| Giochi e grafica | Cache shader DirectX, NVIDIA, AMD, Intel | Non incluse nei Consigliati: dopo la pulizia il primo avvio dei giochi è più lento |
| Sviluppo | pip, npm/pnpm/yarn, NuGet | Non incluse nei Consigliati |

🔑 = richiede l'amministratore. Senza diritti di amministratore la casella è disattivata.

La cancellazione di questa sezione è **definitiva**: i file non passano dal Cestino. Si tratta però solo di cache e file temporanei, che i programmi ricreano da soli.

### 2.3 Analisi spazio
1. Scegli un disco, la cartella utente oppure «Scegli cartella…», poi premi **Analizza**.
2. Vista **Cartelle**: elenco ordinato per dimensione, con quota percentuale e numero di file. Con un doppio clic (o Invio) entri in una cartella; «Su» (o Backspace) torna indietro.
3. Vista **File più grandi**: i 1.000 file più grandi trovati nell'analisi.
4. Il pulsante **Filtri** apre il pannello per trovare file e cartelle per nome (anche con jolly, es. `*.pdf` o `bozza*`), estensione (più estensioni separate da virgola), tipo, data di modifica, dimensione minima e ordinamento. I filtri si applicano subito alla vista attuale, senza rifare l'analisi.
5. Le azioni sono **Apri in Esplora file**, **Copia percorso** (dal menu del tasto destro) e **Sposta nel cestino** (anche con il tasto Canc). Gli elementi vanno nel **Cestino di Windows**, quindi si possono recuperare.

Come vengono calcolate le dimensioni:
- I collegamenti simbolici e le junction non vengono seguiti, così niente viene contato due volte e l'analisi non entra in loop.
- I file sparsi o compressi, come i dischi virtuali di Docker e WSL, vengono contati con lo spazio che occupano davvero sul disco.
- Gli hardlink dentro `C:\Windows` (WinSxS) vengono contati una volta sola.
- I file di OneDrive o Collegamento al telefono che stanno solo in cloud vengono ignorati.

### 2.4 Duplicati
1. Nel riquadro in alto ci sono le cartelle da controllare, una per riga. Di base sono Desktop, Documenti, Download, Immagini, Musica, Video e le cartelle OneDrive. Puoi aggiungerne con «Aggiungi cartella» o tornare all'elenco di base con «Ripristina».
2. Nel pannello **Filtri** scegli, se vuoi, la dimensione minima (di base 1 MB), il nome, le estensioni o la data. I filtri si applicano alla ricerca successiva, quindi impostali prima di premere **Cerca duplicati**.
3. Il confronto avviene in tre passaggi: stessa dimensione, poi impronta (hash) dell'inizio e della fine del file, poi hash dell'intero file (BLAKE2b). Vengono segnalati solo i file con **contenuto identico**.
4. Per selezionare un file clicca la casella ☐ o premi Spazio. «Tieni il più recente» e «Tieni il più vecchio» selezionano in automatico tutte le copie tranne una.
5. **Sposta selezionati nel cestino**: anche se le selezioni tutte, almeno una copia di ogni file resta sempre.

### 2.5 Avvio automatico
- Elenca i programmi che partono con Windows. Le fonti sono il registro (`Run` dell'utente, `Run` per tutti gli utenti, `Run` a 32 bit) e le cartelle Esecuzione automatica.
- Le chiavi di registro vengono lette con viste WOW64 esplicite (64 e 32 bit), così anche la versione a 32 bit su Windows a 64 bit legge `Run` e `StartupApproved` nella vista giusta e mostra lo stesso stato di Gestione attività.
- Per i collegamenti (`.lnk`) la destinazione vera viene risolta con una chiamata PowerShell (in cache): la colonna Comando mostra il programma vero e «Apri posizione» apre la sua cartella con il file selezionato.
- **Disattiva** e **Attiva** usano lo stesso meccanismo di Gestione attività (le chiavi `StartupApproved`): non cancellano niente, sono sempre reversibili e Windows mostra lo stesso stato.
- Le voci «tutti gli utenti» richiedono l'amministratore.
- «Apri posizione» apre il file eseguibile (per un collegamento, quello di destinazione). Se l'eseguibile non esiste più, di solito è un avvio rimasto da un programma disinstallato.

---

## 3. Struttura del codice

```
PulisciPC/
├─ main.py              avvio: DPI awareness + lancio dell'interfaccia
├─ pulisci/
│  ├─ utils.py          formattazione, admin/UAC, dischi, cestino (API shell32), processi, percorsi protetti, log
│  ├─ cleaner.py        definizione categorie, scansione, cancellazione
│  ├─ analyzer.py       albero delle dimensioni, file più grandi, elenco di una cartella, aggiornamento dopo il cestino
│  ├─ filters.py        filtri (nome, estensione, tipo, data, dimensione) e ordinamento, usati da analisi e duplicati
│  ├─ duplicates.py     ricerca duplicati a 3 livelli di hash
│  ├─ startup.py        lettura e scrittura dell'avvio automatico (registro + cartelle)
│  ├─ ui.py             colori, icone, pulsanti, tabelle, barra dei filtri, tooltip, focus da tastiera, stati vuoti
│  ├─ settings.py       impostazioni persistenti (tema, finestra, ultima pagina e disco) in JSON, scrittura atomica
│  ├─ dialogs.py        finestra Informazioni (F1) e visualizzatore di licenza e componenti di terze parti
│  └─ app.py            finestra, barra laterale e una classe per pagina (creata al primo utilizzo)
├─ assets/              logo (icon.png/icon.ico) e icone dell'interfaccia (icons/)
├─ make_icon.py         genera assets/icon.ico (solo in fase di build)
├─ make_icons.py        genera assets/icons/*.png dal font Segoe MDL2 Assets (solo in fase di build)
├─ build.bat            crea dist/PCCleaner.exe con PyInstaller (--onefile --windowed)
└─ README.md
```

Punti chiave:
- **Lavoro in background.** Le operazioni lunghe girano in un thread (`App.run_bg`). Il thread non tocca mai l'interfaccia: passa i comandi a una coda (`App.ui` / `App.set_text`), che il thread dell'interfaccia svuota ogni 60 ms.
- **Pagine pigre.** Ogni pagina viene creata solo quando la apri la prima volta, così l'avvio è più rapido.
- **Filtri.** Un solo oggetto `Filters` (in `filters.py`) decide cosa mostrare o analizzare; la stessa barra (`ui.FilterBar`) è usata in Analisi spazio e Duplicati.
- **Annullamento.** Ogni operazione lunga riceve una funzione `cancel()` che controlla un flag impostato dal pulsante «Annulla».
- **Aggiungere una categoria di pulizia.** Basta aggiungere un `Category(...)` in `cleaner.build_categories()`. I campi `targets` (funzione che restituisce le cartelle o i pattern), `admin`, `default`, `min_age_h` e `procs` coprono tutti i casi attuali.
- **Impostazioni.** `settings.Settings` legge e scrive `%LOCALAPPDATA%\PC Cleaner\impostazioni.json` (scrittura atomica, errori ignorati). Salva tema, finestra, barra laterale, ultima pagina e ultimo disco di Analisi spazio.
- **Tastiera.** Ctrl+1…5 (pagine), F5 (analizza/aggiorna), Esc (annulla), Ctrl+B (barra laterale), F1 (Informazioni). `ui.a11y_pass` rende ogni pulsante CustomTkinter raggiungibile con Tab, con anello di focus e attivazione con Spazio/Invio.
- **Simboli nelle tabelle.** Le caselle di selezione dei duplicati e i pallini dello stato dell'avvio automatico sono immagini disegnate con Pillow (`ui.table_image`), non caratteri Unicode. Restano solo i segni tipografici nei testi (… · — •).
- **Registro.** Ogni eliminazione, spostamento nel cestino e modifica dell'avvio viene scritta in `%LOCALAPPDATA%\PC Cleaner\registro.txt`.
### Ricompilare
Fai doppio clic su `build.bat`. Se manca, crea il `.venv` e installa `customtkinter`, `send2trash`, `pillow` e `pyinstaller`. Il risultato è `dist\PCCleaner.exe`. Per l'installer unico (Windows 32 e 64 bit, sceglie da solo la build giusta) usa `build_installer.bat`: include `dist\PCCleaner` (64 bit) e `dist_x86\PCCleaner` (32 bit, costruita da `build_installer_x86.bat`; con `set PY32=...` viene rifatta in automatico) e produce `installer\PCCleaner-Setup-<versione>.exe`. Le icone dell'interfaccia sono già in `assets\icons`; si rigenerano con `make_icons.py` solo se cambi i glifi.

---

## 4. Criticità da sistemare

Ordinate per importanza.

### 4.1 Da verificare: mai provate sul serio
1. **Pulizia vera dall'interfaccia.** La cancellazione è stata provata solo su una cartella di prova (file normali, file bloccato, junction). Non è mai stata eseguita sulle categorie reali.
2. **«Sposta nel cestino»** (Analisi spazio e Duplicati) non è mai stato premuto su file veri.
3. **Attiva/Disattiva avvio automatico** non è stato provato: va verificato che Gestione attività mostri lo stesso stato.
4. **Modalità amministratore** non è stata provata: riavvio con UAC, categorie sbloccate, voci HKLM.
5. **Altri PC.** È stato provato solo sul PC di sviluppo: niente Windows 10, schermi con DPI diversi o account non amministratori.

### 4.2 Sicurezza e affidabilità
6. **Duplicati dentro cartelle di programmi.** L'app non sa se un file serve a un programma. Se l'utente aggiunge cartelle come `Program Files` o `AppData`, potrebbe spostare nel cestino DLL o asset necessari. Soluzione: bloccare o avvisare per le cartelle di sistema e dei programmi in `DupPage`.
7. **Pulizia basata sulla scansione precedente.** Se tra l'analisi e la pulizia un programma ricrea un file con lo stesso percorso, il nuovo file viene eliminato. Il rischio è basso perché si tratta di cache, ma si potrebbe ricontrollare data e dimensione prima di cancellare.
8. **Percorsi protetti incompleti.** `protected_path()` blocca solo le radici dei dischi, `Windows`, `Program Files`, `ProgramData` e la cartella utente stessa. Le sottocartelle di `Program Files` o di `AppData` si possono spostare nel cestino. Valutare almeno un avviso.
9. **Conteggio dei file saltati poco chiaro.** «Segnalazione errori» non è marcata come amministratore, ma include cartelle di `ProgramData`: senza amministratore quei file finiscono tra i «saltati». Meglio dividerla in due categorie, come già fatto per i dump.
10. **Cache miniature.** Esplora file tiene quasi sempre aperti i file `thumbcache_*.db`, quindi vengono saltati e lo spazio mostrato non viene liberato davvero. Soluzioni: avvisare, oppure riavviare explorer (invasivo).
11. **Windows Update.** Cancella la cartella `Download` senza fermare il servizio `wuauserv`. Di solito funziona, ma la procedura corretta è fermare il servizio, pulire e riavviarlo.

### 4.3 Precisione e prestazioni
12. **Hardlink fuori da `C:\Windows`.** Vengono ancora contati più volte, ad esempio nello store di pnpm o nei backup con hardlink. Il controllo è limitato a `C:\Windows` perché leggere il numero di link richiede una lettura in più per ogni file, che è lenta.
13. **Analisi di un disco intero.** Su C: impiega circa 80 secondi per 1,3 milioni di file e tiene in memoria tutte le cartelle. La barra di stato mostra solo testo, senza percentuale. Possibili miglioramenti: lettura della MFT, che però richiede l'amministratore, oppure risultati parziali mostrati durante la scansione.
14. **Duplicati su HDD.** Leggere per intero file grandi con la stessa dimensione è lento. Vengono mostrati e selezionati in automatico solo i **primi 500 gruppi**: quelli oltre non sono visibili.
15. **«File più grandi».** Ora sono i primi 1.000 e hanno filtri per nome, estensione, tipo, data e dimensione. Restano fuori dall'elenco i file più piccoli dei primi 1.000: per trovarli serve un'analisi più mirata.
16. **Risultati non aggiornati.** Dopo lo spostamento nel cestino le dimensioni vengono aggiornate a mano. Le modifiche fatte fuori dall'app invece non si vedono finché non rianalizzi.

### 4.4 Interfaccia
17. **DPI.** La scala delle tabelle (altezza righe, larghezza colonne) viene calcolata una volta all'avvio. Se sposti la finestra su un monitor con DPI diverso, le tabelle non si adattano.
18. **Tema.** Risolto dalla 1.2.0: scelta Chiaro / Scuro / Sistema salvata in `impostazioni.json` e riletta all'avvio; con «Sistema» il tema di Windows (chiave `AppsUseLightTheme`) viene riletto ogni 2,5 secondi. Le tabelle `ttk` vengono ricolorate a mano al cambio.
19. **Elenco cartelle dei duplicati.** È un campo di testo libero: i percorsi inesistenti vengono ignorati senza avviso.
20. **Icone.** Risolto: le emoji sono sostituite da icone PNG monocromatiche (`assets/icons`), generate dal font di sistema Segoe MDL2 Assets.
21. **Lingua.** Solo italiano, con testi scritti direttamente nel codice.

### 4.5 Distribuzione
22. **Exe senza firma digitale.** Windows SmartScreen mostra «PC protetto» e alcuni antivirus segnalano per errore gli exe creati con PyInstaller in modalità onefile. Soluzioni: firma con certificato, oppure build `--onedir` (segnalata meno spesso).
23. **Avvio lento.** La modalità onefile estrae i file in `%TEMP%\_MEI…` a ogni avvio, quindi l'app impiega 1–3 secondi a partire. Se l'app viene chiusa male, le cartelle `_MEI` restano in `%TEMP%`; la pulizia «Temp utente» le elimina dopo 24 ore.
24. **Compatibilità.** Python 3.13 richiede Windows 10 o successivo, a 64 bit. Su Windows 7/8 o a 32 bit non parte.
25. **Variabili di debug.** Risolto: `PULISCI_PAGE` e `PULISCI_SCAN` sono state rimosse.

### 4.6 Funzioni mancanti (idee)
- Avvio automatico: mancano le **attività pianificate**, i **servizi** e le app dello Store (`StartupTask`).
- Disinstallazione dei programmi con indicazione dello spazio che occupano.
- Pulizia dei vecchi punti di ripristino e di `Windows.old`.
- Anteprima dei file di una categoria prima di pulire (oggi si vede solo il totale).
- Pulizia programmata e salvataggio delle preferenze (categorie scelte, cartelle dei duplicati).
- Test automatici (pytest) per `cleaner`, `analyzer` e `duplicates` su cartelle di prova.
- Repository git: il progetto non è ancora sotto controllo di versione.
