@echo off
title Telegram Bot 24/7 Auto-Restart Runner
echo ========================================================
echo   Telegram Bot 24/7 Watchdog Runner
echo   If the bot crashes or stops, it will restart automatically!
echo   Press Ctrl+C to stop the runner.
echo ========================================================

:loop
echo [%date% %time%] Starting Telegram Bot...
python bot.py
echo.
echo [%date% %time%] Warning: Bot stopped or crashed! Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
