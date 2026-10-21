import csv
import sqlite3
import math
import random
import sys
import threading
import queue
import time
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime
from functools import reduce
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


# ------------------------------ Theme ---------------------------------------
BG = "#0b1220"
PANEL = "#111c2f"
PANEL2 = "#17243a"
BORDER = "#263650"
TEXT = "#edf4ff"
MUTED = "#9eb0c9"
CYAN = "#42d6c5"
BLUE = "#5ba7ff"
GREEN = "#4bd49a"
AMBER = "#ffbf5f"
RED = "#ff667a"
PURPLE = "#b79cff"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 20, "bold")


# ------------------------------ OOP model -----------------------------------
class ThermalStrategy(ABC):
    """Abstract interface: each strategy must define its own recommendation."""
    @abstractmethod
    def recommendation(self, battery_temp, coolant_temp):
        pass


class NormalCooling(ThermalStrategy):
    def recommendation(self, battery_temp, coolant_temp):
        return "NO COOLING", "Temperature is in the normal operating band.", GREEN, 0


class WarningCooling(ThermalStrategy):
    def recommendation(self, battery_temp, coolant_temp):
        return "INCREASE COOLANT FLOW", "Elevated temperature detected; increase micro-channel coolant flow.", AMBER, 65


class CriticalCooling(ThermalStrategy):
    def recommendation(self, battery_temp, coolant_temp):
        return "MAXIMUM COOLING", "Critical temperature detected. Apply maximum cooling and inspect the pack.", RED, 100


