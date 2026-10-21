#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Console-less launcher for Windows (double-click -> no black window).

Equivalent to `python Iniciar.py` but meant for pythonw.exe.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

if os.name == "nt":
    try:
        import ctypes
        _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if _hwnd:
            ctypes.windll.user32.ShowWindow(_hwnd, 0)
    except Exception:
        pass

from Iniciar import main

if __name__ == "__main__":
    raise SystemExit(main())
