@echo off
echo ========================================
echo Building TokenLords Bot Executable
echo ========================================
echo.
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Building executable...
python build_exe.py
echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Your executable is in: dist\TokenLordsBot.exe
echo.
echo To distribute:
echo 1. Copy dist\TokenLordsBot.exe
echo 2. Copy bot_settings.json (optional - will auto-create)
echo 3. Both files must be in the same folder
echo.
pause
