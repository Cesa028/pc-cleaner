@echo off
rem Crea l'installer UNICO installer\PCCleaner-Setup-x.y.z.exe (Windows 32 e 64 bit, richiede Inno Setup 6).
rem Costruisce dist\PCCleaner (64 bit); poi, se PY32 e' impostato (python.exe a 32 bit con tkinter),
rem richiama build_installer_x86.bat per rifare dist_x86\PCCleaner. Se PY32 non c'e', usa dist_x86 esistente.
cd /d "%~dp0"
if not exist .venv python -m venv .venv
if errorlevel 1 goto :fail
.venv\Scripts\python -c "import customtkinter, send2trash, PIL, PyInstaller" >nul 2>&1
if errorlevel 1 (
    .venv\Scripts\python -m pip install -r requirements.txt
    if errorlevel 1 goto :fail
)
.venv\Scripts\python make_icon.py
.venv\Scripts\python make_icons.py
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onedir --windowed --name PCCleaner ^
    --icon assets\icon.ico --add-data "assets;assets" --add-data "LICENSE.txt;." --add-data "licenses;licenses" --collect-data customtkinter main.py
if errorlevel 1 goto :fail

if not "%PY32%"=="" (
    call build_installer_x86.bat
    if errorlevel 1 goto :fail
)
if not exist dist_x86\PCCleaner\PCCleaner.exe (
    echo Manca dist_x86\PCCleaner: imposta PY32 e rilancia, oppure esegui build_installer_x86.bat.
    goto :fail
)

set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo Inno Setup 6 non trovato: scaricalo da https://jrsoftware.org/isdl.php
    goto :fail
)
%ISCC% installer.iss
if errorlevel 1 goto :fail
echo.
echo Fatto: cartella installer\
exit /b 0

:fail
echo Errore durante la creazione dell'installer. Controlla la connessione a Internet e riprova.
exit /b 1
