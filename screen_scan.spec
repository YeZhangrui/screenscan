# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：单文件绿色版 exe。

构建： .venv\\Scripts\\python.exe -m PyInstaller --noconfirm --clean screen_scan.spec
"""
from PyInstaller.utils.hooks import collect_all

# RapidOCR v6 包（含 onnx 模型、config 与 default_models.yaml）整体收集
datas, binaries, hiddenimports = collect_all("rapidocr")
d2, b2, h2 = collect_all("omegaconf")
datas += d2
binaries += b2
hiddenimports += h2

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "scipy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="屏幕扫描助手",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon="assets/icon.ico",
    version="version_info.txt",
)
