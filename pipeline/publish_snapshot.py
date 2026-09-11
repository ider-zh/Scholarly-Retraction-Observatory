"""Validate a staged v3 release and atomically install its aggregate directory."""

import argparse
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def publish(report_dir, public_dir=ROOT / 'public'):
    report_dir, public_dir = Path(report_dir).resolve(), Path(public_dir).resolve()
    staging_root = ROOT / 'data/processed'
    staging_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='snapshot-publication-', dir=staging_root) as temporary:
        stage = Path(temporary)
        (stage / 'data').mkdir()
        for filename in ('report.json', 'samples.json'):
            shutil.copy2(public_dir / 'data' / filename, stage / 'data' / filename)
        shutil.copytree(report_dir, stage / 'data/snapshot')
        subprocess.run(['node', str(ROOT / 'scripts/check-public-data.mjs'), '--root', str(stage)], check=True)
        target = public_dir / 'data/snapshot'
        prepared = stage / 'data/snapshot'
        if not target.exists():
            os.replace(prepared, target)
        else:
            library = ctypes.CDLL(None, use_errno=True)
            if not hasattr(library, 'renameat2'):
                raise RuntimeError('Atomic directory exchange is unavailable; previous release preserved')
            rename = library.renameat2
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            if rename(-100, os.fsencode(prepared), -100, os.fsencode(target), 2) != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    print('Published validated aggregate assets: ' + str(target))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report_dir', type=Path)
    publish(parser.parse_args().report_dir)
