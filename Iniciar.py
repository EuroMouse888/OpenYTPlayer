#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Iniciar.py — legacy entry point name.

Kept for compatibility with existing shortcuts. The canonical entry point is
start.py; this file simply forwards to it.
"""
from start import main

if __name__ == "__main__":
    raise SystemExit(main())
