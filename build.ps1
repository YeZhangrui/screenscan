# 一键打包脚本：生成图标 → PyInstaller 构建单文件 exe
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> 生成应用图标"
.\.venv\Scripts\python.exe scripts\make_icon.py

Write-Host "==> PyInstaller 构建（单文件绿色版）"
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean screen_scan.spec

if ($LASTEXITCODE -eq 0) {
    $exe = "dist\屏幕扫描助手.exe"
    if (Test-Path $exe) {
        $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
        Write-Host "==> 构建完成：$exe （$size MB）"
    }
} else {
    Write-Host "==> 构建失败！"
    exit 1
}
