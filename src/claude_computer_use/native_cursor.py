"""Windows native arrow replacement owned by an independent restoration guard."""
import multiprocessing
from .signals import ProcessSignal, wait_for_process_ready
import os
import time
from .diagnostics import checkpoint

ARROW_ID = 32512  # OCR_NORMAL; preserve text, resize and busy cursor semantics.
MUTEX_NAME = 'Local\\ClaudeComputerUseNativeCursor'


class WindowsCursor:
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        self.c,self.w=c,w
        self.u=c.WinDLL('user32',use_last_error=True)
        self.g=c.WinDLL('gdi32',use_last_error=True)
        self.k=c.WinDLL('kernel32',use_last_error=True)
        self.u.LoadCursorW.argtypes=[w.HINSTANCE,c.c_void_p];self.u.LoadCursorW.restype=w.HANDLE
        self.u.CopyImage.argtypes=[w.HANDLE,w.UINT,c.c_int,c.c_int,w.UINT];self.u.CopyImage.restype=w.HANDLE
        self.u.SetSystemCursor.argtypes=[w.HANDLE,w.DWORD];self.u.SetSystemCursor.restype=w.BOOL
        self.u.DestroyCursor.argtypes=[w.HANDLE]
        self.u.SystemParametersInfoW.argtypes=[w.UINT,w.UINT,c.c_void_p,w.UINT];self.u.SystemParametersInfoW.restype=w.BOOL
        self.k.CreateMutexW.argtypes=[c.c_void_p,w.BOOL,w.LPCWSTR];self.k.CreateMutexW.restype=w.HANDLE
        self.k.ReleaseMutex.argtypes=[w.HANDLE];self.k.CloseHandle.argtypes=[w.HANDLE]
        self.g.DeleteObject.argtypes=[w.HANDLE]
        self.mutex=None
    def acquire(self):
        self.c.set_last_error(0)
        handle=self.k.CreateMutexW(None,True,MUTEX_NAME)
        if not handle:raise RuntimeError('Cursor ownership mutex unavailable')
        if self.c.get_last_error()==183:
            self.k.CloseHandle(handle)
            raise RuntimeError('Another computer-use session owns the native cursor')
        self.mutex=handle
    def release(self):
        if self.mutex:
            self.k.ReleaseMutex(self.mutex);self.k.CloseHandle(self.mutex);self.mutex=None
    def copy(self, handle):
        result=self.u.CopyImage(handle,2,0,0,0)  # IMAGE_CURSOR; never shared/copy-return-original.
        if not result:raise RuntimeError('Cursor snapshot/copy failed')
        return result
    def snapshot(self):
        handle=self.u.LoadCursorW(None,self.c.c_void_p(ARROW_ID))
        if not handle:raise RuntimeError('Native arrow unavailable')
        return self.copy(handle)
    def destroy(self, handle):self.u.DestroyCursor(handle)
    def install(self, handle):
        # Windows consumes this disposable handle; never pass a snapshot directly.
        if not self.u.SetSystemCursor(handle,ARROW_ID):
            self.u.DestroyCursor(handle)
            raise RuntimeError('Native cursor replacement/restoration failed')
    def reload_scheme(self):
        if not self.u.SystemParametersInfoW(0x0057,0,None,0):
            raise RuntimeError('Configured cursor scheme could not be restored')
    def arrow(self):
        from PIL import Image,ImageDraw
        c,w=self.c,self.w
        size=48;scale=4
        image=Image.new('RGBA',(size*scale,size*scale))
        points=[(2,2),(4,37),(13,28),(20,43),(27,40),(20,24),(35,23)]
        draw=ImageDraw.Draw(image)
        draw.polygon([(x*scale,y*scale) for x,y in points],fill='#171b22')
        draw.line([(x*scale,y*scale) for x,y in points+[points[0]]],fill='white',width=2*scale,joint='curve')
        image=image.resize((size,size),Image.Resampling.LANCZOS)
        # Premultiplied BGRA for the alpha cursor bitmap.
        raw=bytes(channel for r,g,b,a in image.getdata() for channel in (b*a//255,g*a//255,r*a//255,a))
        class Header(c.Structure):
            _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bits',w.WORD),('compression',w.DWORD),('image_size',w.DWORD),('xppm',w.LONG),('yppm',w.LONG),('used',w.DWORD),('important',w.DWORD)]
        class Info(c.Structure):_fields_=[('header',Header),('colors',w.DWORD*3)]
        class Icon(c.Structure):_fields_=[('icon',w.BOOL),('x',w.DWORD),('y',w.DWORD),('mask',w.HBITMAP),('color',w.HBITMAP)]
        info=Info();info.header=Header(c.sizeof(Header),size,-size,1,32,0,len(raw),0,0,0,0)
        bits=c.c_void_p()
        self.g.CreateDIBSection.argtypes=[w.HDC,c.POINTER(Info),w.UINT,c.POINTER(c.c_void_p),w.HANDLE,w.DWORD];self.g.CreateDIBSection.restype=w.HBITMAP
        self.g.CreateBitmap.argtypes=[c.c_int,c.c_int,w.UINT,w.UINT,c.c_void_p];self.g.CreateBitmap.restype=w.HBITMAP
        self.u.CreateIconIndirect.argtypes=[c.POINTER(Icon)];self.u.CreateIconIndirect.restype=w.HANDLE
        color=self.g.CreateDIBSection(None,c.byref(info),0,c.byref(bits),None,0)
        mask=None
        try:
            if not color or not bits.value:raise RuntimeError('Cursor bitmap allocation failed')
            c.memmove(bits,raw,len(raw))
            mask=self.g.CreateBitmap(size,size,1,1,c.create_string_buffer(bytes(size*size//8)))
            if not mask:raise RuntimeError('Cursor mask allocation failed')
            handle=self.u.CreateIconIndirect(c.byref(Icon(False,2,2,mask,color)))
            if not handle:raise RuntimeError('Cursor construction failed')
            return handle
        finally:
            if mask:self.g.DeleteObject(mask)
            if color:self.g.DeleteObject(color)


class CursorLease:
    def __init__(self, api):self.api=api;self.saved=None;self.changed=False
    def capture(self):self.saved=self.api.snapshot()
    def activate(self):
        handle=self.api.arrow()
        self.changed=True  # A partial native failure still requires restoration.
        checkpoint("cursor.install_begin")
        self.api.install(handle)
        checkpoint("cursor.install_end")
    def restore(self):
        if self.changed:
            checkpoint("cursor.restore_begin")
            self.api.install(self.api.copy(self.saved));self.changed=False
            checkpoint("cursor.restore_end")
    def close(self):
        self.restore()
        if self.saved:self.api.destroy(self.saved);self.saved=None


def cursor_state(state_lock, epoch, stopped):
    with state_lock:return epoch.value,stopped.is_set()


def resume_cursor(state_lock, epoch, stopped):
    with state_lock:
        epoch.value += 1
        stopped.clear()


def cursor_guard_main(ready,restored,restored_epoch,epoch,state_lock,changed,stopped,shutdown,parent_pid,parent_birth,companion_pid,companion_birth):
    from .worker_entry import parent_matches
    import psutil
    api=None;lease=None
    try:
        parent=psutil.Process(parent_pid);companion=psutil.Process(companion_pid)
        api=WindowsCursor();api.acquire();lease=CursorLease(api);lease.capture()
        while True:
            observed_epoch,paused=cursor_state(state_lock,epoch,stopped)
            exiting=shutdown.is_set() or not parent_matches(parent,parent_birth) or not parent_matches(companion,companion_birth)
            if exiting or paused:
                lease.restore();changed.clear();restored_epoch.value=observed_epoch;restored.set()
            elif not lease.changed:
                restored.clear();changed.set();lease.activate()
            ready.set()  # Only after successful install or successful paused restoration.
            if exiting:break
            shutdown.wait(.02)
    except Exception:
        stopped.set()
    finally:
        try:
            if lease:lease.close();changed.clear();restored_epoch.value=epoch.value;restored.set()
        except Exception:
            try:
                if api:api.reload_scheme();changed.clear();restored_epoch.value=epoch.value;restored.set()
            except Exception:pass
        finally:
            if api:api.release()


class NativeCursorGuard:
    def __init__(self,companion_pid,stopped,epoch,state_lock):
        import psutil
        ctx=multiprocessing.get_context('spawn')
        self.ready=ProcessSignal(ctx);self.restored=ProcessSignal(ctx);self.changed=ProcessSignal(ctx);self.shutdown=ProcessSignal(ctx)
        self.epoch=epoch;self.restored_epoch=ctx.RawValue("q",-1)
        from .companion_launch import start_companion
        deadline=time.monotonic()+10
        self.process=start_companion(ctx,cursor_guard_main,(self.ready,self.restored,self.restored_epoch,self.epoch,state_lock,self.changed,stopped,self.shutdown,
            os.getpid(),psutil.Process(os.getpid()).create_time(),companion_pid,psutil.Process(companion_pid).create_time()),timeout=10,shutdown=self.shutdown,restores_cursor=True)
        if not wait_for_process_ready(self.ready,self.process,max(0,deadline-time.monotonic())):
            self.close();raise RuntimeError('Native cursor guard could not initialize; another session may own the cursor')
    def check(self):
        if not self.process.is_alive():raise RuntimeError('Native cursor guard exited; restart computer use')
    def restoration_matches(self, epoch):
        return self.restored.is_set() and self.restored_epoch.value==epoch
    def wait_restored(self):
        expected=self.epoch.value
        deadline=time.monotonic()+1
        while True:
            if not self.process.is_alive():self.fallback()
            if self.restoration_matches(expected):return
            if time.monotonic()>=deadline:
                raise RuntimeError('Cursor restoration not confirmed for this Resume cycle; Resume remains disabled')
            time.sleep(.02)
    def fallback(self):
        if self.changed.is_set():
            api=WindowsCursor()
            try:
                api.acquire();api.reload_scheme();self.changed.clear();self.restored_epoch.value=self.epoch.value;self.restored.set()
            finally:api.release()
    def close(self):
        self.shutdown.set();self.process.join(1)
        if self.process.is_alive() and getattr(self.process,"owns_process_tree",False) is True:
            self.process.kill();self.process.join(1)
        elif self.process.is_alive():
            import psutil
            try:
                root=psutil.Process(self.process.pid);root.suspend()
                descendants=root.children(recursive=True)
                for child in reversed(descendants):
                    try:child.kill()
                    except psutil.NoSuchProcess:pass
                self.process.kill();self.process.join(1)
                _,alive=psutil.wait_procs(descendants,timeout=.5)
                if alive:raise RuntimeError('Cursor guard termination not confirmed')
            except psutil.NoSuchProcess:pass
        if self.process.is_alive():raise RuntimeError("Cursor guard root termination not confirmed")
        self.fallback()
