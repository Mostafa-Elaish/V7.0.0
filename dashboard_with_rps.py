
# robot/dashboard_with_rps.py
\"\"\"Dashboard with FaceDisplay integration. Keeps Telegram Settings and Wake Logs simple.
This is a lightweight Tkinter dashboard demonstrating FaceDisplay embedding.
\"\"\"
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3, os, datetime, json, requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "events", "events.db")
CONFIG_PATH = os.path.join(BASE_DIR, "..", "config.json")

# Create events DB directory if missing
os.makedirs(os.path.join(BASE_DIR, "..", "events"), exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS wake_events (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, phrase TEXT, matched INTEGER)")
    conn.commit()
    conn.close()

def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {"telegram_token":"", "telegram_chat_id":""}
        with open(CONFIG_PATH,"w") as f: json.dump(default,f,indent=2)
        return default
    try:
        return json.load(open(CONFIG_PATH))
    except Exception:
        return {"telegram_token":"", "telegram_chat_id":""}

def save_config(cfg):
    with open(CONFIG_PATH,"w") as f: json.dump(cfg,f,indent=2)

def send_telegram_alert(message):
    cfg = load_config()
    token = cfg.get("telegram_token","")
    chat_id = cfg.get("telegram_chat_id","")
    if not token or not chat_id:
        print("Telegram not configured")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": message})
    except Exception as e:
        print("Telegram error:", e)

def log_wake_event(phrase, matched):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO wake_events (timestamp, phrase, matched) VALUES (?,?,?)", (ts, phrase, int(matched)))
    conn.commit()
    conn.close()
    if not matched:
        send_telegram_alert(f\"🚨 Wake Attempt Detected\\nTime: {ts}\\nHeard: '{phrase}'\")

# Try to import PanTilt and FaceDisplay
try:
    from robot.pan_tilt import PanTilt
except Exception:
    PanTilt = None

try:
    from robot.face_display import FaceDisplay
except Exception:
    FaceDisplay = None

class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(\"Jarvis Dashboard\")
        self.geometry(\"1024x600\")
        init_db()
        self.create_widgets()
        # attempt to create PanTilt hardware, fallback to simulator
        self.pan_tilt = None
        if PanTilt is not None:
            try:
                # default pins (customize if your wiring differs)
                self.pan_tilt = PanTilt(pin_pan=22, pin_tilt=27)
            except Exception as e:
                print('PanTilt init failed:', e)
                self.pan_tilt = None
        # start face display
        if FaceDisplay is not None:
            self.face_frame = tk.Frame(self.tab_face)
            self.face_frame.pack(fill='both', expand=True)
            self.face = FaceDisplay(self.face_frame, width=640, height=320, pan_tilt=self.pan_tilt)
            self.face.start(interval_ms=60)
        else:
            tk.Label(self.tab_face, text='FaceDisplay not available', fg='red').pack()

    def create_widgets(self):
        tabControl = ttk.Notebook(self)
        self.tab_logs = ttk.Frame(tabControl)
        self.tab_settings = ttk.Frame(tabControl)
        self.tab_games = ttk.Frame(tabControl)
        self.tab_face = ttk.Frame(tabControl)
        tabControl.add(self.tab_face, text='Face')
        tabControl.add(self.tab_games, text='Games')
        tabControl.add(self.tab_logs, text='Logs')
        tabControl.add(self.tab_settings, text='Settings')
        tabControl.pack(expand=1, fill='both')

        # Games Tab
        tk.Button(self.tab_games, text=\"Play Rock-Paper-Scissors\", command=self.play_rps).pack(pady=10)

        # Logs Tab (wake logs)
        self.log_list = tk.Listbox(self.tab_logs, width=120, height=20)
        self.log_list.pack(side='left', fill='both', expand=True)
        sb = tk.Scrollbar(self.tab_logs, orient='vertical', command=self.log_list.yview)
        sb.pack(side='right', fill='y')
        self.log_list.config(yscrollcommand=sb.set)
        tk.Button(self.tab_logs, text='Refresh Wake Logs', command=self.load_wake_logs).pack(pady=6)
        tk.Button(self.tab_logs, text='Clear Wake Logs', command=self.clear_wake_logs).pack(pady=6)
        self.load_wake_logs()

        # Settings Tab
        tk.Button(self.tab_settings, text='Configure Telegram', command=self.configure_telegram).pack(pady=6)
        tk.Button(self.tab_settings, text='Center Camera (Pan/Tilt)', command=self.center_camera).pack(pady=6)

    def play_rps(self):
        try:
            from robot.rps_voice_improved import RPSGame
            g = RPSGame(camera_id=0, pan_tilt_enabled=(self.pan_tilt is not None))
            res = g.play_round()
            if res:
                messagebox.showinfo('RPS Result', f\"Result: {res.get('winner')}\\nYou: {res.get('user_choice')}\\nJarvis: {res.get('jarvis_choice')}\")
                self.load_wake_logs()
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def load_wake_logs(self):
        self.log_list.delete(0, tk.END)
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(\"SELECT timestamp, phrase, matched FROM wake_events ORDER BY id DESC LIMIT 100\")
            rows = cur.fetchall()
            conn.close()
            for ts, phrase, matched in rows:
                tag = 'MATCH' if matched else 'TRY'
                self.log_list.insert(tk.END, f\"[{ts}] ({tag}) {phrase}\")
        except Exception as e:
            self.log_list.insert(tk.END, f\"DB Error: {e}\")

    def clear_wake_logs(self):
        if not messagebox.askyesno('Confirm', 'Clear wake logs?'): return
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('DELETE FROM wake_events')
            conn.commit(); conn.close()
            self.load_wake_logs()
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def configure_telegram(self):
        cfg = load_config()
        token = simpledialog.askstring('Telegram', 'Enter Bot Token:', initialvalue=cfg.get('telegram_token',''))
        if token is None: return
        chat_id = simpledialog.askstring('Telegram', 'Enter Chat ID:', initialvalue=cfg.get('telegram_chat_id',''))
        if chat_id is None: return
        cfg['telegram_token'] = token.strip(); cfg['telegram_chat_id'] = chat_id.strip()
        save_config(cfg)
        if messagebox.askyesno('Test Alert', 'Send test alert now?'):
            send_telegram_alert('✅ Test alert from Jarvis Dashboard')

    def center_camera(self):
        if self.pan_tilt is None:
            messagebox.showinfo('Info', 'PanTilt hardware not available')
            return
        try:
            self.pan_tilt.set_pan(90); self.pan_tilt.set_tilt(90)
            messagebox.showinfo('Info', 'Camera centered')
        except Exception as e:
            messagebox.showerror('Error', str(e))

if __name__ == '__main__':
    app = Dashboard()
    app.mainloop()
