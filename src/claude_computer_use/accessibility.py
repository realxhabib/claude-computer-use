"""Bounded native inspection with short-lived references; no coordinate fallback."""
import platform
import hashlib
import time
import uuid
from collections import deque


class WindowsBackend:
    def __init__(self):
        from pywinauto import Desktop
        self.desktop = Desktop(backend="uia")
        self.target_window = None

    def root(self):
        from ctypes import windll
        handle = int(self.target_window['id']) if self.target_window else windll.user32.GetForegroundWindow()
        return self.desktop.window(handle=handle).wrapper_object()

    def identity(self, node):
        return tuple(node.element_info.runtime_id)

    def children(self, node):
        return node.children()

    def describe(self, node):
        info = node.element_info
        rect = node.rectangle()
        protected = bool(info.element.CurrentIsPassword)
        return {"name": "[protected]" if protected else info.name, "role": info.control_type,
                "enabled": node.is_enabled(), "visible": node.is_visible(),
                "protected": protected, "focused": bool(info.element.CurrentHasKeyboardFocus),
                "focusable": bool(info.element.CurrentIsKeyboardFocusable), "bounds": {"left": rect.left, "top": rect.top,
                "width": rect.width(), "height": rect.height()}, "actions": self.actions(node)}

    def actions(self, node):
        result = ["focus"] if node.element_info.element.CurrentIsKeyboardFocusable else []
        try:
            node.iface_invoke
            result.append("activate")
        except Exception:
            pass
        return result

    def act(self, node, action):
        if action == "activate":
            node.iface_invoke.Invoke()
        else:
            node.set_focus()


class MacBackend:
    def __init__(self):
        import ApplicationServices as ax
        from AppKit import NSWorkspace
        self.ax, self.workspace = ax, NSWorkspace.sharedWorkspace()
        self.target_window = None
        if not ax.AXIsProcessTrusted():
            raise RuntimeError("Grant Accessibility permission to the terminal/runtime and restart it")

    def attr(self, node, name, default=None):
        error, value = self.ax.AXUIElementCopyAttributeValue(node, name, None)
        return value if error == 0 else default

    def root(self):
        if self.target_window:
            from .windows import Mac
            return Mac().ax_window(self.target_window)
        app = self.workspace.frontmostApplication()
        root = self.ax.AXUIElementCreateApplication(app.processIdentifier())
        return self.attr(root, "AXFocusedWindow", root)

    def identity(self, node):
        # CFEqual-style equality supplied by the PyObjC wrapper.
        return node

    def children(self, node):
        return self.attr(node, "AXChildren", [])

    def describe(self, node):
        role = self.attr(node, "AXRole", "unknown")
        protected = self.attr(node, "AXSubrole", "") == "AXSecureTextField"
        name = "[protected]" if protected else str(self.attr(node, "AXTitle") or self.attr(node, "AXDescription", ""))
        error, native_actions = self.ax.AXUIElementCopyActionNames(node, None)
        actions = ["activate"] if error == 0 and "AXPress" in (native_actions or []) else []
        error, settable = self.ax.AXUIElementIsAttributeSettable(node, "AXFocused", None)
        if error == 0 and settable:
            actions.append("focus")
        return {"name": name, "role": role, "enabled": bool(self.attr(node, "AXEnabled", True)),
                "visible": None, "protected": protected,
                "focused": self.attr(node, "AXFocused"), "actions": actions}

    def act(self, node, action):
        if action == "activate":
            error = self.ax.AXUIElementPerformAction(node, "AXPress")
        else:
            error = self.ax.AXUIElementSetAttributeValue(node, "AXFocused", True)
        if error != 0:
            raise RuntimeError(f"Accessibility action failed (AX error {error})")


class Inspector:
    def __init__(self, backend, clock=time.monotonic):
        self.backend, self.clock = backend, clock
        self.refs = {}
        self.root_id = None
        self.expires = 0

    def invalidate(self):
        self.refs.clear()
        self.root_id = None
        self.expires = 0

    @staticmethod
    def fingerprint(data):
        # Compare complete native labels, not only their bounded public prefix.
        return hashlib.sha256(repr(tuple(data.get(k) for k in
            ("name", "role", "protected"))).encode("utf-8")).digest()

    @staticmethod
    def public(data):
        result = dict(data)
        result["name"] = str(data.get("name", ""))[:512]
        result["role"] = str(data.get("role", ""))[:128]
        result["label_truncated"] = len(str(data.get("name", ""))) > 512
        return result

    def inspect(self, max_nodes=150, max_depth=8):
        if not 1 <= max_nodes <= 500 or not 0 <= max_depth <= 20:
            raise ValueError("max_nodes must be 1..500 and max_depth 0..20")
        self.invalidate()
        root = self.backend.root()
        self.root_id = self.backend.identity(root)
        self.expires = self.clock() + 30
        queue = deque([(root, None, 0)])
        nodes, errors, truncated = [], 0, False
        while queue and len(nodes) < max_nodes:
            node, parent, depth = queue.popleft()
            try:
                data = self.backend.describe(node)
                identity = self.backend.identity(node)
            except Exception:
                errors += 1
                continue
            ref = uuid.uuid4().hex[:16]
            self.refs[ref] = (node, identity, self.fingerprint(data))
            nodes.append(dict(self.public(data), id=ref, parent=parent, depth=depth))
            try:
                children = self.backend.children(node)
                remaining = max_nodes - len(nodes) - len(queue)
                if children and depth == max_depth:
                    truncated = True
                elif depth < max_depth:
                    truncated |= len(children) > remaining
                    queue.extend((child, ref, depth + 1) for child in children[:max(0, remaining)])
            except Exception:
                errors += 1
        return {"elements": nodes, "truncated": truncated or bool(queue), "inspection_errors": errors,
                "references_valid_seconds": 30, "scope": "foreground window",
                "note": "Native bounds may use OS-specific coordinates; use screenshot coordinates for mouse input."}

    def resolve(self, ref):
        if self.clock() >= self.expires or ref not in self.refs:
            raise ValueError("Reference expired or unknown; inspect the UI again")
        if self.backend.identity(self.backend.root()) != self.root_id:
            raise ValueError("Foreground window changed; inspect the UI again")
        node, identity, old_fingerprint = self.refs[ref]
        new = self.backend.describe(node)
        if self.backend.identity(node) != identity or self.fingerprint(new) != old_fingerprint:
            raise ValueError("Element changed; inspect the UI again")
        return node, new

    def read(self, ref):
        _, data = self.resolve(ref)
        return dict(self.public(data), id=ref)

    def act(self, ref, action):
        if action not in {"activate", "focus"}:
            raise ValueError("Supported actions: activate, focus")
        node, data = self.resolve(ref)
        if data.get("protected") or not data.get("enabled") or data.get("visible") is False:
            raise ValueError("Element is protected, disabled, or hidden")
        if action not in data.get("actions", []):
            raise ValueError("Element does not support this native action; inspect and choose another approach")
        try:
            self.backend.act(node, action)
        finally:
            self.invalidate()
        return {"dispatched": True, "verified": False, "next": "Inspect UI or screenshot to verify the outcome"}


def create_inspector():
    os_name = platform.system()
    if os_name == "Windows":
        return Inspector(WindowsBackend())
    if os_name == "Darwin":
        return Inspector(MacBackend())
    raise RuntimeError("Native UI inspection supports Windows and macOS only")
