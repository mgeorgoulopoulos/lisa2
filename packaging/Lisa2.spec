# Build on the target OS; do not cross-compile.
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

root=Path(SPECPATH).parent
# A venv backed by conda keeps Tcl DLLs outside the usual Python DLL directory.
extra_binaries=[]
metadata=[]
for package in ('moocore','deap','numba','llvmlite','scipy','Pillow','pygame-ce','cffi','platformdirs','pycparser'):
    metadata+=copy_metadata(package)
if os.name=='nt':
    for name in ('tcl86t.dll','tk86t.dll','ffi.dll'):
        dll=Path(sys.base_prefix)/'Library'/'bin'/name
        if dll.exists(): extra_binaries.append((str(dll),'.'))
a=Analysis([str(root/'packaging'/'entrypoint.py')],pathex=[str(root)],
    binaries=extra_binaries,datas=metadata,
    hiddenimports=['scipy.optimize._lsq','PIL._tkinter_finder'],
    hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=['matplotlib','IPython','pytest','numba.tests','scipy.tests','numpy.tests'],
    noarchive=False,
    # Numba's disk-cache locator and spawned workers need actual .py files.
    module_collection_mode={'lisa2':'py','numba':'py+pyz'})
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Lisa2',
    debug=False,bootloader_ignore_signals=False,strip=False,upx=False,
    console=os.name!='nt')
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='Lisa2')
