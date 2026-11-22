@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 糍粑 QQ 机器人

if not exist .venv\Scripts\python.exe (
    echo [!] 尚未安装，请先运行 "1.首次安装.bat"
    pause
    exit /b 1
)

if not exist config.yaml (
    echo [!] 未找到 config.yaml，请先运行 "1.首次安装.bat" 并填写配置
    pause
    exit /b 1
)

echo ============================================
echo   糍粑 QQ 机器人 启动中...
echo   关闭此窗口即停止机器人
echo ============================================
echo.
.venv\Scripts\python.exe main.py
pause
