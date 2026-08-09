#!/usr/bin/env python3
"""Compatibility entrypoint.

Batch240 already contains SK2MV_30.CAK, so Batch241's remaining movie recovery
lane is Video9. Keep this historical filename callable without duplicating the
recovery implementation.
"""
from pathlib import Path
import runpy

TARGET = Path(__file__).with_name('recover_batch241_video9.py')
if not TARGET.is_file():
    raise SystemExit(f'canonical Video9 recovery tool missing: {TARGET}')
runpy.run_path(str(TARGET), run_name='__main__')
