"""Native Windows file drops for a Tk window; no external Tk extensions."""
import os
from collections import deque


class FileDrop:
    def __init__(self,root,callback):
        self.root=root;self.callback=callback;self.enabled=False
        self.pending=deque();self.poll_id=None
        if os.name!='nt': return
        import ctypes
        from ctypes import wintypes
        self.ctypes=ctypes;self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.shell=ctypes.WinDLL('shell32',use_last_error=True)
        self.user.GetParent.argtypes=[wintypes.HWND];self.user.GetParent.restype=wintypes.HWND
        root.update_idletasks();self.hwnd=self.user.GetParent(root.winfo_id()) or root.winfo_id()
        self.shell.DragAcceptFiles.argtypes=[wintypes.HWND,wintypes.BOOL]
        self.shell.DragQueryFileW.argtypes=[wintypes.HANDLE,wintypes.UINT,wintypes.LPWSTR,wintypes.UINT]
        self.shell.DragQueryFileW.restype=wintypes.UINT
        self.shell.DragQueryPoint.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.POINT)]
        self.shell.DragFinish.argtypes=[wintypes.HANDLE]
        self.user.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
        self.user.CallWindowProcW.argtypes=[ctypes.c_void_p,wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        self.user.CallWindowProcW.restype=ctypes.c_ssize_t
        self.setter=self.user.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p)==8 else self.user.SetWindowLongW
        self.setter.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_void_p];self.setter.restype=ctypes.c_void_p
        procedure=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
        def handler(hwnd,message,wparam,lparam):
            if message==0x233:
                try:
                    count=self.shell.DragQueryFileW(wparam,0xffffffff,None,0);paths=[]
                    for i in range(count):
                        size=self.shell.DragQueryFileW(wparam,i,None,0)
                        buf=ctypes.create_unicode_buffer(size+1)
                        self.shell.DragQueryFileW(wparam,i,buf,size+1);paths.append(buf.value)
                    point=wintypes.POINT();self.shell.DragQueryPoint(wparam,ctypes.byref(point))
                    self.user.ClientToScreen(hwnd,ctypes.byref(point))
                    # Explorer can dispatch this procedure outside Tcl's event
                    # loop. Never enter Tk (even after_idle) from this callback.
                    self.pending.append((paths,point.x,point.y))
                finally: self.shell.DragFinish(wparam)
                return 0
            return self.user.CallWindowProcW(self.previous,hwnd,message,wparam,lparam)
        self.handler=procedure(handler)
        self.previous=self.setter(self.hwnd,-4,ctypes.cast(self.handler,ctypes.c_void_p))
        if not self.previous: raise OSError(ctypes.get_last_error(),'Cannot enable native file drops')
        self.shell.DragAcceptFiles(self.hwnd,True);self.enabled=True
        self.poll_id=root.after(40,self._deliver)

    def _deliver(self):
        self.poll_id=None
        try:
            while self.enabled and self.pending:
                self.callback(*self.pending.popleft())
        finally:
            if self.enabled: self.poll_id=self.root.after(40,self._deliver)

    def close(self):
        if self.enabled:
            self.enabled=False
            if self.poll_id is not None:
                self.root.after_cancel(self.poll_id);self.poll_id=None
            self.pending.clear()
            self.shell.DragAcceptFiles(self.hwnd,False)
            self.setter(self.hwnd,-4,self.previous);self.enabled=False
