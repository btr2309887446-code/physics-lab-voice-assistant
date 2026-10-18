# ESP32 固件编译脚本
# 请在 "ESP-IDF 5.5 PowerShell" 中运行此脚本

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  小智 ESP32 固件编译脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 进入工程目录
$projectDir = "D:/EnglishPath/Study/Workbuddy/xiaozhi/xiaozhi-esp32-main"
Set-Location $projectDir

Write-Host "[1/5] 当前目录: $projectDir" -ForegroundColor Green

# 检查 idf.py 是否可用
if (-not (Get-Command idf.py -ErrorAction SilentlyContinue)) {
    Write-Host "错误: idf.py 命令未找到！" -ForegroundColor Red
    Write-Host "请确保在 'ESP-IDF 5.5 PowerShell' 环境中运行此脚本" -ForegroundColor Red
    exit 1
}

Write-Host "[2/5] ESP-IDF 环境检查通过" -ForegroundColor Green

# 设置目标芯片（根据你的板子型号修改）
$target = "esp32s3"  # 可选: esp32, esp32s2, esp32s3, esp32c3, esp32c6, esp32p4
Write-Host "[3/5] 设置目标芯片: $target" -ForegroundColor Green
idf.py set-target $target

# 配置板子类型（可选 - 如果需要修改板子类型，取消下面的注释）
# Write-Host "[4/5] 打开 menuconfig 配置板子类型..." -ForegroundColor Yellow
# Write-Host "请在 menuconfig 中: Xiaozhi Assistant -> Board Type 选择你的板子" -ForegroundColor Yellow
# idf.py menuconfig

# 编译
Write-Host "[4/5] 开始编译..." -ForegroundColor Green
idf.py build

if ($LASTEXITCODE -ne 0) {
    Write-Host "编译失败！" -ForegroundColor Red
    exit 1
}

Write-Host "[5/5] 编译成功！" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  编译完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "固件文件位置:" -ForegroundColor Yellow
Write-Host "  - 完整固件: $projectDir/build/merged-binary.bin" -ForegroundColor White
Write-Host "  - 应用分区: $projectDir/build/xiaozhi.bin" -ForegroundColor White
Write-Host ""
Write-Host "烧录命令:" -ForegroundColor Yellow
Write-Host "  idf.py -p COM5 -b 2000000 build flash monitor" -ForegroundColor White
Write-Host ""
Write-Host "仅烧录应用分区（快速更新）:" -ForegroundColor Yellow
Write-Host "  idf.py -p COM5 build app-flash monitor" -ForegroundColor White
Write-Host ""
Write-Host "注意: 请将 COM5 替换为你的实际串口号" -ForegroundColor Red
