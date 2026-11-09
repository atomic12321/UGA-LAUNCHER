import io
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox
import webbrowser
import ctypes

CURRENT_VERSION = "1.2"
VERSION_CHECK_URL = "https://raw.githubusercontent.com/atomic12321/UGA-LAUNCHER/main/latestversion"

HTML_CONTENT = """<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>New Tab</title>
    <style>html { background-color: #080808; }</style>
    <script>
        window._CDN_URL = "https://cdn.jsdelivr.net/gh";
        window._GITHUB_URL = "ddddd-dbase/New-UGA";
        window._GITHUB_BRANCH = "main";
        window._OUTPUT_FILE = "dist/index.min.html";
    </script>
</head>
<body>
    <div id="removeme" style="position:absolute;top:0;left:0;width:100vw;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;font-family:sans-serif;">
        <h1 id="loading-text">Loading...</h1>
        <h3>Checking connection...</h3>
    </div>
    <script>
        (async () => {
            const loadInOrder = async (scripts) => {
                for (const script of scripts) {
                    await new Promise((resolve) => {
                        let scr = document.createElement("script");
                        if (script.src) { scr.src = script.src; scr.onload = resolve; scr.onerror = resolve; }
                        else { scr.textContent = script.textContent; resolve(); }
                        document.body.appendChild(scr);
                    });
                }
            };
            let fp = `${window._CDN_URL}/${window._GITHUB_URL}@${window._GITHUB_BRANCH}/${window._OUTPUT_FILE}`;
            let res = await fetch(fp);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            let text = await res.text();
            let parser = new DOMParser();
            let doc = parser.parseFromString(text, "text/html");
            let scripts = Array.from(doc.querySelectorAll("script"));
            doc.querySelectorAll("script").forEach(s => s.remove());
            document.documentElement.innerHTML = doc.documentElement.innerHTML;
            await loadInOrder(scripts);
        })().catch(e => {
            document.getElementById("loading-text").textContent = "Error: " + e.message;
        });
    </script>
</body>
</html>"""

def show_error(msg):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Dependency Installation Failed", msg)
    root.destroy()

