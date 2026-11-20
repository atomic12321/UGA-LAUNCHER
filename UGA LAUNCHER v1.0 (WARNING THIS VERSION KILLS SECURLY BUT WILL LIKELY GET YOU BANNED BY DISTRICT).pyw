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

# Current version - update this when releasing new versions
CURRENT_VERSION = "1.0"
VERSION_CHECK_URL = "https://raw.githubusercontent.com/atomic12321/UGA-LAUNCHER/main/latestversion"

# Compact HTML Loader that pulls your latest build from the CDN
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
            console.log("Fetching:", fp);
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
            console.error(e);
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
from pystray import MenuItem as item
from winreg import (
    HKEY_CURRENT_USER, KEY_QUERY_VALUE, KEY_SET_VALUE,
    OpenKey, QueryValueEx, REG_BINARY, SetValueEx
)

def find_procs_fast_suspend(target_path):
    target_name = os.path.basename(target_path).lower()
    normalized_target = os.path.normcase(os.path.abspath(target_path))
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target_name:
                if os.path.normcase(proc.exe()) == normalized_target:
                    if proc.status() != psutil.STATUS_STOPPED:
                        proc.suspend()
                        print("KOd", target_path)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

def find_procs_fast_kill(target_path):
    target_name = os.path.basename(target_path).lower()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target_name:
                proc.kill()
                print("Killed", target_path)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

def dis_ib() -> None:
    try:
        with OpenKey(
            HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings\Connections",
            access=KEY_QUERY_VALUE | KEY_SET_VALUE,
        ) as connections:
            # Unpacks the data tuple directly to avoid TypeError crashes
            raw_data, reg_type = QueryValueEx(connections, "DefaultConnectionSettings")
            settings = bytearray(raw_data)
            
            settings[0x4:0x8] = (int.from_bytes(settings[0x4:0x8], "little") + 1).to_bytes(4, "little")
            settings[0x8:0xC] = (0x1).to_bytes(4, "little")
            
            SetValueEx(connections, "DefaultConnectionSettings", 0, REG_BINARY, bytes(settings))
    except Exception as e:
        print(f"Failed to update registry settings: {e}")

def dis_clal() -> None:
    paths = [
        "%LOCALAPPDATA%/Microsoft/Edge/User Data/Default/Extensions/ojadkogjbnodmmefeihndccbjdhknljm",
        "%LOCALAPPDATA%/Google/Chrome/User Data/Default/Extensions/ihidolefpgnimlmgfljonacidpkmbhcl/",
    ]
    for path in paths:
        expanded_path = os.path.expandvars(path)
        if os.path.exists(expanded_path) and os.path.isdir(expanded_path):
            try:
                shutil.rmtree(expanded_path)
                print(f"Successfully deleted: {expanded_path}")
            except Exception as e:
                print(f"Failed to delete directory: {e}")

def parse_version(version_string):
    """Parse version string into tuple for comparison (e.g., '1.0' -> (1, 0))"""
    try:
        return tuple(map(int, version_string.strip().split('.')))
    except:
        return (0,)

def fetch_latest_version():
    """Fetch the latest version from GitHub"""
    try:
        url = f"{VERSION_CHECK_URL}?t={int(time.time())}"
        response = requests.get(url, timeout=5, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
        print(f"Version check status: {response.status_code}")
        print(f"Version check raw response: {repr(response.text)}")
        if response.status_code == 200:
            latest = response.text.strip()
            print(f"Parsed latest version: {repr(latest)}")
            return latest
    except Exception as e:
        print(f"Failed to fetch latest version: {e}")
    return None

def has_update():
    """Check if an update is available"""
    latest = fetch_latest_version()
    if latest:
        current = parse_version(CURRENT_VERSION)
        latest_parsed = parse_version(latest)
        print(f"Comparing: current={current} latest={latest_parsed} update={latest_parsed > current}")
        return latest_parsed > current
    return False

def fetch_icon():
    try:
        url = "https://cdn.jsdelivr.net/gh/atomic1232/UGA-LAUNCHER@main/UGA.jpg"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content))
    except Exception as e:
        print(f"Failed to download icon from CDN: {e}")
    
    # Fallback placeholder image if network/fetch fails on startup
    width, height = 64, 64
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, width - 8, height - 8), fill=(209, 179, 233))
    return image

