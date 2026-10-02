@echo off
cd /d "%~dp0"
py -3 -c "import sys; assert sys.version_info >= (3,11), 'Butuh Python 3.11 atau lebih baru'"
if errorlevel 1 goto fail
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m playwright install firefox
if errorlevel 1 goto fail
echo Selesai. Jalankan start_windows.bat
pause
exit /b 0
:fail
echo Instalasi gagal. Periksa pesan di atas dan koneksi internet.
pause
exit /b 1