def install(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        show_error(f"Failed to install required package: {package}\n\nError:\n{e}")
        sys.exit(1)

def ensure_package(package):
    try:
        importlib.import_module(package)
    except ImportError:
        install(package)

ensure_package("pystray")
ensure_package("pillow")
ensure_package("psutil")
ensure_package("requests")

import requests
from PIL import Image, ImageDraw
import psutil
import pystray
from winreg import (
    HKEY_CURRENT_USER, KEY_QUERY_VALUE, KEY_SET_VALUE,
    OpenKey, QueryValueEx, REG_BINARY, SetValueEx
)

# ── Theme ──────────────────────────────────────────────────────────────────────
BG      = "#0a1a0a"
CARD    = "#0f220f"
ACCENT  = "#15FF00"
FG      = "#e0ffe0"
FG_DIM  = "#5a8a5a"
BTN_BG  = "#1a2e1a"
BTN_HOV = "#2a4a2a"
RED     = "#ff4444"
GREEN   = "#15FF00"

# ── State ──────────────────────────────────────────────────────────────────────
running          = True
update_available = False
ib_enabled       = True
sec_enabled      = True
fake_sec_mode    = 0
settings_open    = False

# ── Core ───────────────────────────────────────────────────────────────────────
def find_procs_fast_suspend(target_path):
    target_name = os.path.basename(target_path).lower()
    normalized_target = os.path.normcase(os.path.abspath(target_path))
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target_name:
                if os.path.normcase(proc.exe()) == normalized_target:
                    if proc.status() != psutil.STATUS_STOPPED:
                        proc.suspend()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

def find_procs_fast_kill(target_path):
    target_name = os.path.basename(target_path).lower()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target_name:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

def dis_ib():
    try:
        with OpenKey(HKEY_CURRENT_USER,
                     r"Software\Microsoft\Windows\CurrentVersion\Internet Settings\Connections",
                     access=KEY_QUERY_VALUE | KEY_SET_VALUE) as c:
            raw_data, reg_type = QueryValueEx(c, "DefaultConnectionSettings")
            s = bytearray(raw_data)
            s[0x4:0x8] = (int.from_bytes(s[0x4:0x8], "little") + 1).to_bytes(4, "little")
            s[0x8:0xC] = (0x1).to_bytes(4, "little")
            SetValueEx(c, "DefaultConnectionSettings", 0, REG_BINARY, bytes(s))
    except Exception as e:
        print(f"dis_ib error: {e}")

def dis_clal():
    paths = [
        "%LOCALAPPDATA%/Microsoft/Edge/User Data/Default/Extensions/ojadkogjbnodmmefeihndccbjdhknljm",
        "%LOCALAPPDATA%/Google/Chrome/User Data/Default/Extensions/ihidolefpgnimlmgfljonacidpkmbhcl/",
    ]
    for path in paths:
        ep = os.path.expandvars(path)
        if os.path.exists(ep) and os.path.isdir(ep):
            try:
                shutil.rmtree(ep)
            except Exception as e:
                print(f"dis_clal error: {e}")

# ── Version ────────────────────────────────────────────────────────────────────
def parse_version(v):
    try:
        return tuple(map(int, v.strip().split('.')))
    except:
        return (0,)

def fetch_latest_version():
    try:
        url = f"{VERSION_CHECK_URL}?t={int(time.time())}"
        r = requests.get(url, timeout=5, headers={"Cache-Control": "no-cache"})
        if r.status_code == 200:
            return r.text.strip()
    except Exception as e:
        print(f"Version fetch error: {e}")
    return None

def has_update():
    latest = fetch_latest_version()
    if latest:
        return parse_version(latest) > parse_version(CURRENT_VERSION)
    return False

# ── Icons ──────────────────────────────────────────────────────────────────────
def _fetch_image(url):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        print(f"Image fetch error: {e}")
    return None

def fetch_icon():
    img = _fetch_image("https://cdn.jsdelivr.net/gh/atomic1232/UGA-LAUNCHER@main/UGA.jpg")
    if img:
        return img
    w = h = 64
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((8, 8, w-8, h-8), fill=(21, 255, 0))
    return image

def fetch_fake_sec_icon():
    return _fetch_image("https://cdn.jsdelivr.net/gh/atomic12321/UGA-LAUNCHER@main/fake%20sec%20logo.png")

def fetch_fake_sec_icon_dark():
    return _fetch_image("https://cdn.jsdelivr.net/gh/atomic12321/UGA-LAUNCHER@main/fake%20sec%20logo%20dark.png")

def create_image(color):
    w = h = 64
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((8, 8, w-8, h-8), fill=color)
    return image

def apply_icon_for_mode(tray_icon):
    if fake_sec_mode == 1:
        img = fetch_fake_sec_icon()
    elif fake_sec_mode == 2:
        img = fetch_fake_sec_icon_dark()
    else:
        img = fetch_icon()
    if img:
        tray_icon.icon = img

# ── HTML launcher ──────────────────────────────────────────────────────────────
def execute_html_launch():
    try:
        fp = os.path.join(tempfile.gettempdir(), "NewUGA.html")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(HTML_CONTENT)
        if hasattr(os, "startfile"):
            os.startfile(fp)
        else:
            webbrowser.open(f"file://{fp}")
    except Exception as e:
        print(f"HTML launch error: {e}")

# ── Settings window ────────────────────────────────────────────────────────────
def open_settings(tray_icon):
    global settings_open
    if settings_open:
        return

    def _build():
        global settings_open, ib_enabled, sec_enabled, fake_sec_mode, running
        settings_open = True

        win = tk.Tk()
        win.title("UGA Settings")
        win.geometry("360x600")
        win.resizable(False, True)
        win.configure(bg=BG)

        def on_close():
            global settings_open
            settings_open = False
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

        def card(parent, **kw):
            return tk.Frame(parent, bg=CARD, **kw)

        def label(parent, text, size=10, bold=False, color=FG, **kw):
            return tk.Label(parent, text=text, bg=parent["bg"], fg=color,
                            font=("Segoe UI", size, "bold" if bold else "normal"), **kw)

        def btn(parent, text, cmd, color=ACCENT, fg="black", width=14):
            b = tk.Button(parent, text=text, command=cmd,
                          bg=color, fg=fg, activebackground=BTN_HOV,
                          activeforeground=FG, relief="flat", bd=0,
                          font=("Segoe UI", 9, "bold"), cursor="hand2",
                          padx=10, pady=6, width=width)
            b.bind("<Enter>", lambda e: b.config(bg=BTN_HOV, fg=FG))
            b.bind("<Leave>", lambda e: b.config(bg=color, fg=fg))
            return b

        # Header
        hdr = tk.Frame(win, bg=ACCENT, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="UGA", bg=ACCENT, fg="black",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=16)
        ver = f"v{CURRENT_VERSION}" + ("  ⚠ Update available" if update_available else "")
        tk.Label(hdr, text=ver, bg=ACCENT, fg="#003300",
                 font=("Segoe UI", 9)).pack(side="left")

        # Scrollable body
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=BG)
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")

        def on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def on_canvas_configure(e):
            canvas.itemconfig(body_window, width=e.width)
        body.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Add padding inside body
        tk.Frame(body, bg=BG, height=10).pack()
        inner_body = tk.Frame(body, bg=BG)
        inner_body.pack(fill="both", expand=True, padx=14)
        body = inner_body

        # ── Launch ──
        label(body, "LAUNCH", 8, bold=True, color=FG_DIM).pack(anchor="w", pady=(0,4))
        c = card(body)
        c.pack(fill="x", pady=(0,10))
        inner = tk.Frame(c, bg=CARD, padx=12, pady=10)
        inner.pack(fill="x")
        btn(inner, "Open NewUGA",
            lambda: threading.Thread(target=execute_html_launch, daemon=True).start()).pack(side="left", padx=(0,8))
        if update_available:
            btn(inner, "Get Update",
                lambda: webbrowser.open("https://github.com/atomic12321/UGA-LAUNCHER"),
                color=BTN_BG, fg=ACCENT).pack(side="left")

        # ── Modules ──
        label(body, "MODULES", 8, bold=True, color=FG_DIM).pack(anchor="w", pady=(0,4))
        c2 = card(body)
        c2.pack(fill="x", pady=(0,10))
        mod = tk.Frame(c2, bg=CARD, padx=12, pady=10)
        mod.pack(fill="x")

        def make_toggle(parent, text, desc, get_state, on_toggle):
            row = tk.Frame(parent, bg=CARD)
            row.pack(fill="x", pady=4)
            info = tk.Frame(row, bg=CARD)
            info.pack(side="left", fill="x", expand=True)
            label(info, text, 10, bold=True).pack(anchor="w")
            label(info, desc, 8, color=FG_DIM).pack(anchor="w")
            var = tk.BooleanVar(value=get_state())
            pill = tk.Label(row, text="", bg=CARD, width=6,
                            font=("Segoe UI", 9, "bold"), cursor="hand2")
            pill.pack(side="right", padx=4)
            def refresh():
                on = var.get()
                pill.config(text="ON" if on else "OFF",
                            fg=GREEN if on else RED,
                            bg="#0a2a0a" if on else "#2a0a0a")
            def toggle():
                var.set(on_toggle())
                refresh()
            pill.bind("<Button-1>", lambda e: toggle())
            refresh()

        def do_ib():
            global ib_enabled
            ib_enabled = not ib_enabled
            return ib_enabled

        def do_sec():
            global sec_enabled
            sec_enabled = not sec_enabled
            return sec_enabled

        make_toggle(mod, "IB Bypass", "Disables iBoss proxy via registry",
                    lambda: ib_enabled, do_ib)
        tk.Frame(mod, bg=BTN_HOV, height=1).pack(fill="x", pady=2)
        make_toggle(mod, "SEC", "Kills Securly Classroom processes",
                    lambda: sec_enabled, do_sec)

        # ── Tray Icon ──
        label(body, "TRAY ICON", 8, bold=True, color=FG_DIM).pack(anchor="w", pady=(0,4))
        c3 = card(body)
        c3.pack(fill="x", pady=(0,10))
        icon_inner = tk.Frame(c3, bg=CARD, padx=12, pady=10)
        icon_inner.pack(fill="x")
        icon_var = tk.IntVar(value=fake_sec_mode)
        for text, val in [("Normal (UGA)", 0), ("Fake SEC – Light", 1), ("Fake SEC – Dark", 2)]:
            tk.Radiobutton(icon_inner, text=text, variable=icon_var, value=val,
                           bg=CARD, fg=FG, selectcolor=BG,
                           activebackground=CARD, activeforeground=ACCENT,
                           font=("Segoe UI", 9), cursor="hand2").pack(anchor="w")

        def apply_icon():
            global fake_sec_mode
            fake_sec_mode = icon_var.get()
            threading.Thread(target=lambda: apply_icon_for_mode(tray_icon), daemon=True).start()

        btn(icon_inner, "Apply", apply_icon, width=8).pack(anchor="w", pady=(8,0))

        # ── System ──
        label(body, "SYSTEM", 8, bold=True, color=FG_DIM).pack(anchor="w", pady=(0,4))
        c4 = card(body)
        c4.pack(fill="x", pady=(0,10))
        sys_inner = tk.Frame(c4, bg=CARD, padx=12, pady=10)
        sys_inner.pack(fill="x")

        def do_pause():
            global running
            running = not running
            if not running:
                tray_icon.icon = create_image((74, 20, 140))
                tray_icon.title = "UGA Paused"
            else:
                threading.Thread(target=lambda: apply_icon_for_mode(tray_icon), daemon=True).start()
                tray_icon.title = "UGA On"
            pause_btn.config(text="Resume" if not running else "Pause")

        pause_btn = btn(sys_inner, "Pause" if running else "Resume", do_pause,
                        color=BTN_BG, fg=FG, width=10)
        pause_btn.pack(side="left", padx=(0,8))

        def do_restart():
            global running
            running = False
            tray_icon.stop()
            subprocess.Popen([sys.executable] + sys.argv)
            os._exit(0)

        btn(sys_inner, "Restart", do_restart, color=BTN_BG, fg=FG, width=10).pack(side="left", padx=(0,8))
        btn(sys_inner, "Exit", lambda: (tray_icon.stop(), os._exit(0)),
            color="#3a0000", fg=RED, width=10).pack(side="left")

        win.mainloop()

    threading.Thread(target=_build, daemon=True).start()

