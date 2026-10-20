@echo off
title 3WHs Video Telegram Bot
chcp 65001 > nul
echo ========================================================
echo       🚀 កំពុងដំណើរការ 3WHs Video Telegram Bot...
echo ========================================================
echo.

if not exist ".env" (
    echo [!] រកមិនឃើញ file .env ទេ។ សូមបង្កើត file .env រួចបញ្ចូល Token ជាមុនសិន។
    pause
    exit /b
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
.\venv\Scripts\python.exe bot.py
pause
