import tkinter as tk
from tkinter import messagebox, Checkbutton, IntVar
import json
import subprocess
import os
import sys
import uuid
import socket
import threading
try:
    from PIL import Image, ImageDraw
    import pystray
except ImportError:
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, "Lütfen 'pip install pystray Pillow' kurun.", "Hata", 1)
    sys.exit()

LISANS_KONTROL_AKTIF = True
IZIN_VERILEN_ID = "141719871828486"

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
APP_PY = os.path.join(BASE_DIR, 'app.py') 
SERVER_EXE = os.path.join(BASE_DIR, 'server.exe')
BAT_FILE = os.path.join(BASE_DIR, 'BASLAT.bat')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.ico')

def get_machine_id():
    return str(uuid.getnode()).strip()

def check_license(root):
    current_id = get_machine_id()
    target_id = str(IZIN_VERILEN_ID).strip()
    if LISANS_KONTROL_AKTIF:
        if current_id != target_id:
            root.clipboard_clear()
            root.clipboard_append(current_id)
            messagebox.showerror("Lisans Hatası", f"ID: {current_id}")
            root.destroy()
            sys.exit()
    else:
        print(f"ID: {current_id}")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def load_config():
    defaults = {
        "gunluk_limit": 2, "haftalik_limit": 0, "aylik_limit": 0, "max_ileri_gun": 7,
        "admin_sifresi": "admin123", "port": 80, 
        "oto_baslat_app": False, "windows_baslat": False,
        "guv_sorusu_aktif": True, "baslangic_saati": 7, "bitis_saati": 23, "seans_suresi": 150
    }
    if not os.path.exists(CONFIG_FILE): return defaults
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            for k, v in defaults.items():
                if k not in data: data[k] = v
            return data
    except: return defaults

def save_config(data):
    try:
        with open(CONFIG_FILE, 'w') as f: json.dump(data, f, indent=4)
    except: pass

