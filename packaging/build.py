"""Native PyInstaller build and portable archive; installer compilation is separate."""
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parent.parent


def main():
    os.chdir(ROOT)
    # Keep build cache in the workspace, rather than a machine-specific location.
    os.environ.setdefault('PYINSTALLER_CONFIG_DIR',str(ROOT/'build'/'pyinstaller-cache'))
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean',
                    str(ROOT/'packaging'/'Lisa2.spec')],check=True)
    bundle=ROOT/'dist'/'Lisa2';release=ROOT/'release';release.mkdir(exist_ok=True)
    for name in ('README.md','STUDIO.md','LICENSE'):
        shutil.copy2(ROOT/name,bundle/name)
    shutil.copytree(ROOT/'docs',bundle/'docs',dirs_exist_ok=True)
    (bundle/'QUICKSTART.txt').write_text(
        'Lisa2 — A memetic evolution of LisaGA\n\n'
        'Windows: open Lisa2.exe. Linux: run ./start.sh.\n'
        'Choose four images, press Start evolution and save a project.\n'
        'Keep the JSON project with its companion .data folder.\n'
        'First training startup compiles CPU kernels and may take longer.\n'
        'Python and application dependencies are included; no pip install needed.\n'
        'Linux requires an x86-64 glibc desktop (Ubuntu 22.04+ baseline).\n'
        'Linux image slots use click-to-select; Explorer drag/drop is Windows-only.\n',encoding='utf-8')
    licenses=bundle/'third-party-licenses';licenses.mkdir(exist_ok=True)
    for name in ('LICENSE.txt','LICENSE'):
        source=Path(sys.base_prefix)/name
        if source.is_file(): shutil.copyfile(source,licenses/('Python-'+name));break
    for name in ('tcl8.6','tk8.6'):
        for base in (Path(sys.base_prefix)/'Library'/'lib',Path(sys.base_prefix)/'tcl'):
            source=base/name/'license.terms'
            if source.is_file(): shutil.copyfile(source,licenses/(name+'-license.terms'))
    manifest=[]
    for name in ('numpy','scipy','numba','llvmlite','Pillow','pygame-ce','deap',
                 'moocore','platformdirs','cffi','pycparser','pyinstaller'):
        dist=importlib.metadata.distribution(name)
        manifest.append(dict(name=name,version=dist.version))
        for file in dist.files or []:
            if any(part.lower().startswith(('license','copying','notice')) for part in file.parts):
                source=Path(dist.locate_file(file))
                if source.is_file():
                    dest=licenses/name/str(file).replace('..','_')
                    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    (bundle/'dependencies.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if os.name=='nt':
        shutil.make_archive(str(release/'Lisa2-Windows-Portable'),'zip',ROOT/'dist','Lisa2')
    else:
        shutil.copyfile(ROOT/'packaging'/'start.sh',bundle/'start.sh');(bundle/'start.sh').chmod(0o755)
        (bundle/'Lisa2').chmod(0o755)
        with tarfile.open(release/'Lisa2-Linux-x86_64.tar.gz','w:gz') as archive:
            archive.add(bundle,arcname='Lisa2')


if __name__=='__main__': main()
