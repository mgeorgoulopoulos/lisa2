"""Idempotent source-checkout launcher; uses only the Python standard library."""
import importlib.metadata
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
PYTHON=ROOT/'.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')


def main():
    if sys.version_info[:2]!=(3,12):
        raise RuntimeError('Lisa2 source launch requires Python 3.12. Install it, then run the launcher again. An existing .venv must also use Python 3.12.')
    try:
        import tkinter
        tkinter.Tcl()
    except ImportError as error:
        raise RuntimeError('Python Tk support is missing. On Linux install the matching python3.12-tk package; on Windows enable Tcl/Tk in the Python installer.') from error
    if Path(sys.prefix).resolve()!=(ROOT/'.venv').resolve():
        if not PYTHON.exists():
            print('Creating the local .venv environment...',flush=True)
            subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv')],check=True)
        return subprocess.call([str(PYTHON),str(Path(__file__).resolve()),*sys.argv[1:]],cwd=ROOT)
    requirements=ROOT/'requirements-lock.txt'
    missing=[]
    for line in requirements.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        name,version=line.split('==',1)
        try: installed=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: installed=None
        if installed!=version: missing.append(name)
    if missing:
        print('Installing pinned dependencies (internet required on first launch)...',flush=True)
        subprocess.run([str(PYTHON),'-m','pip','install','--disable-pip-version-check','-r',str(requirements)],cwd=ROOT,check=True)
    if sys.argv[1:]==['--prepare-only']:
        print('Lisa2 source environment is ready.');return 0
    print('Starting Lisa2 Studio...',flush=True)
    return subprocess.call([str(PYTHON),'-m','lisa2.launcher',*sys.argv[1:]],cwd=ROOT)


if __name__=='__main__':
    try: raise SystemExit(main())
    except (RuntimeError,subprocess.CalledProcessError,OSError) as error:
        print(f'Lisa2 setup failed: {error}',file=sys.stderr)
        if sys.platform!='win32':
            print('Use Python 3.12 with venv and Tk support (Ubuntu: python3.12-venv and python3.12-tk). No system packages are installed automatically.',file=sys.stderr)
        raise SystemExit(1)
