@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   糍粑 QQ 机器人 - 首次安装
echo ============================================
echo.

if not exist config.yaml (
    echo [!] 未找到 config.yaml，正在从模板创建...
    copy config.yaml.example config.yaml >nul
    echo     已创建 config.yaml，请先填写 AppID / AppSecret / DeepSeek Key
    echo     填写完成后，重新运行本脚本。
    echo.
    notepad config.yaml
    exit /b 0
)

echo [1/3] 创建 Python 虚拟环境...
if not exist .venv\Scripts\python.exe (
    python -m venv .venv
)

echo [2/3] 安装依赖...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

echo [3/3] 安装完成！
echo.
echo   接下来运行 "2.启动机器人.bat" 即可。
echo.
pause
