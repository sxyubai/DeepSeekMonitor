# -*- mode: python ; coding: utf-8 -*-
"""
DeepSeek Monitor PyInstaller 打包配置
© 2026 sxyubai
"""

import sys
from pathlib import Path

# ---- 项目根目录 ----
# spec 文件放在项目根目录下，所以 CWD 就是项目根
ROOT = Path(".").resolve()
BACKEND = ROOT / "project" / "backend"

a = Analysis(
    [str(BACKEND / "main.py")],
    pathex=[str(ROOT), str(BACKEND)],
    binaries=[],
    datas=[
        # (源路径, 目标相对路径 in MEIPASS)
        (str(BACKEND / "resources"), "resources"),
    ],
    hiddenimports=[
        # PySide6 动态模块
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtCore",
        # cryptography 相关
        "cryptography",
        "cryptography.fernet",
        "cryptography.hazmat.primitives",
        "cryptography.hazmat.primitives.kdf.pbkdf2",
        "cryptography.hazmat.primitives.hashes",
        "cryptography.hazmat.backends",
        # keyring
        "keyring",
        "keyring.backends.Windows",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块以减少体积
        "tkinter",
        "unittest",
        "pdb",
        "test",
        "pip",
        "asyncio",
        "multiprocessing",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DeepSeekMonitor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # --windowed: 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 无图标文件，使用程序内绘制图标
)
