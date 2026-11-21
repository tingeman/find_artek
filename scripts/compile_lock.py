#!/usr/bin/env python3
"""Compile hash-locked app-main/requirements.txt and requirements-dev.txt from the .in files.

Usage: python scripts/compile_lock.py [--upgrade] [--package NAME]... [--constraints PATH]
                                     [--exclude-newer DATE]
  (no flags)           keep the versions of the existing lock, add/remove what changed in .in
  --constraints PATH   pip-freeze style file; versions are held to it (no-upgrade lock). The
                       first lock was made with production's pip freeze of 2026-11-16.
  --upgrade            resolve to the newest versions the .in bounds allow (annual upgrade)
  --package NAME       upgrade only NAME (repeatable); the rest stays at the existing lock
  --exclude-newer DATE ignore releases uploaded after DATE (YYYY-MM-DD); a cooldown against
                       freshly published, possibly compromised versions

Runs uv inside a container of the pinned Python image (the image the Dockerfile builds on),
so only Python 3.8+ (stdlib only) and Docker are needed on the host. Works from Windows
PowerShell, WSL, Linux and Git Bash. The pins come from compose.pins.env; the env variables
FA_PYTHON_IMAGE / FA_UV_VERSION override them.

Adapted from webapp_nukissiorfiit (scripts/compile_lock.py).
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
APP_DIR = REPO_DIR / 'app-main'
PINS_FILE = REPO_DIR / 'compose.pins.env'
# (input, lock file)
LOCKS = (('requirements.in', 'requirements.txt'), ('requirements-dev.in', 'requirements-dev.txt'))

HEADER = """\
# GENERATED FILE, DO NOT EDIT BY HAND.
# Hash-locked from app-main/{src} by scripts/compile_lock.py (uv {uv} in {image}).
# To change a dependency, edit {src} and rerun the script (see its docstring).
"""


def read_pins(path):
    pins = {}
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return pins
    for line in text.splitlines():  # splitlines also drops CR of CRLF files
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        pins.setdefault(key.strip(), value.strip())
    return pins


def count_pins(path):
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return 0
    return len(re.findall(r'^[A-Za-z0-9][^\s=]*==', text, flags=re.MULTILINE))


def add_header(path, src, uv_version, image):
    """Prepend the "generated, do not edit" header (uv runs with --no-header)."""
    body = path.read_text(encoding='utf-8')
    header = HEADER.format(src=src, uv=uv_version, image=image.split('@', 1)[0])
    # newline='\n': the lock is read inside Linux containers; keep LF on Windows too
    with path.open('w', encoding='utf-8', newline='\n') as f:
        f.write(header + body)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Compile hash-locked requirements with uv in a container.'
    )
    parser.add_argument(
        '--constraints', metavar='PATH', help='pip-freeze style file to hold versions to'
    )
    parser.add_argument(
        '--upgrade', action='store_true', help='resolve to the newest allowed versions'
    )
    parser.add_argument(
        '--package',
        action='append',
        default=[],
        metavar='NAME',
        help='upgrade only NAME (repeatable)',
    )
    parser.add_argument(
        '--exclude-newer',
        metavar='DATE',
        help='ignore releases uploaded after DATE (YYYY-MM-DD), e.g. a week before today',
    )
    args = parser.parse_args(argv)

    pins = read_pins(PINS_FILE)
    image = os.environ.get('FA_PYTHON_IMAGE') or pins.get('FA_PYTHON_IMAGE', '')
    uv_version = os.environ.get('FA_UV_VERSION') or pins.get('FA_UV_VERSION', '')
    if not image:
        sys.exit('FA_PYTHON_IMAGE not set and not found in compose.pins.env')
    if not uv_version:
        sys.exit('FA_UV_VERSION not set and not found in compose.pins.env')
    # Markers and wheels are resolved for the Python of the image (python:3.13.18-... -> 3.13)
    m = re.match(r'(?:[^/]+/)*python:(\d+\.\d+)', image)
    if not m:
        sys.exit(f'cannot read the Python version from FA_PYTHON_IMAGE={image!r}')
    python_version = m.group(1)

    # Native resolved paths: C:\... on Windows, POSIX paths on WSL/Linux. Both are accepted by docker -v.
    mounts = ['-v', f'{APP_DIR.resolve()}:/work']
    compile_args = [
        '--generate-hashes',
        '--python-version',
        python_version,
        '--python-platform',
        'x86_64-unknown-linux-gnu',
        '--no-header',
        '--quiet',
    ]
    # Constraints are ignored together with --upgrade (as in nuki).
    if args.constraints and not args.upgrade:
        cpath = Path(args.constraints).resolve()
        if not cpath.is_file():
            sys.exit(f'Constraints file not found: {args.constraints}')
        mounts += ['-v', f'{cpath.parent}:/constraints:ro']
        compile_args += ['-c', f'/constraints/{cpath.name}']
    if args.exclude_newer:
        compile_args += ['--exclude-newer', args.exclude_newer]
    if args.upgrade:
        compile_args.append('--upgrade')
    else:
        for name in args.package:
            compile_args += ['--upgrade-package', name]

    # Executed by sh inside the container; quote everything for it.
    def sh_quote(s):
        return "'" + s.replace("'", "'\\''") + "'"

    common = ' '.join(sh_quote(a) for a in compile_args)
    # On Linux/WSL run as the host user, so the lock files are not owned by root; uv is then
    # installed into a temporary directory instead of the image's site-packages.
    if hasattr(os, 'getuid'):
        user = ['-u', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp']
        install, uv = '--target /tmp/uv', 'PYTHONPATH=/tmp/uv /tmp/uv/bin/uv'
    else:
        user, install, uv = [], '', 'uv'
    lines = [
        'set -e',
        f'pip install --quiet --disable-pip-version-check --root-user-action=ignore {install} {sh_quote("uv==" + uv_version)}',
    ]
    # The production lock first: the dev .in uses it as constraint (-c requirements.txt)
    lines += [f'{uv} pip compile {src} {common} -o {out}' for src, out in LOCKS]
    script = '\n'.join(lines)
    cmd = ['docker', 'run', '--rm', *user, *mounts, '-w', '/work', image, 'sh', '-c', script]

    env = dict(os.environ, MSYS_NO_PATHCONV='1')  # Git Bash: keep /work etc. as they are
    try:
        result = subprocess.run(cmd, env=env)
    except FileNotFoundError:
        sys.exit('docker not found on PATH; install Docker (Desktop) and make sure it is running')
    if result.returncode != 0:
        sys.exit(
            f'docker run failed (exit code {result.returncode}); lock files were not (fully) updated'
        )

    for src, out in LOCKS:
        add_header(APP_DIR / out, src, uv_version, image)
        print(f'Wrote app-main/{out} ({count_pins(APP_DIR / out)} pins)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
