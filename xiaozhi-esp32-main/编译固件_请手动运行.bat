@echo off
chcp 65001
cls

echo ========================================
echo   小智 ESP32 固件编译脚本
echo ========================================
echo.

REM 进入工程目录
cd /d "D:\EnglishPath\Study\Workbuddy\xiaozhi\xiaozhi-esp32-main"

echo [1/5] 当前目录: %CD%

REM 检查 idf.py 是否可用
where idf.py >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: idf.py 命令未找到！
    echo 请确保在 "ESP-IDF 5.5 PowerShell" 或 "ESP-IDF 5.5 CMD" 环境中运行此脚本
    pause
    exit /b 1
)

echo [2/5] ESP-IDF 环境检查通过

REM 设置目标芯片（根据你的板子型号修改）
set TARGET=esp32s3

echo [3/5] 设置目标芯片: %TARGET%
idf.py set-target %TARGET%
if %errorlevel% neq 0 (
    echo 设置目标芯片失败！
    pause
    exit /b 1
)

REM 编译
echo [4/5] 开始编译...
idf.py build
if %errorlevel% neq 0 (
    echo 编译失败！
    pause
    exit /b 1
)

echo [5/5] 编译成功！
echo.
echo ========================================
echo   编译完成！
echo ========================================
echo.
echo 固件文件位置:
echo   - 完整固件: %CD%\build\merged-binary.bin
echo   - 应用分区: %CD%\build\xiaozhi.bin
echo.
echo 烧录命令:
echo   idf.py -p COM5 -b 2000000 build flash monitor
echo.
echo 仅烧录应用分区（快速更新）:
echo   idf.py -p COM5 build app-flash monitor
echo.
echo 注意: 请将 COM5 替换为你的实际串口号
echo.
pause
