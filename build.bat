@echo off
rem Crea dist\PCCleaner.exe (un solo file, nessuna installazione richiesta)
cd /d "%~dp0"
if not exist .venv python -m venv .venv
if errorlevel 1 goto :fail
rem installa i pacchetti mancanti anche se .venv esiste già (una installazione interrotta lascia la cartella)
.venv\Scripts\python -c "import customtkinter, send2trash, PIL, PyInstaller" >nul 2>&1
if errorlevel 1 (
    .venv\Scripts\python -m pip install -r requirements.txt
    if errorlevel 1 goto :fail
)
.venv\Scripts\python make_icon.py
if errorlevel 1 goto :fail
.venv\Scripts\python make_icons.py
.venv\Scripts\python -m PyInstaller --noconfirm --clean PCCleaner.spec
if errorlevel 1 goto :fail
echo.
echo Fatto: dist\PCCleaner.exe
exit /b 0

:fail
echo.
echo Errore durante la compilazione. Controlla la connessione a Internet e riprova.
exit /b 1
