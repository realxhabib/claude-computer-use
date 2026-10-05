"""Desktop indicator; local Escape terminates the computer-use session."""
import multiprocessing
from .signals import ProcessSignal, BoundedProcessLock, wait_for_process_ready
import threading
import sys
import os
from .diagnostics import checkpoint


def overlay_main(ready, stopped, acknowledged, shutdown, lock, cursor_epoch, cursor_state_lock):
    # Qt must own this process's main thread. Never put UI in the killable worker.
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QPainter, QCursor, QRadialGradient
    from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QGraphicsDropShadowEffect
    from .activity_style import (BANNER_WIDTH, BANNER_HEIGHT, CURSOR_SIZE, CURSOR_HOTSPOT,
                                 ACTIVE_TEXT, CANCEL_TEXT, banner_position)
    from pynput import keyboard
    app = QApplication([])
    class Halo(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            self.setWindowTitle("Claude computer use pointer halo")
            self.resize(CURSOR_SIZE,CURSOR_SIZE)
        def paintEvent(self,event):
            painter=QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
            glow=QRadialGradient(*CURSOR_HOTSPOT,34)
            glow.setColorAt(0,QColor(68,155,255,180))
            glow.setColorAt(.35,QColor(68,155,255,95))
            glow.setColorAt(1,QColor(68,155,255,0))
            painter.setPen(Qt.NoPen);painter.setBrush(glow);painter.drawEllipse(1,1,68,68)
    banner=QWidget();banner.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
    banner.setAttribute(Qt.WA_ShowWithoutActivating)
    banner.setAttribute(Qt.WA_TranslucentBackground)
    banner.setWindowTitle('Claude computer use')
    banner.setFixedSize(BANNER_WIDTH+24,BANNER_HEIGHT+24)
    surface=QWidget(banner);surface.setObjectName('activitySurface')
    surface.setGeometry(12,12,BANNER_WIDTH,BANNER_HEIGHT)
    surface.setStyleSheet("""
        QWidget#activitySurface { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 #579ee8, stop:1 #3787d9); border: 1px solid #85bcf2; border-radius: 9px; }
        QLabel { color: white; background: transparent; border: none; font: 13px 'Segoe UI'; }
        QPushButton { color: white; background: transparent; border: none;
            padding: 4px 6px; font: 600 13px 'Segoe UI'; }
        QPushButton:hover { background: rgba(255,255,255,35); border-radius: 5px; }
        QPushButton:disabled { color: #d5e4f2; }
    """)
    shadow=QGraphicsDropShadowEffect(surface);shadow.setBlurRadius(20)
    shadow.setColor(QColor(64,155,255,140));shadow.setOffset(0,0);surface.setGraphicsEffect(shadow)
    layout=QHBoxLayout(surface);layout.setContentsMargins(13,0,10,0);layout.setSpacing(10)
    label=QLabel(ACTIVE_TEXT);layout.addWidget(label,1)
    cancel_button=QPushButton(CANCEL_TEXT);cancel_button.setFocusPolicy(Qt.NoFocus)
    def stop_locally(source="button"):
        if source=="button":checkpoint("activity.cancel_button")
        try:
            with cursor_state_lock:stopped.set()
        except RuntimeError:stopped.set()
    cancel_button.clicked.connect(lambda:stop_locally());layout.addWidget(cancel_button)
    halo=Halo()
    def key_press(key):
        if key==keyboard.Key.esc:
            checkpoint('activity.escape_received')
            stop_locally("escape")
    listener=keyboard.Listener(on_press=key_press)
    if not getattr(listener, "IS_TRUSTED", True):
        raise RuntimeError("Global Escape listener needs macOS Input Monitoring permission")
    listener.start();listener.wait()
    banner.show()
    def tick():
        if shutdown.is_set(): listener.stop();app.quit();return
        if not listener.is_alive(): stopped.set();app.quit();return
        paused=stopped.is_set()
        banner.setVisible(not paused)
        label.setText(ACTIVE_TEXT)
        cancel_button.setVisible(not paused)
        halo.setVisible(not paused)
        pos=QCursor.pos()
        screen=app.screenAt(pos) or app.primaryScreen()
        if screen is not None:
            bounds=screen.availableGeometry()
            bx,by=banner_position((bounds.x(),bounds.y(),bounds.width(),bounds.height()))
            banner.move(bx-12,by-12)
        if not paused:
            halo.move(pos.x()-CURSOR_HOTSPOT[0],pos.y()-CURSOR_HOTSPOT[1])
    timer=QTimer();timer.timeout.connect(tick);timer.start(20);tick();ready.set()
    app.exec()


class Activity:
    def __init__(self, cancel, on_exit=None):
        self.on_exit=on_exit
        self._close_lock=threading.RLock();self._closed=False
        self.cursor_guard=None
        if sys.platform not in {'win32','darwin'}:raise RuntimeError('Desktop indicator requires Windows or macOS')
        ctx=multiprocessing.get_context('spawn')
        self.ready=ProcessSignal(ctx);self.stopped=ProcessSignal(ctx);self.acknowledged=ProcessSignal(ctx);self.shutdown=ProcessSignal(ctx);self.lock=BoundedProcessLock(ctx);self.cursor_epoch=ctx.RawValue("q",0);self.cursor_state_lock=BoundedProcessLock(ctx)
        self.process=ctx.Process(target=overlay_main,args=(self.ready,self.stopped,self.acknowledged,self.shutdown,self.lock,self.cursor_epoch,self.cursor_state_lock),daemon=True)
        self.process.start()
        if not wait_for_process_ready(self.ready,self.process):
            self.close();raise RuntimeError('Activity indicator/Escape listener unavailable. Check desktop and macOS Input Monitoring permissions.')
        if sys.platform=='win32':
            from .native_cursor import NativeCursorGuard
            try:self.cursor_guard=NativeCursorGuard(self.process.pid,self.stopped,self.cursor_epoch,self.cursor_state_lock)
            except Exception:
                self.close();raise
        os.environ["CLAUDE_COMPUTER_ACTIVITY_PID"] = str(self.process.pid)
        def monitor():
            while not self.shutdown.wait(.02):
                if self.finish_stop(cancel):return
        self.monitor=threading.Thread(target=monitor,daemon=True);self.monitor.start()
    def finish_stop(self, cancel):
        # Serialize monitoring with normal close: teardown must not be mistaken
        # for companion/guard failure and latch a user stop on every normal end.
        with self._close_lock:
            if self._closed:return True
            self.poll_stop(cancel)
            if not (self.stopped.is_set() and self.acknowledged.is_set()):return False
            self.close()
            checkpoint('activity.session_exited')
        # Never hold the close lock while calling into the server lifecycle lock.
        if self.on_exit is not None:self.on_exit()
        return True

    def poll_stop(self, cancel):
        if not self.process.is_alive():self.stopped.set()
        guard=getattr(self,'cursor_guard',None)
        if guard is not None and not guard.process.is_alive():
            self.stopped.set()
        needs_stop=self.stopped.is_set() and not self.acknowledged.is_set()
        if needs_stop:
            checkpoint('activity.cancel_worker_begin')
            cancel()  # Stop native work before any potentially orphaned lock.
            checkpoint('activity.cancel_worker_end')
        with self.lock:
            if self.stopped.is_set() and not self.acknowledged.is_set():
                if guard is not None:guard.wait_restored()
                self.acknowledged.set()
                checkpoint("activity.stop_acknowledged")

    def check(self):
        guard=getattr(self,"cursor_guard",None)
        if guard is not None:guard.check()
        if not self.process.is_alive() or self.stopped.is_set():
            raise RuntimeError('Computer use stopped by user or indicator failure. Start a new session and verify any partially executed actions.')
    def close(self):
        if not hasattr(self,'_close_lock'):
            self._close_lock=threading.RLock();self._closed=False
        with self._close_lock:
            if self._closed:return
            if self.cursor_guard is not None:self.cursor_guard.close()
            self.shutdown.set()
            self.process.join(1)
            if self.process.is_alive():self.process.kill();self.process.join(1)
            if self.process.is_alive():raise RuntimeError('Activity companion termination not confirmed')
            self._closed=True
