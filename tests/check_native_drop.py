"""Exercise the real WM_DROPFILES bridge with a withdrawn window."""
import ctypes
from ctypes import wintypes
import tkinter as tk
import time
from pathlib import Path
from unittest.mock import patch
from lisa2.windows_drop import FileDrop

class DROPFILES(ctypes.Structure):
    _fields_=[('pFiles',wintypes.DWORD),('pt',wintypes.POINT),
              ('fNC',wintypes.BOOL),('fWide',wintypes.BOOL)]

root=tk.Tk();root.withdraw();received=[]
drop=FileDrop(root,lambda *args:received.append(args))
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GlobalAlloc.argtypes=[wintypes.UINT,ctypes.c_size_t];kernel.GlobalAlloc.restype=wintypes.HGLOBAL
kernel.GlobalLock.argtypes=[wintypes.HGLOBAL];kernel.GlobalLock.restype=ctypes.c_void_p
kernel.GlobalUnlock.argtypes=[wintypes.HGLOBAL]
drop.user.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
drop.user.SendMessageW.restype=ctypes.c_ssize_t
paths=[str(Path('assets/TestImages/δοκιμή.png').resolve())]
payload=('\0'.join(paths)+'\0\0').encode('utf-16-le')
handle=kernel.GlobalAlloc(0x42,ctypes.sizeof(DROPFILES)+len(payload))
address=kernel.GlobalLock(handle)
header=DROPFILES.from_address(address);header.pFiles=ctypes.sizeof(DROPFILES);header.fWide=True
ctypes.memmove(address+header.pFiles,payload,len(payload));kernel.GlobalUnlock(handle)
with patch.object(root,'after_idle',side_effect=AssertionError('Tk entered from native callback')) as idle:
    drop.user.SendMessageW(drop.hwnd,0x233,handle,0)
    idle.assert_not_called()
assert not received,'Native callback must not enter Tk'
deadline=time.monotonic()+2
while not received and time.monotonic()<deadline:
    root.update();time.sleep(.01)
assert received and received[0][0]==paths,received
drop.close();root.destroy()
print('PASS: native Unicode WM_DROPFILES delivery on a withdrawn window')