def create_image(color):
    width, height = 64, 64
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, width - 8, height - 8), fill=color)
    return image

def on_exit(icon, item):
    global running
    running = False
    icon.stop()
    os._exit(0)

def on_restart(icon, menu_item):
    global running
    running = False
    icon.stop()
    subprocess.Popen([sys.executable] + sys.argv)
    os._exit(0)

def execute_html_launch():
    try:
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, "NewUGA.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(HTML_CONTENT)
        if hasattr(os, "startfile"):
            os.startfile(file_path)
        else:
            webbrowser.open(f"file://{file_path}")
    except Exception as e:
        print(f"Failed to open temporary HTML file: {e}")

def on_open_new_uga(icon, menu_item):
    # Offloads execution to a side thread so the tray context never deadlocks
    threading.Thread(target=execute_html_launch, daemon=True).start()

def on_open_update(icon, menu_item):
    webbrowser.open("https://github.com/atomic12321/UGA-LAUNCHER")

def get_update_label(item):
    return "⚠ UPDATE AVAILABLE" if update_available else "update"

running = True
update_available = False

def on_pause(icon, menu_item):
    global running
    running = not running
    if not running:
        icon.icon = create_image((74, 20, 140))
    else:
        icon.icon = fetch_icon()
    icon.title = "UGA Paused" if not running else "UGA On"

def version_check_thread(icon):
    """Check for updates periodically"""
    global update_available
    check_interval = 3600  # Check every hour
    last_check = 0
    
    while True:
        current_time = time.time()
        if current_time - last_check >= check_interval:
            try:
                new_update = has_update()
                if new_update and not update_available:
                    update_available = True
                    print(f"Update available! Current: {CURRENT_VERSION}, Latest: {fetch_latest_version()}")
                    icon.update_menu()
                elif not new_update and update_available:
                    update_available = False
                    icon.update_menu()
            except Exception as e:
                print(f"Error checking for updates: {e}")
            last_check = current_time
        
        time.sleep(60)  # Check every minute if enough time has passed

def dis_ib_thread():
    """Separate thread for dis_ib() to avoid blocking main loop"""
    while True:
        if running:
            try:
                dis_ib()
            except Exception as e:
                print(f"Error in dis_ib thread: {e}")
        time.sleep(0.2)

def background_loop():
    """Background loop that handles process suspension/killing"""
    while True:
        if running:
            try:
                find_procs_fast_suspend(r"C:\Program Files\Securly\Classroom\1.3.34.8\SlingshotApp.exe")
                find_procs_fast_kill(r"C:\Program Files\Securly\Classroom\Classroom.exe")
            except Exception as e:
                print(f"Error in background task loop: {e}")
        
        time.sleep(0.2)

if __name__ == "__main__":
    try:
        dis_clal()
    except Exception:
        pass

    # Use a plain fallback icon instantly so the tray appears right away
    icon = pystray.Icon(
        "UGA",
        create_image((209, 179, 233)),
        "UGA On",
        menu=pystray.Menu(
            item("Open NewUGA", on_open_new_uga),
            item(get_update_label, on_open_update),
            item("Pause/Resume", on_pause),
            item("Restart", on_restart),
            item("Exit", on_exit),
        ),
    )

    def startup_network_tasks():
        """Run all network tasks in background so the tray isn't blocked"""
        # Load the real icon
        real_icon = fetch_icon()
        icon.icon = real_icon

        # Check for updates
        try:
            if has_update():
                global update_available
                update_available = True
                icon.update_menu()
                print(f"Update available! Current: {CURRENT_VERSION}, Latest: {fetch_latest_version()}")
        except Exception as e:
            print(f"Initial version check failed: {e}")

    threading.Thread(target=startup_network_tasks, daemon=True).start()
    threading.Thread(target=lambda: version_check_thread(icon), daemon=True).start()
    threading.Thread(target=dis_ib_thread, daemon=True).start()
    threading.Thread(target=background_loop, daemon=True).start()
    icon.run()
