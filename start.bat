@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo   四级单词 App
echo   ----------------------------------------
echo   本地地址: http://localhost:8000
echo   手机同一 WiFi 也能访问（见 README）
echo.
echo   这个黑窗口不要关，关掉就是停止运行。
echo   停止: 按 Ctrl+C，或直接关掉本窗口。
echo.

start "" http://localhost:8000/
python -m http.server 8000
pause
