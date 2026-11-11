@echo off
rem Crea installer\PCCleaner-Setup-x.y.z-32bit.exe (Windows a 32 bit, richiede Inno Setup 6)
rem Serve un Python a 32 bit con tkinter: indicane il percorso con PY32, per esempio
rem   set PY32=C:\Python313-32\python.exe
rem Le cartelle di build sono build_x86\ e dist_x86\ (non toccano la versione a 64 bit).
cd /d "%~dp0"
if "%PY32%"=="" (
    echo Imposta PY32 con il percorso di python.exe a 32 bit, per esempio: set PY32=C:\Python313-32\python.exe
    goto :fail
)
"%PY32%" -c "import struct,tkinter,sys;sys.exit(0 if struct.calcsize('P')==4 else 1)"
if errorlevel 1 (
    echo "%PY32%" non e' un Python a 32 bit con tkinter.
    goto :fail
)
"%PY32%" -c "import customtkinter, send2trash, PIL, PyInstaller" >nul 2>&1
if errorlevel 1 (
    "%PY32%" -m pip install -r requirements.txt
    if errorlevel 1 goto :fail
)
if not exist assets\icon.ico "%PY32%" make_icon.py
if not exist assets\icons "%PY32%" make_icons.py
"%PY32%" -m PyInstaller --noconfirm --clean --onedir --windowed --name PCCleaner --distpath dist_x86 --workpath build_x86 --specpath build_x86 ^
    --icon "%CD%\assets\icon.ico" --add-data "%CD%\assets;assets" --add-data "%CD%\LICENSE.txt;." --add-data "%CD%\licenses;licenses" --collect-data customtkinter main.py
if errorlevel 1 goto :fail

set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo Inno Setup 6 non trovato: scaricalo da https://jrsoftware.org/isdl.php
    goto :fail
)
%ISCC% /DX86=1 installer.iss
if errorlevel 1 goto :fail
echo.
echo Fatto: installer\PCCleaner-Setup-1.2.1-32bit.exe
exit /b 0

:fail
echo Errore durante la creazione dell'installer a 32 bit.
exit /b 1
