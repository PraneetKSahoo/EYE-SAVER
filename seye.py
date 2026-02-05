import ctypes
import math
import threading
import tkinter as tk
from tkinter import ttk
from ctypes import wintypes
import pystray
from PIL import Image, ImageDraw
import sys
import os

# --- Helper to find the icon when packaged as EXE ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 1. The Engine ---
class GammaControl:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.hdc = self.user32.GetDC(None)

    def set_gamma(self, red, green, blue):
        ramp = (wintypes.WORD * 768)()
        for i in range(256):
            val_r = int((i / 255.0) * 65535 * red)
            val_g = int((i / 255.0) * 65535 * green)
            val_b = int((i / 255.0) * 65535 * blue)
            val_r = min(65535, max(0, val_r))
            val_g = min(65535, max(0, val_g))
            val_b = min(65535, max(0, val_b))
            ramp[i] = val_r
            ramp[i + 256] = val_g
            ramp[i + 512] = val_b
        self.gdi32.SetDeviceGammaRamp(self.hdc, ctypes.byref(ramp))

    def kelvin_to_rgb(self, kelvin):
        temp = kelvin / 100.0
        if temp <= 66:
            r = 255
            g = temp
            g = 99.4708025861 * math.log(g) - 161.1195681661
        else:
            r = temp - 60
            r = 329.698727446 * (r ** -0.1332047592)
            g = temp - 60
            g = 288.1221695283 * (g ** -0.0755148492)
        if temp >= 66:
            b = 255
        elif temp <= 19:
            b = 0
        else:
            b = temp - 10
            b = 138.5177312231 * math.log(b) - 305.0447927307
        return (
            min(255, max(0, r)) / 255.0,
            min(255, max(0, g)) / 255.0,
            min(255, max(0, b)) / 255.0
        )

# --- 2. The Enhanced GUI ---
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Eye Saver")
        self.root.geometry("450x420")
        self.root.resizable(False, False)
        
        # Set Window Icon
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except:
                pass # Ignore if icon is invalid

        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.engine = GammaControl()

        # Styles
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", font=("Segoe UI", 9), padding=5)
        style.configure("TLabel", font=("Segoe UI", 10))
        
        # --- PRESETS SECTION ---
        preset_frame = ttk.LabelFrame(root, text="Quick Presets", padding=15)
        preset_frame.pack(fill="x", padx=15, pady=10)

        # Preset Buttons Grid
        ttk.Button(preset_frame, text="Normal", command=lambda: self.apply_preset(6500, 100)).grid(row=0, column=0, padx=5)
        ttk.Button(preset_frame, text="Office", command=lambda: self.apply_preset(4500, 90)).grid(row=0, column=1, padx=5)
        ttk.Button(preset_frame, text="Health", command=lambda: self.apply_preset(3500, 80)).grid(row=0, column=2, padx=5)
        ttk.Button(preset_frame, text="Night", command=lambda: self.apply_preset(2500, 60)).grid(row=0, column=3, padx=5)

        # --- CONTROLS SECTION ---
        control_frame = ttk.LabelFrame(root, text="Manual Adjustment", padding=15)
        control_frame.pack(fill="x", padx=15, pady=5)

        # Temperature
        self.lbl_temp_val = tk.StringVar(value="6500K")
        
        temp_header = ttk.Frame(control_frame)
        temp_header.pack(fill="x")
        ttk.Label(temp_header, text="Warmth").pack(side="left")
        ttk.Label(temp_header, textvariable=self.lbl_temp_val, foreground="blue").pack(side="right")
        
        self.temp_slider = ttk.Scale(control_frame, from_=1500, to=6500, orient='horizontal', command=self.update_from_slider)
        self.temp_slider.pack(fill="x", pady=(0, 15))

        # Brightness
        self.lbl_bright_val = tk.StringVar(value="100%")
        
        bright_header = ttk.Frame(control_frame)
        bright_header.pack(fill="x")
        ttk.Label(bright_header, text="Brightness").pack(side="left")
        ttk.Label(bright_header, textvariable=self.lbl_bright_val, foreground="blue").pack(side="right")
        
        self.bright_slider = ttk.Scale(control_frame, from_=20, to=100, orient='horizontal', command=self.update_from_slider)
        self.bright_slider.pack(fill="x")

        # FIX: Initialize values AFTER both sliders exist
        self.temp_slider.set(6500)
        self.bright_slider.set(100)

        # --- FOOTER ---
        footer_frame = ttk.Frame(root)
        footer_frame.pack(side="bottom", fill="x", pady=10)
        
        tk.Label(footer_frame, text="Close window to minimize to tray", fg="gray", font=("Segoe UI", 8)).pack()

        # Start Tray Thread
        self.tray_icon = None
        threading.Thread(target=self.create_tray_icon, daemon=True).start()

    def apply_preset(self, temp, bright):
        """Updates sliders and applies settings"""
        # Update sliders, which will trigger the command automatically
        self.temp_slider.set(temp)
        self.bright_slider.set(bright)

    def update_from_slider(self, _=None):
        """Called when user drags slider"""
        # FIX: Crash prevention - check if sliders exist yet
        if not hasattr(self, 'temp_slider') or not hasattr(self, 'bright_slider'):
            return

        temp = int(self.temp_slider.get())
        bright = int(self.bright_slider.get())
        self.update_screen(temp, bright)

    def update_screen(self, temp, bright):
        # Update text labels
        self.lbl_temp_val.set(f"{int(temp)}K")
        self.lbl_bright_val.set(f"{int(bright)}%")
        
        # Apply to engine
        b_float = bright / 100.0
        r, g, b = self.engine.kelvin_to_rgb(temp)
        self.engine.set_gamma(r * b_float, g * b_float, b * b_float)

    # --- System Tray Logic ---
    def create_tray_icon(self):
        icon_path = resource_path("icon.ico")
        
        if os.path.exists(icon_path):
            try:
                image = Image.open(icon_path)
            except:
                image = Image.new('RGB', (64, 64), "orange")
        else:
            image = Image.new('RGB', (64, 64), "orange")
            dc = ImageDraw.Draw(image)
            dc.ellipse((10, 10, 54, 54), fill="orange")
        
        menu = pystray.Menu(
            pystray.MenuItem("Show Settings", self.show_window_from_tray),
            pystray.MenuItem("Exit", self.quit_app)
        )
        
        self.tray_icon = pystray.Icon("EyeSaver", image, "Eye Saver", menu)
        self.tray_icon.run()

    def hide_window(self):
        self.root.withdraw()

    def show_window_from_tray(self, icon, item):
        self.root.after(0, self.root.deiconify)

    def quit_app(self, icon, item):
        self.engine.set_gamma(1.0, 1.0, 1.0) # Reset screen
        icon.stop()
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()