class BatteryPack:
    """Base class holding common battery identity and sensor readings."""
    STATUS_LEVELS = {"Normal", "Warning", "Critical"}

    def __init__(self, vehicle_id, pack_id):
        self.vehicle_id = vehicle_id
        self.pack_id = pack_id
        self.history = []                 # list: battery temperature history
        self.readings = {}                # dictionary: latest sensor parameters
        self.identity = (vehicle_id, pack_id, "Micro-channel liquid cooling")  # tuple

    def update(self, battery_temp, coolant_temp, current, voltage, soc, flow=None, coolant_flow=None):
        # Accept both internal name `flow` and UI/data key `coolant_flow`.
        if coolant_flow is not None:
            flow = coolant_flow
        if flow is None:
            raise ValueError("Coolant flow must be provided.")
        self.readings = {
            "battery_temp": battery_temp,
            "coolant_temp": coolant_temp,
            "current": current,
            "voltage": voltage,
            "soc": soc,
            "coolant_flow": flow,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.history.append(battery_temp)
        if len(self.history) > 60:
            self.history.pop(0)


class MicroChannelBatteryPack(BatteryPack):
    """Derived class adds thermal classification and advisory generation."""
    WARNING_TEMP = 38.0
    CRITICAL_TEMP = 45.0

    def __init__(self, vehicle_id, pack_id):
        super().__init__(vehicle_id, pack_id)
        self.strategies = {
            "Normal": NormalCooling(),
            "Warning": WarningCooling(),
            "Critical": CriticalCooling(),
        }

    def classify(self):
        t = self.readings.get("battery_temp", 25.0)
        coolant = self.readings.get("coolant_temp", 25.0)
        # Illustrative rule-based thermal score, not a learned AI model.
        thermal_score = (lambda temp, delta: temp + max(0, delta) * 0.25)(
            t, t - coolant
        )
        if t >= self.CRITICAL_TEMP or thermal_score >= 46:
            status = "Critical"
        elif t >= self.WARNING_TEMP or thermal_score >= 39:
            status = "Warning"
        else:
            status = "Normal"
        return status, thermal_score

    def analyze(self):
        status, score = self.classify()
        action, explanation, color, cooling_percent = self.strategies[status].recommendation(
            self.readings["battery_temp"], self.readings["coolant_temp"]
        )
        temps = self.history or [self.readings["battery_temp"]]
        # reduce() is used to aggregate readings; protect against empty history.
        total = reduce(lambda a, b: a + b, temps, 0.0)
        average = total / len(temps)
        # map() transforms Celsius readings into Fahrenheit; filter() finds high temps.
        fahrenheit = list(map(lambda c: (c * 9 / 5) + 32, temps))
        hot_readings = list(filter(lambda value: value >= self.WARNING_TEMP, temps))
        return {
            "status": status,
            "score": score,
            "action": action,
            "explanation": explanation,
            "color": color,
            "cooling_percent": cooling_percent,
            "average": average,
            "maximum": max(temps),
            "minimum": min(temps),
            "hot_readings": hot_readings,
            "fahrenheit_latest": fahrenheit[-1],
        }


# ------------------------------ Sensor simulator ----------------------------
class SensorSimulator:
    """Reads synthetic battery samples from thermaliq_battery_dataset.csv.

    If the CSV is missing or invalid, it falls back to generated demo readings.
    Dataset values are educational simulations, not measurements from a real EV.
    """
    def __init__(self, dataset_path=None):
        self.base_temp = 34.0
        self.base_coolant = 27.0
        self.base_current = 85.0
        self.base_voltage = 356.0
        self.base_soc = 78.0
        self.base_flow = 3.2
        self.dataset_path = Path(dataset_path) if dataset_path else Path(__file__).with_name("thermaliq_battery_dataset.csv")
        self.dataset_rows = self._load_dataset()
        self.dataset_index = 0

    def _load_dataset(self):
        required = {"battery_temp", "coolant_temp", "current", "voltage", "soc", "coolant_flow"}
        try:
            with self.dataset_path.open("r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                if not required.issubset(set(reader.fieldnames or [])):
                    return []
                rows = []
                for row in reader:
                    try:
                        rows.append({key: float(row[key]) for key in required})
                    except (ValueError, TypeError, KeyError):
                        continue
                return rows
        except OSError:
            return []

    def sample(self):
        # Cycle through the CSV records, then restart from the beginning.
        if self.dataset_rows:
            reading = self.dataset_rows[self.dataset_index]
            self.dataset_index = (self.dataset_index + 1) % len(self.dataset_rows)
            return {
                "battery_temp": round(reading["battery_temp"], 1),
                "coolant_temp": round(reading["coolant_temp"], 1),
                "current": round(reading["current"], 1),
                "voltage": round(reading["voltage"], 1),
                "soc": round(reading["soc"], 1),
                "coolant_flow": round(reading["coolant_flow"], 2),
            }

        # Fallback if the CSV is unavailable: generate a moving demo sample.
        self.base_temp = min(52.0, max(24.0, self.base_temp + random.uniform(-1.1, 1.5)))
        self.base_coolant = min(40.0, max(18.0, self.base_coolant + random.uniform(-0.6, 0.7)))
        self.base_current = min(220.0, max(0.0, self.base_current + random.uniform(-12, 12)))
        self.base_voltage = min(420.0, max(280.0, self.base_voltage + random.uniform(-2, 2)))
        self.base_soc = min(100.0, max(5.0, self.base_soc + random.uniform(-1.5, 0.4)))
        self.base_flow = min(6.0, max(0.5, self.base_flow + random.uniform(-0.25, 0.25)))
        return {
            "battery_temp": round(self.base_temp, 1),
            "coolant_temp": round(self.base_coolant, 1),
            "current": round(self.base_current, 1),
            "voltage": round(self.base_voltage, 1),
            "soc": round(self.base_soc, 1),
            "coolant_flow": round(self.base_flow, 2),
        }


# ------------------------------ SQLite persistence ---------------------------
class ThermalDatabase:
    """Persist sensor readings and thermal decisions between application runs."""
    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else Path(__file__).with_name("thermaliq_battery.db")
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS thermal_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    battery_temp REAL NOT NULL,
                    coolant_temp REAL NOT NULL,
                    current REAL NOT NULL,
                    voltage REAL NOT NULL,
                    soc REAL NOT NULL,
                    coolant_flow REAL NOT NULL,
                    status TEXT NOT NULL,
                    thermal_score REAL NOT NULL,
                    average_temp REAL NOT NULL,
                    cooling_action TEXT NOT NULL
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_thermal_timestamp ON thermal_readings(timestamp)")

    def insert_reading(self, row):
        fields = ("timestamp", "battery_temp", "coolant_temp", "current", "voltage",
                  "soc", "coolant_flow", "status", "thermal_score", "average_temp", "cooling_action")
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO thermal_readings ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                tuple(row[field] for field in fields)
            )

    def fetch_all(self, limit=5000):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT timestamp, battery_temp, coolant_temp, current, voltage, soc, coolant_flow, "
                "status, thermal_score, average_temp, cooling_action FROM thermal_readings ORDER BY id ASC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]


# ------------------------------ GUI app -------------------------------------
class ThermalIQApp:
    def __init__(self, root):
        self.root = root
        self.root.title("THERMALIQ EV | Battery Thermal Intelligence")
        self.root.geometry("1360x850")
        self.root.minsize(1100, 720)
        self.root.configure(bg=BG)

        self.battery = MicroChannelBatteryPack("EV-074", "BATT-MC-01")
        self.simulator = SensorSimulator()
        self.sensor_queue = queue.Queue()
        self.running = False
        self.worker = None
        self.after_id = None
        self.last_analysis = None
        self.database = ThermalDatabase()
        self.events = self.database.fetch_all()
        self.active_page = "Overview"
        self.theme_mode = "dark"

        self._configure_styles()
        self._build_layout()
        self._seed_demo_data()
        self._render_dashboard()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._bind_shortcuts()
        self.root.after(250, self._poll_sensor_queue)


    def _toggle_theme(self):
        """Switch the complete Tkinter dashboard between dark and light palettes."""
        global BG, PANEL, PANEL2, BORDER, TEXT, MUTED, CYAN, BLUE, GREEN, AMBER, RED, PURPLE
        current_page = self.active_page
        if self.theme_mode == "dark":
            palette = {
                "BG": "#edf2fb", "PANEL": "#ffffff", "PANEL2": "#f5f8fd",
                "BORDER": "#dce4f2", "TEXT": "#17243b", "MUTED": "#6b7891",
                "CYAN": "#08a9a2", "BLUE": "#3478f6", "GREEN": "#168957",
                "AMBER": "#a86a00", "RED": "#c8324b", "PURPLE": "#8357e8"
            }
            self.theme_mode = "light"
        else:
            palette = {
                "BG": "#0b1220", "PANEL": "#111c2f", "PANEL2": "#17243a",
                "BORDER": "#263650", "TEXT": "#edf4ff", "MUTED": "#9eb0c9",
                "CYAN": "#42d6c5", "BLUE": "#5ba7ff", "GREEN": "#4bd49a",
                "AMBER": "#ffbf5f", "RED": "#ff667a", "PURPLE": "#b79cff"
            }
            self.theme_mode = "dark"
        for name, value in palette.items():
            globals()[name] = value
        # Rebuild widgets with the selected palette while preserving the model and history.
        for child in self.root.winfo_children():
            child.destroy()
        self.root.configure(bg=BG)
        self._configure_styles()
        self._build_layout()
        self._show_page(current_page)
        self._render_dashboard()
        if hasattr(self, "theme_btn"):
            self.theme_btn.configure(text="☀ Light mode" if self.theme_mode == "dark" else "☾ Dark mode")

    def _configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", background=PANEL, foreground=TEXT,
                        fieldbackground=PANEL, rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL2, foreground=TEXT,
                        font=FONT_BOLD, relief="flat")
        style.map("Treeview", background=[("selected", "#244a65")],
                  foreground=[("selected", TEXT)])
        style.configure("Horizontal.TProgressbar", troughcolor=PANEL2,
                        background=CYAN, bordercolor=PANEL2, lightcolor=CYAN,
                        darkcolor=CYAN)

    def _build_layout(self):
        # Header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 12))
        logo = tk.Canvas(header, width=44, height=44, bg=BG, highlightthickness=0)
        logo.pack(side="left", padx=(0, 12))
        logo.create_oval(4, 4, 40, 40, outline=CYAN, width=2)
        logo.create_line(22, 10, 22, 28, fill=TEXT, width=4)
        logo.create_oval(15, 24, 29, 38, fill=RED, outline=RED)
        logo.create_line(22, 13, 22, 30, fill=RED, width=3)
        titlebox = tk.Frame(header, bg=BG)
        titlebox.pack(side="left")
        tk.Label(titlebox, text="THERMALIQ EV", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(titlebox, text="AI-ENABLED MICRO-CHANNEL BATTERY THERMAL MANAGEMENT",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(2, 0))
        self.theme_btn = tk.Button(header, text="☀ Light mode", command=self._toggle_theme,
                                   bg=PANEL2, fg=TEXT, activebackground=BORDER,
                                   activeforeground=TEXT, relief="flat", bd=0,
                                   font=FONT_BOLD, padx=12, pady=8, cursor="hand2")
        self.theme_btn.configure(text="☀ Light mode" if self.theme_mode == "dark" else "☾ Dark mode")
        self.theme_btn.pack(side="right", padx=(10, 0))
        self.clock_label = tk.Label(header, text="", bg=BG, fg=MUTED, font=FONT)
        self.clock_label.pack(side="right", padx=(8, 0))
        self._update_clock()

        # Main content: sidebar + page area
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.sidebar = tk.Frame(body, bg=PANEL, width=190)
        self.sidebar.pack(side="left", fill="y", padx=(0, 16))
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="WORKSPACE", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18, pady=(22, 12))
        for page, symbol in [("Overview", "◈"), ("Live Monitor", "⌁"),
                             ("Thermal History", "▤"), ("Alerts & Insights", "⚑"),
                             ("System Info", "ⓘ")]:
            btn = tk.Button(self.sidebar, text=f"  {symbol}   {page}", anchor="w",
                            command=lambda p=page: self._show_page(p),
                            bg=PANEL, fg=TEXT, activebackground=PANEL2,
                            activeforeground=CYAN, relief="flat", bd=0,
                            font=FONT, padx=12, pady=12, cursor="hand2")
            btn.pack(fill="x", padx=8, pady=2)
            setattr(self, f"nav_{page.lower().replace(' ', '_')}", btn)
        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", padx=16, pady=18)
        tk.Label(self.sidebar, text="DEMO CONTROLS", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=18, pady=(0, 10))
        self.start_btn = tk.Button(self.sidebar, text="▶  Start Simulation",
                                   command=self.start_simulation, bg=CYAN, fg=BG,
                                   activebackground="#6ce8da", relief="flat",
                                   font=FONT_BOLD, padx=8, pady=10, cursor="hand2")
        self.start_btn.pack(fill="x", padx=12, pady=4)
        self.stop_btn = tk.Button(self.sidebar, text="■  Stop Simulation",
                                  command=self.stop_simulation, bg=PANEL2, fg=TEXT,
                                  activebackground=BORDER, relief="flat",
                                  font=FONT_BOLD, padx=8, pady=10, cursor="hand2",
                                  state="disabled")
        self.stop_btn.pack(fill="x", padx=12, pady=4)
        tk.Button(self.sidebar, text="↻  New Sensor Sample", command=self.take_sample,
                  bg=PANEL2, fg=TEXT, activebackground=BORDER, relief="flat",
                  font=FONT, padx=8, pady=9, cursor="hand2").pack(fill="x", padx=12, pady=4)
        tk.Button(self.sidebar, text="⇩  Export CSV", command=self.export_csv,
                  bg=PANEL2, fg=TEXT, activebackground=BORDER, relief="flat",
                  font=FONT, padx=8, pady=9, cursor="hand2").pack(fill="x", padx=12, pady=4)
        tk.Label(self.sidebar, text="SIMULATED SENSORS\nRule-based educational demo",
                 bg=PANEL, fg=MUTED, justify="left",
                 font=("Segoe UI", 8)).pack(side="bottom", anchor="w", padx=16, pady=18)

        self.page_area = tk.Frame(body, bg=BG)
        self.page_area.pack(side="left", fill="both", expand=True)
        self._show_page("Overview")

    def _card(self, parent, title, value, unit="", accent=CYAN, subtitle=""):
        card = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(card, text=title.upper(), bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(14, 7))
        row = tk.Frame(card, bg=PANEL)
        row.pack(anchor="w", padx=16)
        val = tk.Label(row, text=value, bg=PANEL, fg=accent,
                       font=("Segoe UI", 22, "bold"))
        val.pack(side="left")
        if unit:
            tk.Label(row, text=unit, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 10)).pack(side="left", padx=(5, 0), pady=(7, 0))
        tk.Label(card, text=subtitle, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(5, 14))
        return card, val

    def _show_page(self, page):
        self.active_page = page
        for child in self.page_area.winfo_children():
            child.destroy()
        for nav_page in ("overview", "live_monitor", "thermal_history", "alerts_&_insights", "system_info"):
            btn = getattr(self, "nav_" + nav_page, None)
            if btn:
                btn.configure(bg=PANEL2 if nav_page.replace("_", " ").title() == page else PANEL,
                              fg=CYAN if nav_page.replace("_", " ").title() == page else TEXT)
        if page == "Overview":
            self._build_overview()
        elif page == "Live Monitor":
            self._build_live_monitor()
        elif page == "Thermal History":
            self._build_history()
        elif page == "Alerts & Insights":
            self._build_alerts_insights()
        else:
            self._build_system_info()

    def _page_heading(self, title, subtitle):
        tk.Label(self.page_area, text=title, bg=BG, fg=TEXT,
                 font=FONT_TITLE).pack(anchor="w", pady=(4, 3))
        tk.Label(self.page_area, text=subtitle, bg=BG, fg=MUTED,
                 font=FONT).pack(anchor="w", pady=(0, 16))

    def _build_overview(self):
        self._page_heading("Battery intelligence overview",
                           "Monitor pack conditions, detect thermal risk, and review cooling recommendations.")
        self.status_banner = tk.Frame(self.page_area, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        self.status_banner.pack(fill="x", pady=(0, 14))
        self.status_dot = tk.Label(self.status_banner, text="●", bg=PANEL, fg=GREEN, font=("Segoe UI", 20))
        self.status_dot.pack(side="left", padx=(16, 10), pady=13)
        status_text = tk.Frame(self.status_banner, bg=PANEL)
        status_text.pack(side="left", fill="x", expand=True, pady=12)
        self.status_title = tk.Label(status_text, text="NORMAL · THERMAL STATUS",
                                     bg=PANEL, fg=GREEN, font=FONT_BOLD)
        self.status_title.pack(anchor="w")
        self.status_detail = tk.Label(status_text, text="Waiting for sensor analysis",
                                      bg=PANEL, fg=MUTED, font=FONT)
        self.status_detail.pack(anchor="w", pady=(3, 0))
        self.action_badge = tk.Label(self.status_banner, text="NO COOLING",
                                     bg="#173d3b", fg=CYAN, font=FONT_BOLD, padx=14, pady=8)
        self.action_badge.pack(side="right", padx=16)

        cards = tk.Frame(self.page_area, bg=BG)
        cards.pack(fill="x", pady=(0, 14))
        card_specs = [
            ("Battery temperature", "—", "°C", RED, "Pack temperature"),
            ("Coolant temperature", "—", "°C", BLUE, "Micro-channel inlet"),
            ("Battery current", "—", "A", PURPLE, "Simulated sensor"),
            ("Battery voltage", "—", "V", CYAN, "Pack voltage"),
            ("State of charge", "—", "%", GREEN, "Estimated remaining charge"),
            ("Coolant flow", "—", "L/min", AMBER, "Micro-channel flow rate"),
        ]
        self.metric_values = {}
        for i, (title, val, unit, color, sub) in enumerate(card_specs):
            card, value_label = self._card(cards, title, val, unit, color, sub)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0), pady=0)
            cards.grid_columnconfigure(i, weight=1, uniform="metrics")
            self.metric_values[title] = value_label

        lower = tk.Frame(self.page_area, bg=BG)
        lower.pack(fill="both", expand=True)
        left = tk.Frame(lower, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = tk.Frame(lower, bg=PANEL, width=280, highlightbackground=BORDER, highlightthickness=1)
        right.pack(side="left", fill="y", padx=(8, 0))
        tk.Label(left, text="TEMPERATURE TREND", bg=PANEL, fg=TEXT,
                 font=FONT_BOLD).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(left, text="Recent simulated battery readings · °C", bg=PANEL,
                 fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(3, 0))
        self.chart = tk.Canvas(left, bg=PANEL, height=230, highlightthickness=0)
        self.chart.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(right, text="THERMAL DIAGNOSTICS", bg=PANEL, fg=TEXT,
                 font=FONT_BOLD).pack(anchor="w", padx=16, pady=(14, 12))
        self.avg_label = self._diagnostic_row(right, "Average temperature", "—")
        self.max_label = self._diagnostic_row(right, "Peak temperature", "—")
        self.score_label = self._diagnostic_row(right, "Thermal score", "—")
        self.cooling_label = self._diagnostic_row(right, "Cooling demand", "—")
        tk.Frame(right, bg=BORDER, height=1).pack(fill="x", padx=16, pady=10)
        tk.Label(right, text="COOLING OUTPUT", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16)
        self.cooling_bar = ttk.Progressbar(right, maximum=100, mode="determinate")
        self.cooling_bar.pack(fill="x", padx=16, pady=(8, 4))
        self.cooling_percent_label = tk.Label(right, text="0% commanded (simulated)",
                                               bg=PANEL, fg=MUTED, font=("Segoe UI", 8))
        self.cooling_percent_label.pack(anchor="w", padx=16, pady=(0, 14))

    def _diagnostic_row(self, parent, label, value):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=16, pady=5)
        tk.Label(row, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        val = tk.Label(row, text=value, bg=PANEL, fg=TEXT, font=FONT_BOLD)
        val.pack(side="right")
        return val

    def _build_live_monitor(self):
        self._page_heading("Live sensor monitor",
                           "Sensor values are generated locally for demonstration. No vehicle hardware is connected.")
        controls = tk.Frame(self.page_area, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        controls.pack(fill="x", pady=(0, 14))
        tk.Label(controls, text="MANUAL SENSOR INPUT", bg=PANEL, fg=TEXT,
                 font=FONT_BOLD).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(14, 8))
        self.manual_vars = {}
        fields = [
            ("Battery temperature (°C)", "battery_temp", "34.0"),
            ("Coolant temperature (°C)", "coolant_temp", "27.0"),
            ("Battery current (A)", "current", "85.0"),
            ("Battery voltage (V)", "voltage", "356.0"),
            ("State of charge (%)", "soc", "78.0"),
            ("Coolant flow (L/min)", "coolant_flow", "3.2"),
        ]
        for i, (label, key, default) in enumerate(fields):
            r, c = 1 + i // 3, (i % 3) * 2
            tk.Label(controls, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).grid(
                row=r, column=c, sticky="w", padx=(16, 8), pady=7)
            var = tk.StringVar(value=default)
            self.manual_vars[key] = var
            ent = tk.Entry(controls, textvariable=var, bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                           relief="flat", font=FONT, width=12)
            ent.grid(row=r, column=c+1, sticky="ew", padx=(0, 16), pady=7, ipady=7)
        for c in range(6):
            controls.grid_columnconfigure(c, weight=1)
        tk.Button(controls, text="Analyze Entered Values", command=self.analyze_manual,
                  bg=CYAN, fg=BG, activebackground="#6ce8da", relief="flat",
                  font=FONT_BOLD, padx=14, pady=9, cursor="hand2").grid(
                      row=3, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 16))
        tk.Button(controls, text="Load Random Sample", command=self.load_manual_sample,
                  bg=PANEL2, fg=TEXT, activebackground=BORDER, relief="flat",
                  font=FONT, padx=14, pady=9, cursor="hand2").grid(
                      row=3, column=2, columnspan=2, sticky="w", padx=8, pady=(12, 16))
        self.manual_result = tk.Text(self.page_area, height=12, bg=PANEL, fg=TEXT,
                                     insertbackground=TEXT, relief="flat", wrap="word",
                                     font=("Consolas", 10), padx=14, pady=12)
        self.manual_result.pack(fill="both", expand=True)
        self.manual_result.insert("end", "Enter sensor values above and select Analyze Entered Values.\n")
        self.manual_result.configure(state="disabled")

    def _build_history(self):
        self._page_heading("Thermal history & event log",
                           "Readings are saved in SQLite and restored automatically when you reopen the dashboard.")
        toolbar = tk.Frame(self.page_area, bg=BG)
        toolbar.pack(fill="x", pady=(0, 10))
        tk.Label(toolbar, text=f"SQLITE DATABASE · {len(self.events)} SAVED READINGS", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(toolbar, text="Export history as CSV", command=self.export_csv,
                  bg=PANEL2, fg=TEXT, activebackground=BORDER, relief="flat",
                  font=FONT, padx=12, pady=7).pack(side="right")
        columns = ("time", "temp", "coolant", "current", "voltage", "soc", "status", "action")
        self.history_tree = ttk.Treeview(self.page_area, columns=columns, show="headings")
        headings = {
            "time": "Timestamp", "temp": "Battery °C", "coolant": "Coolant °C",
            "current": "Current A", "voltage": "Voltage V", "soc": "SOC %",
            "status": "Thermal status", "action": "Cooling action"
        }
        widths = {"time": 145, "temp": 90, "coolant": 90, "current": 85,
                  "voltage": 85, "soc": 70, "status": 105, "action": 190}
        for col in columns:
            self.history_tree.heading(col, text=headings[col])
            self.history_tree.column(col, width=widths[col], anchor="center")
        self.history_tree.pack(fill="both", expand=True)
        self.history_tree.tag_configure("Critical", foreground=RED)
        self.history_tree.tag_configure("Warning", foreground=AMBER)
        self.history_tree.tag_configure("Normal", foreground=GREEN)
        self._refresh_history_table()

    def _build_alerts_insights(self):
        self._page_heading(
            "Alerts & thermal insights",
            "Explore thermal states, trigger demonstration scenarios, and understand the rule-based decision engine."
        )
        current = self.battery.analyze()
        self.alert_status_card = tk.Frame(
            self.page_area, bg=PANEL, highlightbackground=current["color"], highlightthickness=1
        )
        self.alert_status_card.pack(fill="x", pady=(0, 14))
        tk.Label(self.alert_status_card, text="CURRENT THERMAL ASSESSMENT",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(
                     anchor="w", padx=18, pady=(14, 4))
        self.alert_status_title = tk.Label(
            self.alert_status_card, text="", bg=PANEL, fg=current["color"],
            font=("Segoe UI", 18, "bold")
        )
        self.alert_status_title.pack(anchor="w", padx=18)
        self.alert_status_detail = tk.Label(
            self.alert_status_card, text="", bg=PANEL, fg=TEXT,
            font=FONT, justify="left", wraplength=900
        )
        self.alert_status_detail.pack(anchor="w", padx=18, pady=(4, 14))

        scenarios = tk.Frame(self.page_area, bg=BG)
        scenarios.pack(fill="x", pady=(0, 14))
        tk.Label(scenarios, text="DEMO SCENARIOS", bg=BG, fg=TEXT,
                 font=FONT_BOLD).pack(anchor="w", pady=(0, 8))
        tk.Label(scenarios, text="Use these buttons to demonstrate how the status changes at different temperatures.",
                 bg=BG, fg=MUTED, font=FONT).pack(anchor="w", pady=(0, 8))
        buttons = tk.Frame(scenarios, bg=BG)
        buttons.pack(anchor="w")
        tk.Button(buttons, text="●  Normal · 34°C", command=lambda: self.load_scenario(34.0),
                  bg="#173d3b", fg=GREEN, activebackground=PANEL2, relief="flat",
                  font=FONT_BOLD, padx=14, pady=10, cursor="hand2").pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="▲  Warning · 41°C", command=lambda: self.load_scenario(41.0),
                  bg="#46371f", fg=AMBER, activebackground=PANEL2, relief="flat",
                  font=FONT_BOLD, padx=14, pady=10, cursor="hand2").pack(side="left", padx=8)
        tk.Button(buttons, text="◆  Critical · 47°C", command=lambda: self.load_scenario(47.0),
                  bg="#48232d", fg=RED, activebackground=PANEL2, relief="flat",
                  font=FONT_BOLD, padx=14, pady=10, cursor="hand2").pack(side="left", padx=8)

        lower = tk.Frame(self.page_area, bg=BG)
        lower.pack(fill="both", expand=True)
        guide = tk.Frame(lower, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        guide.pack(side="left", fill="both", expand=True, padx=(0, 8))
        log = tk.Frame(lower, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        log.pack(side="left", fill="both", expand=True, padx=(8, 0))
        tk.Label(guide, text="DECISION RULES", bg=PANEL, fg=TEXT, font=FONT_BOLD).pack(
            anchor="w", padx=16, pady=(14, 8))
        rule_rows = [
            (GREEN, "NORMAL", "Battery temperature below 38°C and score below warning level."),
            (AMBER, "WARNING", "Battery temperature reaches 38°C, or the thermal score reaches 39."),
            (RED, "CRITICAL", "Battery temperature reaches 45°C, or the thermal score reaches 46."),
        ]
        for color, title, detail in rule_rows:
            row = tk.Frame(guide, bg=PANEL)
            row.pack(fill="x", padx=16, pady=6)
            tk.Label(row, text="●", bg=PANEL, fg=color, font=FONT_BOLD).pack(side="left", padx=(0, 8))
            tk.Label(row, text=title, bg=PANEL, fg=color, font=FONT_BOLD, width=9, anchor="w").pack(side="left")
            tk.Label(row, text=detail, bg=PANEL, fg=TEXT, font=("Segoe UI", 9),
                     justify="left", wraplength=360).pack(side="left", fill="x", expand=True)
        tk.Label(guide, text="The score = battery temperature + 25% of any positive battery-to-coolant temperature gap.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9), justify="left",
                 wraplength=460).pack(anchor="w", padx=16, pady=(10, 14))
        tk.Label(log, text="RECENT EVENTS", bg=PANEL, fg=TEXT, font=FONT_BOLD).pack(
            anchor="w", padx=16, pady=(14, 8))
        self.alert_events_text = tk.Text(log, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                                         relief="flat", wrap="word", font=("Consolas", 9),
                                         height=10, padx=14, pady=8)
        self.alert_events_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.alert_events_text.configure(state="disabled")
        self._refresh_alerts_page()

    def load_scenario(self, temperature):
        # A controlled demo sample makes each thermal state easy to show in a viva.
        base = self.battery.readings or self.simulator.sample()
        reading = dict(base)
        # Stored readings include a timestamp, but update() creates a fresh one.
        reading.pop("timestamp", None)
        reading["battery_temp"] = temperature
        reading["coolant_temp"] = 27.0 if temperature < 40 else 29.0 if temperature < 45 else 31.0
        reading["current"] = 85.0 if temperature < 40 else 145.0 if temperature < 45 else 190.0
        reading["voltage"] = 356.0 if temperature < 40 else 348.0 if temperature < 45 else 335.0
        reading["soc"] = 78.0
        reading["coolant_flow"] = 3.2 if temperature < 40 else 4.2 if temperature < 45 else 5.8
        self._apply_reading(reading)

    def _refresh_alerts_page(self):
        if not hasattr(self, "alert_status_title") or not self.alert_status_title.winfo_exists():
            return
        analysis = self.battery.analyze()
        self.alert_status_title.configure(
            text=f'{analysis["status"].upper()}  |  {analysis["action"]}',
            fg=analysis["color"]
        )
        self.alert_status_detail.configure(
            text=f'Battery: {self.battery.readings["battery_temp"]:.1f}°C   •   '
                 f'Coolant: {self.battery.readings["coolant_temp"]:.1f}°C   •   '
                 f'Thermal score: {analysis["score"]:.1f}\n{analysis["explanation"]}'
        )
        self.alert_status_card.configure(highlightbackground=analysis["color"])
        lines = []
        for event in reversed(self.events[-8:]):
            lines.append(
                f'{event.get("timestamp", "")}  |  {event.get("status", "")}\n'
                f'  {event.get("battery_temp", 0):.1f}°C  →  {event.get("cooling_action", "")}\n'
            )
        if not lines:
            lines = ["No events recorded yet."]
        self.alert_events_text.configure(state="normal")
        self.alert_events_text.delete("1.0", "end")
        self.alert_events_text.insert("end", "\n".join(lines))
        self.alert_events_text.configure(state="disabled")

    def _build_system_info(self):
        self._page_heading("System information",
                           "Project notes, OOP design choices, and the experiments demonstrated in this software.")
        info = tk.Frame(self.page_area, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        info.pack(fill="both", expand=True)
        sections = [
            ("PROJECT", "THERMALIQ EV — AI-Enabled Micro-channel Battery Thermal Management System for Electric Vehicles."),
            ("SIMULATION NOTICE", "Sensor data is simulated. Thermal classification uses transparent example thresholds; it is not a trained machine-learning model, a validated electro-thermal simulation, or a safety-certified controller."),
            ("OOP CONCEPTS", "Classes and objects: BatteryPack and MicroChannelBatteryPack. Inheritance: the micro-channel pack extends the base pack. Abstraction: ThermalStrategy defines a required recommendation() interface. Polymorphism: NormalCooling, WarningCooling, and CriticalCooling implement the same interface differently. Encapsulation: sensor state and analysis live in classes."),
            ("COLLECTIONS + FUNCTIONAL PROGRAMMING", "List: temperature history. Tuple: vehicle/battery identity. Dictionary: latest sensor parameters. Set: supported thermal statuses. lambda: thermal score and transformations. map(): Celsius-to-Fahrenheit conversion. filter(): high-temperature readings. reduce(): aggregate temperature."),
            ("DATABASE + SOFTWARE PRACTICES", f"SQLite database file: {self.database.db_path.name}. Every processed reading and thermal decision is saved in the thermal_readings table and restored on the next launch. Tkinter widgets and Canvas trend chart. Threaded sensor simulation with a queue to safely pass readings to the GUI. Exception handling for manual input. CSV export for saved history."),
            ("BUTTONS + KEYBOARD SHORTCUTS", "Sidebar: Start Simulation begins automatic sample updates every 2 seconds; Stop Simulation pauses them; New Sensor Sample adds one reading; Export CSV saves the session log. Live Monitor: Analyze Entered Values validates and analyses the six entered values; Load Random Sample fills the form and analyses it. Thermal History: Export history as CSV saves readings. Alerts & Insights: Normal/Warning/Critical scenario buttons load example temperatures. Shortcuts: Ctrl+1 Overview, Ctrl+2 Live Monitor, Ctrl+3 Thermal History, Ctrl+4 Alerts & Insights, Ctrl+5 System Info, Ctrl+E export CSV, N new sample, Space start/stop simulation, F1 System Info. Shortcuts are ignored while typing in text fields."),
            ("ILLUSTRATIVE THRESHOLDS", "Normal: below 38°C. Warning: 38°C to below 45°C. Critical: 45°C and above. The thermal score can also raise a status earlier. These values are chosen for the mini-project demonstration only and must not be used to control a real EV battery."),
        ]
        for title, body in sections:
            tk.Label(info, text=title, bg=PANEL, fg=CYAN, font=FONT_BOLD).pack(anchor="w", padx=20, pady=(17, 4))
            tk.Label(info, text=body, bg=PANEL, fg=TEXT, font=FONT,
                     justify="left", wraplength=850).pack(anchor="w", padx=20, pady=(0, 2))

    def _seed_demo_data(self):
        # Restore the last saved sensor state and temperature history on startup.
        if self.events:
            latest = self.events[-1]
            self.battery.update(
                battery_temp=latest["battery_temp"], coolant_temp=latest["coolant_temp"],
                current=latest["current"], voltage=latest["voltage"], soc=latest["soc"],
                coolant_flow=latest["coolant_flow"]
            )
            self.battery.readings["timestamp"] = latest["timestamp"]
            self.battery.history = [row["battery_temp"] for row in self.events[-60:]]
            self.last_analysis = self.battery.analyze()
            return

        # First launch: seed the initial dashboard history from the CSV dataset.
        for _ in range(min(5, len(self.simulator.dataset_rows))):
            self.battery.update(**self.simulator.sample())
        if not self.battery.readings:
            # Safe fallback when the dataset is missing or empty.
            for sample in [
                {"battery_temp": 32.8, "coolant_temp": 26.1, "current": 72.0, "voltage": 358.0, "soc": 82.0, "coolant_flow": 2.8},
                {"battery_temp": 33.4, "coolant_temp": 26.3, "current": 81.0, "voltage": 357.0, "soc": 81.0, "coolant_flow": 2.9},
                {"battery_temp": 34.1, "coolant_temp": 26.8, "current": 88.0, "voltage": 356.0, "soc": 80.0, "coolant_flow": 3.0},
                {"battery_temp": 35.0, "coolant_temp": 27.0, "current": 92.0, "voltage": 355.0, "soc": 79.0, "coolant_flow": 3.1},
                {"battery_temp": 34.6, "coolant_temp": 27.2, "current": 86.0, "voltage": 356.0, "soc": 78.0, "coolant_flow": 3.2},
            ]:
                self.battery.update(**sample)
        self._record_event()

    def _record_event(self):
        if not self.battery.readings:
            return
        analysis = self.battery.analyze()
        row = dict(self.battery.readings)
        row.update({
            "status": analysis["status"],
            "thermal_score": round(analysis["score"], 2),
            "average_temp": round(analysis["average"], 2),
            "cooling_action": analysis["action"],
        })
        self.events.append(row)
        try:
            self.database.insert_reading(row)
        except (sqlite3.Error, KeyError) as exc:
            messagebox.showerror(
                "Database save error",
                f"The reading is visible for this session but could not be saved to SQLite:\\n{exc}"
            )
        self.last_analysis = analysis

    def _apply_reading(self, reading):
        try:
            self.battery.update(**reading)
            self._record_event()
            self._render_dashboard()
            if self.active_page == "Thermal History":
                self._refresh_history_table()
            elif self.active_page == "Alerts & Insights":
                self._refresh_alerts_page()
        except (KeyError, TypeError, ValueError) as exc:
            messagebox.showerror("Sensor processing error", f"Could not process the sensor reading:\n{exc}")

    def _render_dashboard(self):
        if not self.battery.readings:
            return
        a = self.battery.analyze()
        r = self.battery.readings
        for title, key, fmt in [
            ("Battery temperature", "battery_temp", "{:.1f}"),
            ("Coolant temperature", "coolant_temp", "{:.1f}"),
            ("Battery current", "current", "{:.1f}"),
            ("Battery voltage", "voltage", "{:.1f}"),
            ("State of charge", "soc", "{:.1f}"),
            ("Coolant flow", "coolant_flow", "{:.2f}"),
        ]:
            label = self.metric_values.get(title)
            if label and label.winfo_exists():
                label.configure(text=fmt.format(r[key]))
        if hasattr(self, "status_title") and self.status_title.winfo_exists():
            color = a["color"]
            self.status_dot.configure(fg=color)
            self.status_title.configure(text=f'{a["status"].upper()} · THERMAL STATUS', fg=color)
            self.status_detail.configure(text=a["explanation"])
            self.action_badge.configure(text=a["action"],
                                        bg="#173d3b" if a["status"] == "Normal" else
                                           "#46371f" if a["status"] == "Warning" else "#48232d",
                                        fg=color)
            self.avg_label.configure(text=f'{a["average"]:.1f} °C')
            self.max_label.configure(text=f'{a["maximum"]:.1f} °C')
            self.score_label.configure(text=f'{a["score"]:.1f}')
            self.cooling_label.configure(text=f'{a["cooling_percent"]}%')
            self.cooling_bar["value"] = a["cooling_percent"]
            self.cooling_percent_label.configure(text=f'{a["cooling_percent"]}% commanded (simulated)')
            self._draw_chart()

    def _draw_chart(self):
        if not hasattr(self, "chart") or not self.chart.winfo_exists():
            return
        canvas = self.chart
        canvas.delete("all")
        w = max(canvas.winfo_width(), 360)
        h = max(canvas.winfo_height(), 180)
        temps = self.battery.history[-30:]
        if len(temps) < 2:
            return
        lo = min(20, min(temps) - 2)
        hi = max(50, max(temps) + 2)
        left, right, top, bottom = 42, w - 16, 16, h - 30
        for val in (20, 30, 40, 50):
            y = bottom - (val - lo) / max(hi - lo, 1) * (bottom - top)
            canvas.create_line(left, y, right, y, fill=BORDER, dash=(3, 4))
            canvas.create_text(left - 8, y, text=str(val), fill=MUTED, anchor="e", font=("Segoe UI", 8))
        pts = []
        for i, temp in enumerate(temps):
            x = left + i * (right - left) / max(len(temps) - 1, 1)
            y = bottom - (temp - lo) / max(hi - lo, 1) * (bottom - top)
            pts.extend([x, y])
        canvas.create_line(*pts, fill=CYAN, width=2, smooth=True)
        for i in range(0, len(pts), 2):
            canvas.create_oval(pts[i]-3, pts[i+1]-3, pts[i]+3, pts[i+1]+3,
                               fill=CYAN, outline=CYAN)
        threshold_y = bottom - (MicroChannelBatteryPack.WARNING_TEMP - lo) / max(hi - lo, 1) * (bottom - top)
        canvas.create_line(left, threshold_y, right, threshold_y, fill=AMBER, dash=(5, 3))
        canvas.create_text(right, top, text="BATTERY TEMP · °C", fill=MUTED,
                           anchor="ne", font=("Segoe UI", 8))

    def _refresh_history_table(self):
        if not hasattr(self, "history_tree") or not self.history_tree.winfo_exists():
            return
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        for row in reversed(self.events[-150:]):
            self.history_tree.insert("", "end", values=(
                row.get("timestamp", ""), f'{row.get("battery_temp", 0):.1f}',
                f'{row.get("coolant_temp", 0):.1f}', f'{row.get("current", 0):.1f}',
                f'{row.get("voltage", 0):.1f}', f'{row.get("soc", 0):.1f}',
                row.get("status", ""), row.get("cooling_action", "")
            ), tags=(row.get("status", "Normal"),))

    def take_sample(self):
        self._apply_reading(self.simulator.sample())

    def load_manual_sample(self):
        sample = self.simulator.sample()
        for key, value in sample.items():
            self.manual_vars[key].set(str(value))
        self.analyze_manual()

    def analyze_manual(self):
        try:
            reading = {key: float(var.get().strip()) for key, var in self.manual_vars.items()}
            limits = {
                "battery_temp": (-20, 100), "coolant_temp": (-20, 80),
                "current": (0, 1000), "voltage": (0, 1000),
                "soc": (0, 100), "coolant_flow": (0, 50)
            }
            for key, value in reading.items():
                low, high = limits[key]
                if not math.isfinite(value) or not low <= value <= high:
                    raise ValueError(f"{key.replace('_', ' ').title()} must be between {low} and {high}.")
            self._apply_reading(reading)
            a = self.battery.analyze()
            r = self.battery.readings
            report = (
                "THERMAL MANAGEMENT ANALYSIS\n"
                "────────────────────────────────────────────\n"
                f"Vehicle / pack      : {self.battery.vehicle_id} / {self.battery.pack_id}\n"
                f"Battery temperature : {r['battery_temp']:.1f} °C ({a['fahrenheit_latest']:.1f} °F)\n"
                f"Coolant temperature : {r['coolant_temp']:.1f} °C\n"
                f"Battery current     : {r['current']:.1f} A\n"
                f"Battery voltage     : {r['voltage']:.1f} V\n"
                f"State of charge     : {r['soc']:.1f}%\n"
                f"Coolant flow        : {r['coolant_flow']:.2f} L/min\n\n"
                f"Thermal status      : {a['status']}\n"
                f"Thermal score       : {a['score']:.2f} (illustrative)\n"
                f"Cooling action      : {a['action']}\n"
                f"Cooling demand      : {a['cooling_percent']}%\n"
                f"Average temp history: {a['average']:.2f} °C\n"
                f"Peak temp history   : {a['maximum']:.1f} °C\n"
                f"High-temp readings  : {a['hot_readings']}\n\n"
                f"Advisory: {a['explanation']}\n\n"
                "Note: simulated data and educational thresholds only; not for real vehicle control."
            )
            if hasattr(self, "manual_result") and self.manual_result.winfo_exists():
                self.manual_result.configure(state="normal")
                self.manual_result.delete("1.0", "end")
                self.manual_result.insert("end", report)
                self.manual_result.configure(state="disabled")
        except ValueError as exc:
            messagebox.showerror("Invalid sensor input", str(exc))
        except Exception as exc:
            messagebox.showerror("Analysis error", f"Unexpected issue while analyzing values:\n{exc}")

    def start_simulation(self):
        if self.running:
            return
        self.running = True
        self.start_btn.configure(state="disabled", text="●  Simulation Running")
        self.stop_btn.configure(state="normal")
        self.worker = threading.Thread(target=self._sensor_worker, daemon=True)
        self.worker.start()

    def _sensor_worker(self):
        while self.running:
            self.sensor_queue.put(self.simulator.sample())
            time.sleep(2.0)

    def _poll_sensor_queue(self):
        try:
            while True:
                reading = self.sensor_queue.get_nowait()
                self._apply_reading(reading)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after_id = self.root.after(250, self._poll_sensor_queue)

    def stop_simulation(self):
        self.running = False
        self.start_btn.configure(state="normal", text="▶  Start Simulation")
        self.stop_btn.configure(state="disabled")

    def export_csv(self):
        if not self.events:
            messagebox.showinfo("No history", "There are no readings to export yet.")
            return
        path = filedialog.asksaveasfilename(
            title="Export thermal history", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="thermaliq_battery_history.csv"
        )
        if not path:
            return
        fields = ["timestamp", "battery_temp", "coolant_temp", "current", "voltage",
                  "soc", "coolant_flow", "status", "thermal_score", "average_temp", "cooling_action"]
        try:
            with open(path, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self.events)
            messagebox.showinfo("Export complete", f"Exported {len(self.events)} readings to:\n{path}")
        except OSError as exc:
            messagebox.showerror("Export failed", f"Could not write the CSV file:\n{exc}")

    def _bind_shortcuts(self):
        """Keyboard shortcuts; ignored while typing into an Entry/Text field."""
        modifier = "Command" if sys.platform == "darwin" else "Control"
        self.root.bind_all(f"<{modifier}-Key-1>", lambda event: self._shortcut_page("Overview", event))
        self.root.bind_all(f"<{modifier}-Key-2>", lambda event: self._shortcut_page("Live Monitor", event))
        self.root.bind_all(f"<{modifier}-Key-3>", lambda event: self._shortcut_page("Thermal History", event))
        self.root.bind_all(f"<{modifier}-Key-4>", lambda event: self._shortcut_page("Alerts & Insights", event))
        self.root.bind_all(f"<{modifier}-Key-5>", lambda event: self._shortcut_page("System Info", event))
        self.root.bind_all(f"<{modifier}-e>", self._shortcut_export)
        self.root.bind_all(f"<{modifier}-E>", self._shortcut_export)
        self.root.bind_all("<KeyPress-n>", self._shortcut_sample)
        self.root.bind_all("<KeyPress-N>", self._shortcut_sample)
        self.root.bind_all("<space>", self._shortcut_toggle_simulation)
        self.root.bind_all("<F1>", lambda event: self._shortcut_page("System Info", event))

    def _typing_in_text_field(self, event):
        widget = getattr(event, "widget", None)
        return isinstance(widget, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox))

    def _shortcut_page(self, page, event=None):
        if event is not None and self._typing_in_text_field(event):
            return None
        self._show_page(page)
        return "break"

    def _shortcut_export(self, event=None):
        if event is not None and self._typing_in_text_field(event):
            return None
        self.export_csv()
        return "break"

    def _shortcut_sample(self, event=None):
        if event is not None and self._typing_in_text_field(event):
            return None
        self.take_sample()
        return "break"

    def _shortcut_toggle_simulation(self, event=None):
        if event is not None and (self._typing_in_text_field(event) or isinstance(event.widget, (tk.Button, ttk.Button))):
            return None
        if self.running:
            self.stop_simulation()
        else:
            self.start_simulation()
        return "break"

    def _update_clock(self):
        if self.root.winfo_exists():
            self.clock_label.configure(text=datetime.now().strftime("%a, %d %b %Y  |  %H:%M:%S"))
            self.root.after(1000, self._update_clock)

    def _on_close(self):
        self.running = False
        self.root.destroy()


def main():
    root = tk.Tk()
    app = ThermalIQApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
