"""Desktop mission builder. Importing this module does not open a window."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import webbrowser
import zipfile
from dataclasses import asdict, replace
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter import font as tkfont

from .airfields import airport_catalogue
from .mapview import MapView
from .model import MissionOptions, aircraft_catalogue, default_output_dir, RECOVERY_LABELS
from .preferences import load_preferences, save_preferences
from .theatres import THEATRES, get_theatre
from .weather import WEATHER_LABELS
from .operations import OPERATION_LABELS, OPERATION_HELP, PACE_LABELS
from . import APP_NAME, RELEASE_TAG, __version__


AUTOMATIC_AIRFIELD = "Automatic (nearest friendly)"
THEME_PALETTES = {
    "dark": {
        "theme": "dark", "bg": "#161c25", "surface": "#202936", "field": "#111923",
        "foreground": "#edf3fa", "muted": "#b0bfd0", "border": "#48566a",
        "accent": "#3987cf", "active": "#344a62", "header": "#101923", "select": "#245d8e",
    },
    "light": {
        "theme": "light", "bg": "#e9edf2", "surface": "#f5f7fa", "field": "#ffffff",
        "foreground": "#243448", "muted": "#5b6b7b", "border": "#9aabbc",
        "accent": "#2367a3", "active": "#dce8f4", "header": "#172b40", "select": "#2367a3",
    },
}


MISSION_LABELS = {
    "facility": "Strike · facility",
    "line": "Strike · fortified line",
    "convoy": "Strike · moving convoy",
    "sead": "SEAD / DEAD",
    "cap": "Combat air patrol",
}
MISSION_HELP = {
    "facility": "Attack a defended installation and its supporting vehicles.",
    "line": "Attack staggered fighting positions with sandbag protection. Choose the units below.",
    "convoy": "Intercept a moving convoy. Its position is available from the mission's F10 menu.",
    "sead": "Destroy enemy air defenses around the selected target area.",
    "cap": "Patrol the target area and engage enemy fighter flights.",
}
FACILITY_LABELS = {
    "random": "Random facility", "fuel": "Fuel depot", "command": "Command center",
    "ammunition": "Ammunition depot", "factory": "Factory", "radar": "Radar station",
}
LINE_UNITS = {
    "mbt": "Tanks",
    "ifv": "IFVs",
    "apc": "APCs",
    "atgm": "ATGM vehicles",
    "infantry": "Infantry",
    "manpads": "MANPADS",
    "aaa": "Anti-aircraft guns",
    "artillery": "Artillery",
}


class Application(tk.Tk):
    """A responsive Tk interface around the same options used by the CLI."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {__version__} · DCS Mission Generator")
        width = min(1240, self.winfo_screenwidth() - 50)
        height = min(820, self.winfo_screenheight() - 80)
        self.geometry(f"{width}x{height}")
        self.minsize(min(960, width), min(640, height))
        self._preferences = load_preferences()
        self._settings_canvases = []
        icon = Path(__file__).parent / "assets" / "ironanvil.ico"
        if sys.platform == "win32" and icon.is_file():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                logging.warning("The application icon could not be loaded")
        self._results: queue.Queue = queue.Queue()
        self._update_results: queue.Queue = queue.Queue()
        self._updating = False
        self._closed = False
        self._busy = False
        self._last_output: Path | None = None
        self._catalogue = [item for item in aircraft_catalogue() if item["missions"]]
        if not self._catalogue:
            raise RuntimeError("The aircraft library could not be loaded. Download a fresh copy of Iron Anvil.")
        self._aircraft_by_label = {
            item["name"].replace("_", " "): item for item in self._catalogue
        }
        self._map_by_label = {theatre.label: key for key, theatre in THEATRES.items()}
        self._mission_by_label = {label: key for key, label in MISSION_LABELS.items()}
        self._weather_by_label = {label: key for key, label in WEATHER_LABELS.items()}
        self._facility_by_label = {label: key for key, label in FACILITY_LABELS.items()}
        self._operation_by_label = {label: key for key, label in OPERATION_LABELS.items()}
        self._pace_by_label = {label: key for key, label in PACE_LABELS.items()}
        self._recovery_by_label = {label: key for key, label in RECOVERY_LABELS.items()}
        self._variables()
        self._restore_settings()
        self._style()
        self._build()
        self._apply_theme()
        self.bind("<Map>", self._theme_titlebar, add="+")
        self._aircraft_changed()
        self._theatre_changed()
        self._poll_timer = self.after(100, self._poll_generation)

    def _variables(self) -> None:
        default_aircraft = next(
            (label for label, item in self._aircraft_by_label.items()
             if item["id"] == "FA_18C_hornet"),
            next(iter(self._aircraft_by_label)),
        )
        first_map = "caucasus" if "caucasus" in THEATRES else next(iter(THEATRES))
        self.theatre_var = tk.StringVar(value=THEATRES[first_map].label)
        self.departure_var = tk.StringVar(value=AUTOMATIC_AIRFIELD)
        self.departure_help_var = tk.StringVar()
        theme = self._preferences.get("theme", "dark")
        self.theme_var = tk.StringVar(value=theme if isinstance(theme, str) and theme in THEME_PALETTES else "dark")
        self.update_status_var = tk.StringVar(value="")
        self.aircraft_var = tk.StringVar(value=default_aircraft)
        self.mission_var = tk.StringVar(value=MISSION_LABELS["facility"])
        self.operation_var = tk.StringVar(value=OPERATION_LABELS["broken_relay"])
        self.operation_help_var = tk.StringVar()
        self.pace_var = tk.StringVar(value=PACE_LABELS["standard"])
        self.response_var = tk.BooleanVar(value=True)
        self.recovery_var = tk.StringVar(value=RECOVERY_LABELS["home"])
        self.withdrawal_var = tk.BooleanVar(value=True)
        self.preset_var = tk.StringVar()
        self.facility_var = tk.StringVar(value=FACILITY_LABELS["random"])
        self.clients_var = tk.StringVar(value="2")
        self.difficulty_var = tk.StringVar(value="normal")
        self.enemy_cap_var = tk.BooleanVar(value=True)
        self.air_defenses_var = tk.BooleanVar(value=True)
        self.start_var = tk.StringVar(value="cold")
        self.time_var = tk.StringVar(value="day")
        self.weather_var = tk.StringVar(value=WEATHER_LABELS["clear"])
        self.loadout_var = tk.StringVar(value="auto")
        self.tanker_var = tk.BooleanVar(value=True)
        self.awacs_var = tk.BooleanVar(value=True)
        self.base_detail_var = tk.BooleanVar(value=True)
        self.opponent_var = tk.StringVar(value="regular")
        self.seed_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value=str(default_output_dir()))
        self.latitude_var = tk.StringVar(value="")
        self.longitude_var = tk.StringVar(value="")
        self.target_var = tk.StringVar(value="Automatic target selection")
        self.status_var = tk.StringVar(value="Ready to create your mission.")
        self.output_status_var = tk.StringVar(value="Choose your map and aircraft, then click Generate mission.")
        self.next_step_var = tk.StringVar(value="Target selection is optional. The other tabs let you customize your flight.")
        self.mission_help_var = tk.StringVar()
        self.opposition_help_var = tk.StringVar()
        self.line_vars = {
            key: tk.BooleanVar(value=key in {"mbt", "ifv", "infantry", "manpads", "aaa"})
            for key in LINE_UNITS
        }

    def _style(self) -> None:
        style = ttk.Style(self)
        self._font_family = tkfont.nametofont("TkDefaultFont").actual("family")
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=(self._font_family, 10))
        style.configure("TNotebook.Tab", padding=(10, 7))
        style.configure("TButton", padding=(9, 5))
        style.configure("Primary.TButton", font=(self._font_family, 11, "bold"), padding=(16, 10))
        style.configure("Help.TLabel", font=(self._font_family, 9))
        style.configure("Status.TLabel", font=(self._font_family, 10, "bold"))
        style.configure("Title.TLabel", font=(self._font_family, 23, "bold"))
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Theme inputs and their popups as well as the surrounding panels."""
        palette = THEME_PALETTES[self.theme_var.get()]
        self.configure(background=palette["bg"])
        style = ttk.Style(self)
        surface, foreground = palette["surface"], palette["foreground"]
        style.configure(".", background=surface, foreground=foreground,
                        bordercolor=palette["border"], lightcolor=surface, darkcolor=surface,
                        troughcolor=palette["field"], selectbackground=palette["select"],
                        selectforeground="#ffffff")
        for name in ("TFrame", "TLabel", "TLabelframe", "TLabelframe.Label", "TCheckbutton", "TRadiobutton"):
            style.configure(name, background=surface, foreground=foreground)
        for name in ("TCheckbutton", "TRadiobutton"):
            style.map(name, background=[("active", surface)],
                      foreground=[("disabled", palette["muted"]), ("active", foreground)],
                      indicatorbackground=[("selected", palette["accent"]), ("!selected", palette["field"])],
                      indicatorforeground=[("selected", "#ffffff")])
        style.configure("Help.TLabel", foreground=palette["muted"])
        style.configure("TNotebook", background=surface, borderwidth=0)
        style.configure("TNotebook.Tab", background=palette["bg"], foreground=palette["muted"])
        style.map("TNotebook.Tab", background=[("selected", surface), ("active", palette["active"])],
                  foreground=[("selected", foreground), ("active", foreground)])
        for name in ("TEntry", "TCombobox", "TSpinbox"):
            style.configure(name, fieldbackground=palette["field"], background=palette["field"],
                            foreground=foreground, insertcolor=foreground, arrowcolor=foreground,
                            selectbackground=palette["select"], selectforeground="#ffffff")
            style.map(name, fieldbackground=[("disabled", palette["bg"]), ("readonly", palette["field"])],
                      foreground=[("disabled", palette["muted"]), ("readonly", foreground)],
                      background=[("active", palette["active"]), ("readonly", palette["field"])],
                      arrowcolor=[("disabled", palette["muted"]), ("!disabled", foreground)])
        style.configure("TButton", background=palette["active"], foreground=foreground)
        style.map("TButton", background=[("active", palette["select"]), ("disabled", surface)],
                  foreground=[("disabled", palette["muted"]), ("active", "#ffffff")])
        style.configure("Primary.TButton", background=palette["accent"], foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", palette["select"]), ("disabled", palette["active"])])
        style.configure("TScrollbar", background=palette["active"], arrowcolor=foreground)
        style.map("TScrollbar", background=[("active", palette["border"])])
        style.configure("TProgressbar", background=palette["accent"])
        style.configure("TSeparator", background=palette["border"])
        style.configure("Header.TFrame", background=palette["header"])
        for name, color in (("Title.TLabel", "#ffffff"), ("Subtitle.TLabel", "#cbd8e5")):
            style.configure(name, background=palette["header"], foreground=color)
        style.configure("Header.TCheckbutton", background=palette["header"], foreground="#edf3fa")
        style.map("Header.TCheckbutton", background=[("active", palette["header"])],
                  foreground=[("active", "#ffffff")])
        for canvas in self._settings_canvases:
            canvas.configure(background=surface)
        for option, value in (("background", palette["field"]), ("foreground", foreground),
                              ("selectBackground", palette["select"]), ("selectForeground", "#ffffff")):
            self.option_add(f"*TCombobox*Listbox.{option}", value)
        def theme_popups(widget):
            if isinstance(widget, ttk.Combobox):
                popup = self.tk.call("ttk::combobox::PopdownWindow", widget)
                self.tk.call(f"{popup}.f.l", "configure", "-background", palette["field"],
                             "-foreground", foreground, "-selectbackground", palette["select"],
                             "-selectforeground", "#ffffff")
            for child in widget.winfo_children():
                theme_popups(child)
        theme_popups(self)
        if hasattr(self, "map_view") and hasattr(self.map_view, "set_theme"):
            self.map_view.set_theme(palette)
        self._theme_titlebar()

    def _theme_titlebar(self, event=None) -> None:
        if sys.platform != "win32" or (event is not None and event.widget is not self):
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            handle = user32.GetParent(self.winfo_id())
            dark = ctypes.c_int(self.theme_var.get() == "dark")
            setter = ctypes.windll.dwmapi.DwmSetWindowAttribute
            setter.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            setter.restype = ctypes.c_long
            if setter(handle, 20, ctypes.byref(dark), ctypes.sizeof(dark)) != 0:
                # Earlier Windows 10 releases use the previous attribute number.
                setter(handle, 19, ctypes.byref(dark), ctypes.sizeof(dark))
        except (AttributeError, OSError, tk.TclError):
            logging.debug("Native title-bar theme is unavailable", exc_info=True)

    def _theme_changed(self) -> None:
        self._apply_theme()
        self._save_settings()

    def _settings_variables(self):
        return {name: getattr(self, f"{name}_var") for name in (
            "theatre", "aircraft", "departure", "mission", "facility", "clients", "difficulty", "enemy_cap",
            "air_defenses", "start", "time", "weather", "loadout", "tanker", "awacs",
            "base_detail", "opponent", "seed", "output", "operation", "pace", "response", "recovery", "withdrawal")}

    def _restore_settings(self) -> None:
        settings = self._preferences.get("mission", {})
        if not isinstance(settings, dict):
            return
        allowed = {
            "theatre": self._map_by_label, "aircraft": self._aircraft_by_label,
            "mission": self._mission_by_label, "clients": ("1", "2", "3", "4"),
            "facility": self._facility_by_label,
            "difficulty": ("easy", "normal", "hard", "extreme"),
            "start": ("cold", "hot", "runway", "air"), "time": ("day", "dawn", "dusk", "night", "random"),
            "weather": self._weather_by_label, "loadout": ("auto", "default"),
            "opponent": ("regular", "insurgents"),
            "operation": self._operation_by_label, "pace": self._pace_by_label,
            "recovery": self._recovery_by_label,
        }
        for name, variable in self._settings_variables().items():
            value = settings.get(name)
            if isinstance(variable, tk.BooleanVar):
                if isinstance(value, bool):
                    variable.set(value)
            elif isinstance(value, str) and (name not in allowed or value in allowed[name]):
                variable.set(value)
        units = settings.get("line_units")
        if isinstance(units, list) and all(isinstance(key, str) for key in units):
            for key, variable in self.line_vars.items():
                variable.set(key in units)

    def _save_settings(self) -> None:
        settings = {name: variable.get() for name, variable in self._settings_variables().items()}
        settings["line_units"] = [key for key, variable in self.line_vars.items() if variable.get()]
        # Re-read to preserve settings saved by other features, including the updater.
        preferences = load_preferences()
        preferences.update(theme=self.theme_var.get(), mission=settings)
        try:
            save_preferences(preferences)
        except (OSError, ValueError):
            logging.exception("Iron Anvil could not save preferences")

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self, style="Header.TFrame", padding=(22, 14))
        header.grid(row=0, column=0, sticky="ew")
        title = ttk.Frame(header, style="Header.TFrame")
        title.pack(side="left", fill="x", expand=True)
        ttk.Label(title, text="IRON ANVIL · EXPERIMENTAL", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title, text="Shared objectives. Same squadron. New choices.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))
        tools = ttk.Frame(header, style="Header.TFrame")
        tools.pack(side="right", padx=(12, 0))
        ttk.Checkbutton(tools, text="Dark mode", variable=self.theme_var, onvalue="dark", offvalue="light",
                        style="Header.TCheckbutton", command=self._theme_changed).grid(row=0, column=0, padx=(0, 12))
        self.update_button = ttk.Button(tools, text="Experimental downloads", command=lambda: webbrowser.open(
            f"https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/{RELEASE_TAG}"))
        self.update_button.grid(row=0, column=1)
        ttk.Label(tools, textvariable=self.update_status_var, style="Subtitle.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="e", pady=(4, 0))

        body = ttk.Frame(self, padding=12)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, minsize=370)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(body, padding=(0, 0, 12, 0))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(0, weight=1)
        notebook = ttk.Notebook(sidebar)
        notebook.grid(row=0, column=0, sticky="nsew")
        flight = self._settings_tab(notebook, "Flight")
        mission = self._settings_tab(notebook, "Mission")
        conditions = self._settings_tab(notebook, "Conditions")
        self._flight_tab(flight)
        self._mission_tab(mission)
        self._conditions_tab(conditions)

        opposition = ttk.LabelFrame(sidebar, text="Enemy forces · all mission types", padding=10)
        opposition.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Checkbutton(opposition, text="Enemy fighter patrols (CAP)", variable=self.enemy_cap_var,
                        command=self._opposition_changed).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opposition, text="Enemy air defenses", variable=self.air_defenses_var,
                        command=self._opposition_changed).grid(row=1, column=0, sticky="w")
        ttk.Label(opposition, textvariable=self.opposition_help_var, style="Help.TLabel",
                  wraplength=320).grid(row=2, column=0, sticky="w", pady=(5, 0))

        planner = ttk.Frame(body)
        planner.grid(row=0, column=1, sticky="nsew")
        planner.columnconfigure(0, weight=1)
        planner.rowconfigure(1, weight=1)
        ttk.Label(planner, text="Target planner", font=(self._font_family, 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        self.map_view = MapView(planner, on_select=self._map_selected)
        self.map_view.grid(row=1, column=0, sticky="nsew")
        target = ttk.Frame(planner, padding=(0, 9, 0, 0))
        target.grid(row=2, column=0, sticky="ew")
        ttk.Label(target, text="Latitude").grid(row=0, column=0, sticky="w")
        ttk.Entry(target, width=12, textvariable=self.latitude_var).grid(
            row=0, column=1, sticky="w", padx=(5, 12))
        ttk.Label(target, text="Longitude").grid(row=0, column=2, sticky="w")
        ttk.Entry(target, width=12, textvariable=self.longitude_var).grid(
            row=0, column=3, sticky="w", padx=(5, 12))
        ttk.Button(target, text="Set target", command=self._apply_coordinates).grid(
            row=0, column=4, padx=(0, 5))
        ttk.Button(target, text="Clear", command=self._clear_target).grid(row=0, column=5)
        ttk.Label(target, textvariable=self.target_var, style="Help.TLabel").grid(
            row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))
        ttk.Label(target, text="Click to choose a target · right-click to clear · zoom to place it accurately",
                  style="Help.TLabel").grid(row=2, column=0, columnspan=6, sticky="w", pady=(3, 0))

        footer = ttk.Frame(self, padding=(18, 12))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Label(footer, textvariable=self.output_status_var, style="Help.TLabel",
                  wraplength=600).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(footer, textvariable=self.next_step_var, style="Help.TLabel",
                  wraplength=600).grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=180)
        self.progress.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.open_button = ttk.Button(footer, text="Open mission folder", command=self._open_output)
        self.open_button.grid(row=0, column=1, rowspan=2, padx=(10, 8))
        self.generate_button = ttk.Button(footer, text="Generate mission", style="Primary.TButton",
                                         command=self._generate)
        self.generate_button.grid(row=0, column=2, rowspan=2)
        ttk.Button(footer, text="Mission briefing", command=self._open_briefing).grid(row=2, column=1, padx=(10, 8))
        ttk.Button(footer, text="Repeat last mission", command=self._repeat_last).grid(row=2, column=2)

    def _settings_tab(self, notebook, label):
        """Keep every setting reachable on small screens and at larger DPI."""
        container = ttk.Frame(notebook)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        canvas = tk.Canvas(container, background=THEME_PALETTES[self.theme_var.get()]["surface"], highlightthickness=0,
                           width=340, height=430)
        self._settings_canvases.append(canvas)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        content = ttk.Frame(canvas, padding=12)
        window = canvas.create_window((0, 0), window=content, anchor="nw")

        def resized(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            if content.winfo_reqheight() > canvas.winfo_height():
                scrollbar.grid()
            else:
                scrollbar.grid_remove()

        def viewport_changed(event):
            canvas.itemconfigure(window, width=event.width)
            resized()

        def scroll(event):
            if content.winfo_reqheight() <= canvas.winfo_height():
                return None
            direction = -1 if getattr(event, "num", None) == 4 or event.delta > 0 else 1
            canvas.yview_scroll(direction, "units")
            return "break"

        def bind_scrolling(widget):
            widget.bind("<MouseWheel>", scroll, add="+")
            widget.bind("<Button-4>", scroll, add="+")
            widget.bind("<Button-5>", scroll, add="+")
            for child in widget.winfo_children():
                bind_scrolling(child)

        content.bind("<Configure>", resized)
        canvas.bind("<Configure>", viewport_changed)
        self.after_idle(lambda: bind_scrolling(content))
        notebook.add(container, text=label)
        return content

    @staticmethod
    def _combo(parent, row, label, variable, values, width=34):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(8 if row else 0, 3))
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=width)
        combo.grid(row=row + 1, column=0, sticky="ew")
        return combo

    def _flight_tab(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        map_combo = self._combo(parent, 0, "DCS map", self.theatre_var, list(self._map_by_label))
        map_combo.bind("<<ComboboxSelected>>", self._theatre_changed)
        aircraft_combo = self._combo(parent, 2, "Your aircraft", self.aircraft_var,
                                     list(self._aircraft_by_label))
        aircraft_combo.bind("<<ComboboxSelected>>", self._aircraft_changed)
        self.departure_combo = self._combo(parent, 4, "Departure airfield · type to search", self.departure_var,
                                           [AUTOMATIC_AIRFIELD])
        self.departure_combo.configure(state="normal")
        self.departure_combo.bind("<KeyRelease>", self._filter_departures)
        self.departure_combo.bind("<<ComboboxSelected>>", self._departure_changed)
        self.departure_combo.bind("<FocusOut>", self._departure_changed)
        ttk.Label(parent, textvariable=self.departure_help_var, style="Help.TLabel", wraplength=315).grid(
            row=6, column=0, sticky="w", pady=(7, 0))
        flight_row = ttk.Frame(parent)
        flight_row.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        flight_row.columnconfigure(0, weight=1)
        flight_row.columnconfigure(1, weight=1)
        clients_frame = ttk.Frame(flight_row, padding=(0, 0, 6, 0))
        clients_frame.grid(row=0, column=0, sticky="ew")
        clients_frame.columnconfigure(0, weight=1)
        loadout_frame = ttk.Frame(flight_row, padding=(6, 0, 0, 0))
        loadout_frame.grid(row=0, column=1, sticky="ew")
        loadout_frame.columnconfigure(0, weight=1)
        self._combo(clients_frame, 0, "Number of pilots", self.clients_var, ["1", "2", "3", "4"], width=15)
        self._combo(loadout_frame, 0, "Loadout", self.loadout_var, ["auto", "default"], width=15)
        ttk.Label(parent, text="Auto builds a role-appropriate starting payload. You can adjust it in DCS.",
                  style="Help.TLabel", wraplength=315).grid(row=8, column=0, sticky="w", pady=(7, 10))
        ttk.Checkbutton(parent, text="Tanker support, where compatible", variable=self.tanker_var).grid(
            row=9, column=0, sticky="w", pady=3)
        ttk.Checkbutton(parent, text="AWACS support", variable=self.awacs_var).grid(
            row=10, column=0, sticky="w", pady=3)
        ttk.Checkbutton(parent, text="Airbase detail", variable=self.base_detail_var).grid(
            row=11, column=0, sticky="w", pady=3)
        ttk.Separator(parent).grid(row=12, column=0, sticky="ew", pady=9)
        ttk.Label(parent, text="Your airbase is friendly, with fuel and weapons available for rearming and refueling.",
                  style="Help.TLabel", wraplength=315).grid(row=13, column=0, sticky="w")
        presets = ttk.LabelFrame(parent, text="Squadron presets", padding=8)
        presets.grid(row=14, column=0, sticky="ew", pady=(12, 0))
        presets.columnconfigure(0, weight=1)
        self.preset_combo = ttk.Combobox(presets, textvariable=self.preset_var, state="readonly",
            values=sorted(self._preferences.get("presets", {})) if isinstance(self._preferences.get("presets"), dict) else [])
        self.preset_combo.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(presets, text="Save preset", command=self._save_preset).grid(row=1, column=0, sticky="ew", pady=5)
        ttk.Button(presets, text="Load preset", command=self._load_preset).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(presets, text="Import mission / settings", command=self._import_recipe).grid(row=2, column=0, sticky="ew")
        ttk.Button(presets, text="Export settings", command=self._export_recipe).grid(row=2, column=1, sticky="ew")
        self.recovery_combo = self._combo(parent, 15, "Approved recovery bases", self.recovery_var, list(RECOVERY_LABELS.values()))
        ttk.Checkbutton(parent, text="Allow team withdrawal with partial debrief", variable=self.withdrawal_var).grid(
            row=17, column=0, sticky="w", pady=8)
        ttk.Label(parent, text="An alternate is selected from friendly compatible bases. Withdrawal uses a proposal and confirmation in the F10 menu.",
            style="Help.TLabel", wraplength=315).grid(row=18, column=0, sticky="w")

    def _mission_tab(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        operation = ttk.LabelFrame(parent, text="Cooperative operation", padding=8)
        operation.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        operation.columnconfigure(0, weight=1)
        self.operation_combo = self._combo(operation, 0, "Mission style", self.operation_var, list(OPERATION_LABELS.values()))
        self.operation_combo.bind("<<ComboboxSelected>>", self._operation_changed)
        ttk.Label(operation, textvariable=self.operation_help_var, style="Help.TLabel", wraplength=295).grid(
            row=2, column=0, sticky="w", pady=(8, 2))
        self.response_check = ttk.Checkbutton(operation, text="One staged enemy ground response", variable=self.response_var)
        self.response_check.grid(row=3, column=0, sticky="w", pady=5)
        self._combo(operation, 4, "Automatic target distance", self.pace_var, list(PACE_LABELS.values()))
        ttk.Label(operation, text="A target you pin on the map always takes priority.", style="Help.TLabel", wraplength=295).grid(
            row=6, column=0, sticky="w", pady=5)
        settings = ttk.Frame(parent)
        settings.grid(row=1, column=0, sticky="ew")
        parent = settings
        parent.columnconfigure(0, weight=1)
        self.mission_combo = self._combo(parent, 0, "Mission", self.mission_var, list(MISSION_LABELS.values()))
        self.mission_combo.bind("<<ComboboxSelected>>", self._mission_changed)
        ttk.Label(parent, textvariable=self.mission_help_var, style="Help.TLabel", wraplength=315).grid(
            row=2, column=0, sticky="w", pady=(8, 2))
        self.facility_combo = self._combo(parent, 3, "Facility type", self.facility_var, list(FACILITY_LABELS.values()))
        opposition_row = ttk.Frame(parent)
        opposition_row.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        opposition_row.columnconfigure(0, weight=1)
        opposition_row.columnconfigure(1, weight=1)
        difficulty_frame = ttk.Frame(opposition_row, padding=(0, 0, 6, 0))
        difficulty_frame.grid(row=0, column=0, sticky="ew")
        difficulty_frame.columnconfigure(0, weight=1)
        opponent_frame = ttk.Frame(opposition_row, padding=(6, 0, 0, 0))
        opponent_frame.grid(row=0, column=1, sticky="ew")
        opponent_frame.columnconfigure(0, weight=1)
        self._combo(difficulty_frame, 0, "Difficulty", self.difficulty_var,
                    ["easy", "normal", "hard", "extreme"], width=15)
        self.opponent_combo = self._combo(opponent_frame, 0, "Syria opponent", self.opponent_var,
                                          ["regular", "insurgents"], width=15)
        self.line_frame = ttk.LabelFrame(parent, text="Fortified-line units", padding=8)
        self.line_frame.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        self._line_buttons = []
        for index, (key, label) in enumerate(LINE_UNITS.items()):
            check = ttk.Checkbutton(self.line_frame, text=label, variable=self.line_vars[key])
            check.grid(row=index // 2, column=index % 2, sticky="w", pady=2, padx=(0, 10))
            self._line_buttons.append(check)

    def _conditions_tab(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        self._combo(parent, 0, "Start type", self.start_var, ["cold", "hot", "runway", "air"])
        conditions_row = ttk.Frame(parent)
        conditions_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        conditions_row.columnconfigure(0, weight=1)
        conditions_row.columnconfigure(1, weight=1)
        time_frame = ttk.Frame(conditions_row, padding=(0, 0, 6, 0))
        time_frame.grid(row=0, column=0, sticky="ew")
        time_frame.columnconfigure(0, weight=1)
        weather_frame = ttk.Frame(conditions_row, padding=(6, 0, 0, 0))
        weather_frame.grid(row=0, column=1, sticky="ew")
        weather_frame.columnconfigure(0, weight=1)
        self._combo(time_frame, 0, "Time of day", self.time_var,
                    ["day", "dawn", "dusk", "night", "random"], width=15)
        self.weather_combo = self._combo(weather_frame, 0, "Weather", self.weather_var,
                                         [label for key, label in WEATHER_LABELS.items() if key != "cloudy"], width=19)
        ttk.Label(parent, text="Mission variation number (optional)").grid(row=3, column=0, sticky="w", pady=(10, 3))
        seed_row = ttk.Frame(parent)
        seed_row.grid(row=4, column=0, sticky="ew")
        seed_row.columnconfigure(0, weight=1)
        ttk.Entry(seed_row, textvariable=self.seed_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(seed_row, text="New", command=lambda: self.seed_var.set(str(secrets.randbelow(2**31)))).grid(
            row=0, column=1, padx=(6, 0))
        ttk.Label(parent, text="Leave blank for a fresh mission each time. Reuse a number to repeat a layout.",
                  style="Help.TLabel", wraplength=315).grid(row=5, column=0, sticky="w", pady=(6, 10))
        ttk.Label(parent, text="Mission output folder").grid(row=6, column=0, sticky="w", pady=(4, 3))
        ttk.Entry(parent, textvariable=self.output_var).grid(row=7, column=0, sticky="ew")
        ttk.Button(parent, text="Choose folder...", command=self._choose_output).grid(
            row=8, column=0, sticky="w", pady=(6, 0))
        ttk.Label(parent, text="On Windows, missions are saved in your DCS Saved Games folder automatically. Use Choose folder if you use a custom DCS profile.",
                  style="Help.TLabel", wraplength=315).grid(row=9, column=0, sticky="w", pady=(15, 0))

    def _theatre_changed(self, _event=None) -> None:
        key = self._map_by_label[self.theatre_var.get()]
        self._departures = airport_catalogue(key)
        self._departure_by_name = {airport["name"]: airport for airport in self._departures}
        self._departure_names = [AUTOMATIC_AIRFIELD, *self._departure_by_name]
        self.departure_combo.configure(values=self._departure_names)
        if self.departure_var.get() not in self._departure_names:
            self.departure_var.set(AUTOMATIC_AIRFIELD)
        self.map_view.set_theatre(get_theatre(key))
        self._departure_changed()
        self._clear_target()
        self.opponent_combo.configure(state="readonly" if key == "syria" else "disabled")
        if key != "syria":
            self.opponent_var.set("regular")

    def _filter_departures(self, event=None) -> None:
        if event is not None and event.keysym in {"Up", "Down", "Return", "Escape", "Tab"}:
            return
        search = self.departure_var.get().strip().casefold()
        names = self._departure_names
        if search and search != AUTOMATIC_AIRFIELD.casefold():
            names = [name for name in names if search in name.casefold()]
        self.departure_combo.configure(values=names)

    def _departure_changed(self, _event=None) -> None:
        if not hasattr(self, "_departure_by_name"):
            return
        name = self.departure_var.get()
        airport = self._departure_by_name.get(name)
        if hasattr(self.map_view, "set_home_airport"):
            self.map_view.set_home_airport(name if airport else None)
        if airport:
            runway = "Runway" if airport.get("runways") else "Helipad / no runway"
            parking = airport.get("parking", 0)
            self.departure_help_var.set(f"{runway} · {parking} parking spots. This airfield becomes friendly, with fuel and weapons.")
        else:
            self.departure_help_var.set(f"All {len(self._departures)} airfields are listed, including helipads. Choose a runway for fixed-wing aircraft. Automatic picks a suitable friendly base.")

    def _aircraft_changed(self, _event=None) -> None:
        item = self._aircraft_by_label[self.aircraft_var.get()]
        allowed = [key for key in MISSION_LABELS if key in item["missions"]]
        if not allowed:
            raise ValueError("This aircraft has no supported mission roles.")
        labels = [MISSION_LABELS[key] for key in allowed]
        self.mission_combo.configure(values=labels)
        if self.mission_var.get() not in labels:
            self.mission_var.set(labels[0])
        self._mission_changed()
        if hasattr(self, "_departure_by_name"):
            self._departure_changed()

    def _mission_changed(self, _event=None) -> None:
        mission = self._mission_by_label[self.mission_var.get()]
        if mission != "facility":
            self.operation_var.set(OPERATION_LABELS["classic"])
        operation = self._operation_by_label[self.operation_var.get()]
        self.operation_help_var.set(OPERATION_HELP[operation])
        self.response_check.configure(state="normal" if operation != "classic" else "disabled")
        self.mission_help_var.set(MISSION_HELP[mission])
        self.facility_combo.configure(state="readonly" if mission == "facility" and operation == "classic" else "disabled")
        for check in self._line_buttons:
            check.configure(state="normal" if mission == "line" else "disabled")
        self._opposition_changed()

    def _operation_changed(self, _event=None):
        if self._operation_by_label[self.operation_var.get()] != "classic":
            aircraft = self._aircraft_by_label[self.aircraft_var.get()]
            if "facility" not in aircraft["missions"]:
                self.operation_var.set(OPERATION_LABELS["classic"])
                messagebox.showinfo("Choose a ground-attack aircraft", "This operation needs an aircraft that can attack ground targets.", parent=self)
            else:
                self.mission_var.set(MISSION_LABELS["facility"])
        self._mission_changed()

    def _opposition_changed(self) -> None:
        mission = self._mission_by_label[self.mission_var.get()]
        if mission == "sead" and not self.air_defenses_var.get():
            text = "Air defenses are off: this SEAD mission has no SAM, AAA or MANPADS targets."
        elif mission == "cap" and not self.enemy_cap_var.get():
            text = "Enemy CAP is off: this is an unopposed patrol."
        elif not self.air_defenses_var.get():
            text = "Air defenses are off, including AAA and MANPADS selected for a fortified line."
        else:
            text = "Both switches apply to every mission, including CAP and SEAD."
        self.opposition_help_var.set(text)

    def _map_selected(self, lat, lon) -> None:
        if lat is None or lon is None:
            self._clear_target()
            return
        self.latitude_var.set(f"{lat:.6f}")
        self.longitude_var.set(f"{lon:.6f}")
        self.target_var.set(f"Pinned target: {lat:.5f}°, {lon:.5f}°")
        self.map_view.set_target(lat, lon)

    def _clear_target(self) -> None:
        self.latitude_var.set("")
        self.longitude_var.set("")
        self.target_var.set("Automatic target selection")
        self.map_view.set_target(None, None)

    def _coordinates(self):
        lat_text = self.latitude_var.get().strip()
        lon_text = self.longitude_var.get().strip()
        if not lat_text and not lon_text:
            return None, None
        if not lat_text or not lon_text:
            raise ValueError("Enter both latitude and longitude, or clear both for an automatic target.")
        try:
            lat, lon = float(lat_text), float(lon_text)
        except ValueError:
            raise ValueError("Latitude and longitude must be decimal numbers.") from None
        theatre = get_theatre(self._map_by_label[self.theatre_var.get()])
        west, south, east, north = theatre.bounds
        if not south <= lat <= north or not west <= lon <= east:
            raise ValueError(f"Choose a point within {theatre.label}: latitude {south:g} to {north:g}, "
                             f"longitude {west:g} to {east:g}.")
        return lat, lon

    def _apply_coordinates(self) -> None:
        try:
            lat, lon = self._coordinates()
        except ValueError as exc:
            messagebox.showerror("Target coordinates", str(exc), parent=self)
            return
        self._map_selected(lat, lon)

    def collect_options(self) -> MissionOptions:
        """Read and validate UI state on the Tk thread before starting a worker."""
        lat, lon = self._coordinates()
        seed_text = self.seed_var.get().strip()
        try:
            seed = int(seed_text) if seed_text else secrets.randbelow(2**31)
        except ValueError:
            raise ValueError("Seed must be a whole number, or blank for a new seed.") from None
        if not 0 <= seed < 2**31:
            raise ValueError("Seed must be between 0 and 2147483647.")
        output_text = self.output_var.get().strip()
        if not output_text:
            raise ValueError("Choose a mission output folder.")
        output = Path(output_text).expanduser()
        if output.exists() and not output.is_dir():
            raise ValueError("The mission output path is a file. Choose a folder instead.")
        mission = self._mission_by_label[self.mission_var.get()]
        units = tuple(key for key, variable in self.line_vars.items() if variable.get())
        if mission == "line" and not units:
            raise ValueError("Select at least one unit type for the fortified line.")
        departure = self.departure_var.get().strip()
        if departure == AUTOMATIC_AIRFIELD:
            departure = None
        else:
            departure = next((name for name in self._departure_by_name
                              if name.casefold() == departure.casefold()), None)
            if departure is None:
                raise ValueError("Choose a departure airfield from the list, or select Automatic (nearest friendly).")
        return MissionOptions(
            map=self._map_by_label[self.theatre_var.get()],
            aircraft=self._aircraft_by_label[self.aircraft_var.get()]["id"],
            mission=mission,
            facility_type=self._facility_by_label.get(self.facility_var.get(), self.facility_var.get()),
            operation=self._operation_by_label[self.operation_var.get()] if mission == "facility" else "classic",
            pace=self._pace_by_label[self.pace_var.get()],
            enemy_response=self.response_var.get(),
            recovery=self._recovery_by_label[self.recovery_var.get()],
            allow_withdrawal=self.withdrawal_var.get(),
            clients=int(self.clients_var.get()),
            difficulty=self.difficulty_var.get(),
            enemy_cap=self.enemy_cap_var.get(),
            air_defenses=self.air_defenses_var.get(),
            target_lat=lat,
            target_lon=lon,
            seed=seed,
            start=self.start_var.get(),
            time_of_day=self.time_var.get(),
            weather=self._weather_by_label.get(self.weather_var.get(), self.weather_var.get()),
            departure_airport=departure,
            tanker=self.tanker_var.get(),
            awacs=self.awacs_var.get(),
            loadout=self.loadout_var.get(),
            line_units=units,
            base_detail=self.base_detail_var.get(),
            output_dir=str(output),
            opponent=self.opponent_var.get(),
        ).validate()

    def _generate(self) -> None:
        if self._busy or self._updating:
            return
        try:
            options = self.collect_options()
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Check mission settings", str(exc), parent=self)
            return
        self._save_settings()
        self._busy = True
        self.generate_button.configure(state="disabled")
        self.progress.start(14)
        self.status_var.set("Creating your mission...")
        self.output_status_var.set("Preparing your aircraft, targets and support flights. This may take a few seconds.")
        self.next_step_var.set("")
        # The worker owns only plain data. Closing the window must not leave a
        # worker holding the last reference to a Tk interpreter or its widgets.
        threading.Thread(target=self._generate_worker, args=(options, self._results), daemon=True).start()

    @staticmethod
    def _generate_worker(options, results) -> None:
        try:
            from .generator import generate

            path = generate(options)
            results.put((True, Path(path)))
        except Exception as exc:
            logging.exception("Iron Anvil mission generation failed")
            if isinstance(exc, PermissionError):
                message = ("Iron Anvil couldn't save in the selected folder. "
                           "Choose another mission folder in Conditions, then try again.")
            elif isinstance(exc, OSError):
                message = ("Iron Anvil couldn't read or write a required file. "
                           "Check that your mission folder is available, then try again.")
            elif isinstance(exc, ValueError):
                message = str(exc)
            else:
                message = "Try creating the mission again. If this keeps happening, share the log file below when asking for help."
            results.put((False, message))

    def _check_updates(self) -> None:
        if self._updating:
            return
        if self._busy:
            messagebox.showinfo("Finish creating your mission", "Check for updates after your mission is ready.", parent=self)
            return
        self._updating = True
        self.update_button.configure(state="disabled")
        self.generate_button.configure(state="disabled")
        self.update_status_var.set("Checking for updates...")
        threading.Thread(target=self._check_update_worker, args=(self._update_results,), daemon=True).start()

    @staticmethod
    def _check_update_worker(results) -> None:
        try:
            from .updater import check_for_update

            results.put(("checked", check_for_update()))
        except Exception as exc:
            logging.exception("Iron Anvil update check failed")
            results.put(("update-error", str(exc)))

    @staticmethod
    def _download_update_worker(info, results) -> None:
        try:
            from .updater import download_update

            def progress(received, total):
                results.put(("update-progress", (received, total)))

            path = download_update(info, progress_callback=progress)
            results.put(("downloaded", (path, info)))
        except Exception as exc:
            logging.exception("Iron Anvil update download failed")
            results.put(("update-error", str(exc)))

    def _poll_updates(self) -> None:
        while True:
            try:
                event, result = self._update_results.get_nowait()
            except queue.Empty:
                return
            if event == "update-progress":
                received, total = result
                text = f"{received / total:.0%}" if total else f"{received / 1048576:.1f} MB"
                self.update_status_var.set(f"Downloading update... {text}")
            elif event == "checked":
                if result is None:
                    self._finish_update("You're up to date.")
                    messagebox.showinfo("Iron Anvil is up to date", "You already have the latest version of Iron Anvil.", parent=self)
                    continue
                if sys.platform != "win32":
                    self._finish_update(f"Version {result.version} is available.")
                    messagebox.showinfo("Windows update available", f"Iron Anvil {result.version} is available for Windows.\n\n{result.release_url}", parent=self)
                    continue
                install = messagebox.askyesno("Iron Anvil update available",
                    f"Download and install Iron Anvil {result.version}?\n\n"
                    "This updates your current installation. Your saved missions and settings stay in place. "
                    "Iron Anvil will close when the installer is ready.", parent=self)
                if not install:
                    self._finish_update(f"Version {result.version} is available.")
                    continue
                self.generate_button.configure(state="disabled")
                self.update_status_var.set("Downloading update...")
                threading.Thread(target=self._download_update_worker,
                                 args=(result, self._update_results), daemon=True).start()
            elif event == "downloaded":
                path, info = result
                try:
                    from .updater import launch_update

                    self._save_settings()
                    launch_update(path, expected_sha256=info.sha256)
                except Exception as exc:
                    logging.exception("Iron Anvil could not start its update")
                    self._finish_update("Update could not start.")
                    messagebox.showerror("Update could not start", str(exc), parent=self)
                else:
                    self.destroy()
                    return
            elif event == "update-error":
                self._finish_update("Update unavailable. Try again later.")
                messagebox.showerror("Could not update Iron Anvil",
                                     f"{result}\n\nYou can keep using your current version.", parent=self)

    def _finish_update(self, text) -> None:
        self._updating = False
        self.update_button.configure(state="normal")
        if not self._busy:
            self.generate_button.configure(state="normal")
        self.update_status_var.set(text)

    def _poll_generation(self) -> None:
        self._poll_updates()
        if self._closed:
            return
        try:
            success, result = self._results.get_nowait()
        except queue.Empty:
            pass
        else:
            self._busy = False
            self.progress.stop()
            self.generate_button.configure(state="normal")
            if success:
                self._last_output = result
                self.status_var.set(f"Mission ready: {result.name}")
                self.output_status_var.set(str(result))
                self.next_step_var.set("In DCS: Mission > My Missions to fly solo, or Multiplayer > New server to host for friends. Add the saved mission.")
            else:
                from .diagnostics import log_path

                self.status_var.set("Mission could not be generated")
                self.output_status_var.set("Review the error, adjust the settings and try again.")
                self.next_step_var.set(f"Help log: {log_path()}")
                messagebox.showerror("Mission generation failed",
                                     f"{result}\n\nDetails were saved to:\n{log_path()}", parent=self)
        self._poll_timer = self.after(100, self._poll_generation)

    def destroy(self) -> None:
        if getattr(self, "_closed", False):
            return
        if hasattr(self, "line_vars"):
            self._save_settings()
        self._closed = True
        if getattr(self, "_poll_timer", None):
            self.after_cancel(self._poll_timer)
            self._poll_timer = None
        super().destroy()

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="Mission output folder",
                                         initialdir=self.output_var.get(), mustexist=False)
        if folder:
            self.output_var.set(folder)
            self._save_settings()

    def _apply_options(self, options):
        """Import plain validated settings while retaining this computer's output folder."""
        options.validate()
        output = self.output_var.get()
        self.operation_var.set(OPERATION_LABELS["classic"])
        self.theatre_var.set(THEATRES[options.map].label)
        self._theatre_changed()
        self.aircraft_var.set(next(label for label, item in self._aircraft_by_label.items()
                                   if item["id"] == options.aircraft or item["name"] == options.aircraft))
        self._aircraft_changed()
        self.mission_var.set(MISSION_LABELS[options.mission])
        self.operation_var.set(OPERATION_LABELS[options.operation])
        self.facility_var.set(FACILITY_LABELS[options.facility_type])
        self.pace_var.set(PACE_LABELS[options.pace])
        self.response_var.set(options.enemy_response)
        self.recovery_var.set(RECOVERY_LABELS[options.recovery])
        self.withdrawal_var.set(options.allow_withdrawal)
        for name, value in {"clients": str(options.clients), "difficulty": options.difficulty,
                "enemy_cap": options.enemy_cap, "air_defenses": options.air_defenses, "start": options.start,
                "time": options.time_of_day, "weather": WEATHER_LABELS[options.weather], "loadout": options.loadout,
                "tanker": options.tanker, "awacs": options.awacs, "base_detail": options.base_detail,
                "opponent": options.opponent, "seed": str(options.seed)}.items():
            getattr(self, f"{name}_var").set(value)
        for name, variable in self.line_vars.items():
            variable.set(name in options.line_units)
        if options.departure_airport:
            from .airfields import resolve_airport
            self.departure_var.set(resolve_airport(get_theatre(options.map).terrain(), options.departure_airport).name)
        else:
            self.departure_var.set(AUTOMATIC_AIRFIELD)
        self._departure_changed()
        if options.target_lat is not None:
            self._map_selected(options.target_lat, options.target_lon)
        else:
            self._clear_target()
        self.output_var.set(output)
        self._mission_changed()
        self._save_settings()

    def _save_preset(self):
        try:
            options = self.collect_options()
            name = simpledialog.askstring("Save squadron preset", "Name this setup:", parent=self)
            if not name or not name.strip():
                return
            name = name.strip()
            if len(name) > 60:
                raise ValueError("Use a preset name with 60 characters or fewer")
            preferences = load_preferences()
            presets = preferences.get("presets", {})
            if not isinstance(presets, dict):
                presets = {}
            presets[name] = {"options": asdict(replace(options, output_dir=None))}
            save_preferences({"presets": presets})
            self.preset_combo.configure(values=sorted(presets))
            self.preset_var.set(name)
            self.status_var.set(f"Squadron preset saved: {name}")
        except (ValueError, OSError) as error:
            messagebox.showerror("Save preset", str(error), parent=self)

    def _load_preset(self):
        from .recipes import options_from_data
        try:
            presets = load_preferences().get("presets", {})
            if not isinstance(presets, dict) or self.preset_var.get() not in presets:
                raise ValueError("Choose a saved squadron preset first")
            self._apply_options(options_from_data(presets[self.preset_var.get()]))
            self.status_var.set(f"Preset loaded: {self.preset_var.get()}. Change the variation number for a fresh layout.")
        except (ValueError, OSError) as error:
            messagebox.showerror("Load preset", str(error), parent=self)

    def _import_recipe(self):
        path = filedialog.askopenfilename(parent=self, title="Load settings from a mission or recipe",
                filetypes=[("Iron Anvil missions and settings", "*.miz *.json"), ("All files", "*.*")])
        if path:
            self._load_recipe(path)

    def _load_recipe(self, path):
        from .recipes import read_recipe
        try:
            self._apply_options(read_recipe(path))
            self.status_var.set(f"Mission settings loaded from {Path(path).name}. Your output folder is unchanged.")
        except (ValueError, OSError) as error:
            messagebox.showerror("Load mission settings", str(error), parent=self)

    def _export_recipe(self):
        from .recipes import write_recipe
        try:
            options = self.collect_options()
            path = filedialog.asksaveasfilename(parent=self, title="Share mission settings", defaultextension=".json",
                        filetypes=[("Iron Anvil settings", "*.json")], initialfile="My squadron mission.json")
            if path:
                write_recipe(options, path)
                self.status_var.set("Mission settings exported. Your output folder was excluded for easy sharing.")
        except (ValueError, OSError) as error:
            messagebox.showerror("Export mission settings", str(error), parent=self)

    def _repeat_last(self):
        if self._last_output:
            self._load_recipe(self._last_output)
        else:
            messagebox.showinfo("Repeat a mission", "Generate a mission first, or use Import mission / settings in the Flight tab.", parent=self)

    def _open_briefing(self):
        if not self._last_output:
            messagebox.showinfo("Mission briefing", "Generate a mission first. Its briefing and kneeboard will be included automatically.", parent=self)
            return
        try:
            from .diagnostics import log_path
            with zipfile.ZipFile(self._last_output) as archive:
                info = archive.getinfo("ironanvil-briefing.html")
                if info.file_size > 8 * 1024 * 1024:
                    raise ValueError("The mission briefing is unexpectedly large")
                document = archive.read(info)
            directory = log_path().parent.parent / "briefings"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / (self._last_output.stem + ".html")
            path.write_bytes(document)
            webbrowser.open(path.resolve().as_uri())
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
            messagebox.showerror("Mission briefing", str(error), parent=self)

    def _open_output(self) -> None:
        folder = self._last_output.parent if self._last_output else Path(self.output_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            messagebox.showerror("Open mission folder", f"{folder}\n\n{exc}", parent=self)


def run() -> None:
    from .diagnostics import configure_logging

    configure_logging()
    Application().mainloop()
