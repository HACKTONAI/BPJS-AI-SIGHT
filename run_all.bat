@echo off
REM Pastikan script berjalan dari folder file ini
cd /d "%~dp0"

echo Menjalankan AI (start windows untuk setiap proses)...

REM Cari virtualenv yang ada (.venv atau venv)
if exist ".venv\Scripts\activate.bat" (
	set "ACTIVATE=.venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
	set "ACTIVATE=venv\Scripts\activate.bat"
) else (
	echo Virtual environment not found. Buat dulu dengan: python -m venv .venv
	pause
	goto :eof
)

echo Using virtualenv: %ACTIVATE%

REM Start producer in new window (activate venv inside that window)
start "Producer" cmd /k "%ACTIVATE% && cd /d "%~dp0" && echo Menjalankan Producer Redis... && python producer_redis.py"

REM Start worker in new window
start "Worker" cmd /k "%ACTIVATE% && cd /d "%~dp0" && echo Menjalankan Worker Redis... && python worker_redis.py"

REM Start snapshot API in new window (specify host/port)
start "SnapshotAPI" cmd /k "%ACTIVATE% && cd /d "%~dp0" && echo Menjalankan Snapshot API... && uvicorn snapshot_api:app --reload --host 127.0.0.1 --port 9000"

echo Semua proses telah dimulai. Lihat jendela terpisah untuk log dan error.
pause