def set_windows_startup(enable):
    try:
        startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
        shortcut_path = os.path.join(startup_folder, 'CamasirhaneSistemi.lnk')
        if enable:
            target = sys.executable.replace("python.exe", "pythonw.exe") if not os.path.exists(BAT_FILE) else BAT_FILE
            script = os.path.abspath(__file__)
            w_dir = BASE_DIR
            args = f'"{script}"' if not os.path.exists(BAT_FILE) else ""
            
            vbs_content = f'Set oWS = WScript.CreateObject("WScript.Shell")\nSet oLink = oWS.CreateShortcut("{shortcut_path}")\noLink.TargetPath = "{target}"\noLink.Arguments = "{args}"\noLink.WorkingDirectory = "{w_dir}"\n'
            if os.path.exists(LOGO_PATH): vbs_content += f'oLink.IconLocation = "{LOGO_PATH}"\n'
            vbs_content += "oLink.Save"
            
            vbs_path = os.path.join(BASE_DIR, "temp.vbs")
            with open(vbs_path, "w") as f: f.write(vbs_content)
            subprocess.call(['cscript', '//Nologo', vbs_path], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if os.path.exists(vbs_path): os.remove(vbs_path)
            return True
        else:
            if os.path.exists(shortcut_path): os.remove(shortcut_path)
            return False
    except: return False

class YoneticiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Yönetici Paneli")
        self.root.geometry("480x980") # Biraz daha uzattık
        check_license(root)
        
        self.server_process = None
        self.config = load_config()
        self.tray_icon = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing_attempt)

        tk.Label(root, text="YÖNETİCİ PANELİ", font=("Arial", 16, "bold"), fg="#333").pack(pady=10)
        self.lbl_status = tk.Label(root, text="DURUM: KAPALI", fg="red", font=("Arial", 12, "bold"))
        self.lbl_status.pack(pady=5)
        
        self.btn_start = tk.Button(root, text="BAŞLAT", bg="green", fg="white", font=("Arial", 12), command=self.start_server)
        self.btn_start.pack(fill="x", padx=20, pady=5)
        
        self.btn_stop = tk.Button(root, text="DURDUR", bg="red", fg="white", font=("Arial", 12), command=self.stop_server, state="disabled")
        self.btn_stop.pack(fill="x", padx=20, pady=5)

        # --- YENİ EKLENEN KAPATMA BUTONU ---
        tk.Button(root, text="UYGULAMADAN ÇIK (KAPAT)", bg="#333", fg="white", font=("Arial", 10, "bold"), command=self.quit_app).pack(fill="x", padx=20, pady=5)

        self.frame_main = tk.Frame(root)
        self.frame_main.pack(pady=10, fill="both", expand=True)
        
        self.var_guv = IntVar(value=1 if self.config.get('guv_sorusu_aktif') else 0)
        tk.Checkbutton(self.frame_main, text="Güvenlik Sorusu Sorulsun", variable=self.var_guv, command=self.save_chk).pack(anchor="w", padx=20)
        
        self.var_oto_app = IntVar(value=1 if self.config.get('oto_baslat_app') else 0)
        tk.Checkbutton(self.frame_main, text="Program açılınca siteyi başlat", variable=self.var_oto_app, command=self.save_chk).pack(anchor="w", padx=20)
        
        self.var_oto_win = IntVar(value=1 if self.config.get('windows_baslat') else 0)
        tk.Checkbutton(self.frame_main, text="Windows açılınca otomatik başlat", variable=self.var_oto_win, command=self.toggle_win).pack(anchor="w", padx=20)

        tk.Label(self.frame_main, text="-- AYARLAR --", font=("Arial", 10, "bold")).pack(pady=10)
        self.grid_fr = tk.Frame(self.frame_main)
        self.grid_fr.pack()
        
        self.entries = {}
        fields = [
            ("Günlük Limit:", "gunluk_limit"), ("Haftalık Limit:", "haftalik_limit"),
            ("Aylık Limit:", "aylik_limit"), ("İleri Tarih (Gün):", "max_ileri_gun"),
            ("Açılış Saati (Tam):", "baslangic_saati"), ("Kapanış Saati (Tam):", "bitis_saati"),
            ("Seans (Dk):", "seans_suresi"), ("Admin Şifresi:", "admin_sifresi"),
            ("Port:", "port")
        ]
        
        for i, (lbl, key) in enumerate(fields):
            tk.Label(self.grid_fr, text=lbl).grid(row=i, column=0, sticky="e", padx=5, pady=2)
            e = tk.Entry(self.grid_fr)
            e.insert(0, self.config.get(key, ""))
            e.grid(row=i, column=1, padx=5, pady=2)
            self.entries[key] = e

        tk.Button(root, text="KAYDET", command=self.save_all, height=2, bg="#ddd").pack(fill="x", padx=20, pady=10)
        
        # --- LİSANS ALANI ---
        frame_lic = tk.Frame(root, relief=tk.GROOVE, borderwidth=2)
        frame_lic.pack(fill="x", padx=10, pady=10, side="bottom")
        
        machine_id = get_machine_id()
        tk.Label(frame_lic, text="Bilgisayar ID:", font=("Arial", 8, "bold"), fg="#555").pack(anchor="w", padx=5)
        
        ent_id = tk.Entry(frame_lic, width=40, font=("Consolas", 9))
        ent_id.insert(0, machine_id)
        ent_id.config(state="readonly")
        ent_id.pack(anchor="w", padx=5, pady=2)
        
        # Sessiz Kopyalama Butonu
        self.btn_copy = tk.Button(frame_lic, text="ID'yi Kopyala", command=lambda: self.copy_id(machine_id), font=("Arial", 8))
        self.btn_copy.pack(anchor="w", padx=5, pady=2)
        
        status_txt = "AKTİF (Kilitli)" if LISANS_KONTROL_AKTIF else "PASİF (Geliştirici Modu)"
        status_fg = "green" if LISANS_KONTROL_AKTIF else "orange"
        tk.Label(frame_lic, text=f"Lisans: {status_txt}", font=("Arial", 9, "bold"), fg=status_fg).pack(anchor="w", padx=5, pady=5)

        if self.config.get('oto_baslat_app'):
            self.root.after(500, self.start_server)

    # --- SESSİZ KOPYALAMA ---
    def copy_id(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        # Buton yazısını geçici olarak değiştir
        original_text = self.btn_copy.cget("text")
        self.btn_copy.config(text="Kopyalandı!", fg="green")
        self.root.after(2000, lambda: self.btn_copy.config(text=original_text, fg="black"))

    def start_server(self):
        if self.server_process is None:
            port = int(self.entries["port"].get())
            if is_port_in_use(port):
                messagebox.showerror("Hata", f"Port {port} dolu!")
                return
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                cmd = [SERVER_EXE] if os.path.exists(SERVER_EXE) else [sys.executable.replace("python.exe", "pythonw.exe"), APP_PY]
                self.server_process = subprocess.Popen(
                    cmd, startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.lbl_status.config(text="DURUM: ÇALIŞIYOR (Arka Planda)", fg="green")
                self.btn_start.config(state="disabled")
                self.btn_stop.config(state="normal")
                self.toggle_ui(False)
            except Exception as e:
                try: 
                    self.server_process = subprocess.Popen([sys.executable, APP_PY], creationflags=subprocess.CREATE_NO_WINDOW)
                    self.lbl_status.config(text="DURUM: ÇALIŞIYOR", fg="green")
                    self.btn_start.config(state="disabled")
                    self.btn_stop.config(state="normal")
                    self.toggle_ui(False)
                except: messagebox.showerror("Hata", str(e))

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None
            self.lbl_status.config(text="DURUM: KAPALI", fg="red")
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
            self.toggle_ui(True)

    def on_closing_attempt(self):
        try: self.minimize_to_tray()
        except: self.quit_app()

    def minimize_to_tray(self):
        image = self.get_icon_image()
        menu = (pystray.MenuItem('Aç', self.show_window, default=True), pystray.MenuItem('Çıkış', self.quit_app))
        self.tray_icon = pystray.Icon("Camasirhane", image, "Yönetici Paneli", menu)
        self.root.withdraw()
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def get_icon_image(self):
        if os.path.exists(LOGO_PATH): return Image.open(LOGO_PATH)
        return Image.new('RGB', (64, 64), color='blue')

    def show_window(self, icon=None, item=None):
        if self.tray_icon: self.tray_icon.stop()
        self.root.after(0, self.root.deiconify)

    def quit_app(self, icon=None, item=None):
        if self.tray_icon: self.tray_icon.stop()
        if self.server_process: self.server_process.terminate()
        self.root.quit()
        sys.exit()

    def save_chk(self):
        self.config['oto_baslat_app'] = bool(self.var_oto_app.get())
        self.config['guv_sorusu_aktif'] = bool(self.var_guv.get())
        save_config(self.config)

    def toggle_win(self):
        enable = bool(self.var_oto_win.get())
        if set_windows_startup(enable) or not enable:
            self.config['windows_baslat'] = enable
            save_config(self.config)
        else:
            self.var_oto_win.set(0)

    def save_all(self):
        try:
            for key, entry in self.entries.items():
                val = entry.get()
                if key == "admin_sifresi":
                    self.config[key] = val
                    continue
                if not val.isdigit():
                    messagebox.showerror("Hata", f"Lütfen '{key}' için sadece TAM SAYI giriniz.\n(Nokta veya virgül kullanmayınız).")
                    return
                self.config[key] = int(val)
            
            self.config['guv_sorusu_aktif'] = bool(self.var_guv.get())
            save_config(self.config)
            messagebox.showinfo("Başarılı", "Ayarlar kaydedildi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Kayıt hatası: {e}")

    def toggle_ui(self, enable):
        state = "normal" if enable else "disabled"
        for e in self.entries.values(): e.config(state=state)

if __name__ == "__main__":
    root = tk.Tk()
    app = YoneticiApp(root)
    root.mainloop()