# ── Background threads ─────────────────────────────────────────────────────────
def dis_ib_thread():
    while True:
        if running and ib_enabled:
            try:
                dis_ib()
            except Exception as e:
                print(f"dis_ib_thread error: {e}")
        time.sleep(0.2)

def background_loop():
    while True:
        if running and sec_enabled:
            try:
                find_procs_fast_suspend(r"C:\Program Files\Securly\Classroom\1.3.34.8\SlingshotApp.exe")
                find_procs_fast_kill(r"C:\Program Files\Securly\Classroom\Classroom.exe")
            except Exception as e:
                print(f"background_loop error: {e}")
        time.sleep(0.2)

def version_check_thread(tray_icon):
    global update_available
    last_check = 0
    while True:
        if time.time() - last_check >= 3600:
            try:
                new_update = has_update()
                if new_update != update_available:
                    update_available = new_update
            except Exception as e:
                print(f"version_check error: {e}")
            last_check = time.time()
        time.sleep(60)

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        dis_clal()
    except Exception:
        pass

    # Make tkinter DPI-aware so the settings window looks sharp
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    tray_icon = pystray.Icon(
        "UGA",
        create_image((21, 255, 0)),
        "UGA On",
        menu=pystray.Menu(
            pystray.MenuItem("Open NewUGA", lambda icon, item: threading.Thread(target=execute_html_launch, daemon=True).start()),
            pystray.MenuItem("Settings", lambda icon, item: open_settings(icon)),
            pystray.MenuItem(lambda item: "⚠ Update Available" if update_available else "update",
                             lambda icon, item: webbrowser.open("https://github.com/atomic12321/UGA-LAUNCHER")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", lambda icon, item: (icon.stop(), os._exit(0))),
        )
    )

    def startup_tasks():
        global update_available
        tray_icon.icon = fetch_icon()
        try:
            if has_update():
                update_available = True
        except Exception as e:
            print(f"Startup version check error: {e}")

    threading.Thread(target=startup_tasks, daemon=True).start()
    threading.Thread(target=lambda: version_check_thread(tray_icon), daemon=True).start()
    threading.Thread(target=dis_ib_thread, daemon=True).start()
    threading.Thread(target=background_loop, daemon=True).start()
    tray_icon.run()
