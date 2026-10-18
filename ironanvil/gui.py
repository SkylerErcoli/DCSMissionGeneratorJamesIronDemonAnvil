"""Desktop mission builder. Importing this module does not open a window."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from .mapview import MapView
from .model import MissionOptions, aircraft_catalogue, default_output_dir
from .theatres import THEATRES, get_theatre


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
        self.title("Iron Anvil · DCS Mission Generator")
        width = min(1240, self.winfo_screenwidth() - 50)
        height = min(820, self.winfo_screenheight() - 80)
        self.geometry(f"{width}x{height}")
        self.minsize(min(960, width), min(640, height))
        self.configure(background="#e9edf2")
        icon = Path(__file__).parent / "assets" / "ironanvil.ico"
        if sys.platform == "win32" and icon.is_file():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                logging.warning("The application icon could not be loaded")
        self._results: queue.Queue = queue.Queue()
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
        self._variables()
        self._style()
        self._build()
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
        self.aircraft_var = tk.StringVar(value=default_aircraft)
        self.mission_var = tk.StringVar(value=MISSION_LABELS["facility"])
        self.clients_var = tk.StringVar(value="2")
        self.difficulty_var = tk.StringVar(value="normal")
        self.enemy_cap_var = tk.BooleanVar(value=True)
        self.air_defenses_var = tk.BooleanVar(value=True)
        self.start_var = tk.StringVar(value="cold")
        self.time_var = tk.StringVar(value="day")
        self.weather_var = tk.StringVar(value="clear")
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
        style.configure("TFrame", background="#f5f7fa")
        style.configure("TLabel", background="#f5f7fa", foreground="#243448")
        style.configure("TLabelframe", background="#f5f7fa")
        style.configure("TLabelframe.Label", background="#f5f7fa", foreground="#243448")
        style.configure("TCheckbutton", background="#f5f7fa", foreground="#243448")
        style.configure("TRadiobutton", background="#f5f7fa", foreground="#243448")
        style.configure("TNotebook", background="#f5f7fa", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(10, 7))
        style.configure("TButton", padding=(9, 5))
        style.configure("Primary.TButton", font=(self._font_family, 11, "bold"), padding=(16, 10))
        style.configure("Help.TLabel", foreground="#5b6b7b", font=(self._font_family, 9))
        style.configure("Status.TLabel", font=(self._font_family, 10, "bold"))
        style.configure("Header.TFrame", background="#172b40")
        style.configure("Title.TLabel", background="#172b40", foreground="#ffffff",
                        font=(self._font_family, 23, "bold"))
        style.configure("Subtitle.TLabel", background="#172b40", foreground="#cbd8e5")

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self, style="Header.TFrame", padding=(22, 14))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="IRON ANVIL", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Choose your flight. Create a mission. Fly together in DCS World.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

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

    def _settings_tab(self, notebook, label):
        """Keep every setting reachable on small screens and at larger DPI."""
        container = ttk.Frame(notebook)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        canvas = tk.Canvas(container, background="#f5f7fa", highlightthickness=0,
                           width=340, height=430)
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
        flight_row = ttk.Frame(parent)
        flight_row.grid(row=4, column=0, sticky="ew", pady=(8, 0))
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
                  style="Help.TLabel", wraplength=315).grid(row=5, column=0, sticky="w", pady=(7, 10))
        ttk.Checkbutton(parent, text="Tanker support, where compatible", variable=self.tanker_var).grid(
            row=6, column=0, sticky="w", pady=3)
        ttk.Checkbutton(parent, text="AWACS support", variable=self.awacs_var).grid(
            row=7, column=0, sticky="w", pady=3)
        ttk.Checkbutton(parent, text="Airbase detail", variable=self.base_detail_var).grid(
            row=8, column=0, sticky="w", pady=3)
        ttk.Separator(parent).grid(row=9, column=0, sticky="ew", pady=9)
        ttk.Label(parent, text="Your airbase is friendly, with fuel and weapons available for rearming and refueling.",
                  style="Help.TLabel", wraplength=315).grid(row=10, column=0, sticky="w")

    def _mission_tab(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        self.mission_combo = self._combo(parent, 0, "Mission", self.mission_var, list(MISSION_LABELS.values()))
        self.mission_combo.bind("<<ComboboxSelected>>", self._mission_changed)
        ttk.Label(parent, textvariable=self.mission_help_var, style="Help.TLabel", wraplength=315).grid(
            row=2, column=0, sticky="w", pady=(8, 2))
        opposition_row = ttk.Frame(parent)
        opposition_row.grid(row=3, column=0, sticky="ew", pady=(8, 0))
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
        self.line_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))
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
        self._combo(weather_frame, 0, "Weather", self.weather_var, ["clear", "cloudy"], width=15)
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
        self.map_view.set_theatre(get_theatre(key))
        self._clear_target()
        self.opponent_combo.configure(state="readonly" if key == "syria" else "disabled")
        if key != "syria":
            self.opponent_var.set("regular")

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

    def _mission_changed(self, _event=None) -> None:
        mission = self._mission_by_label[self.mission_var.get()]
        self.mission_help_var.set(MISSION_HELP[mission])
        for check in self._line_buttons:
            check.configure(state="normal" if mission == "line" else "disabled")
        self._opposition_changed()

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
        return MissionOptions(
            map=self._map_by_label[self.theatre_var.get()],
            aircraft=self._aircraft_by_label[self.aircraft_var.get()]["id"],
            mission=mission,
            clients=int(self.clients_var.get()),
            difficulty=self.difficulty_var.get(),
            enemy_cap=self.enemy_cap_var.get(),
            air_defenses=self.air_defenses_var.get(),
            target_lat=lat,
            target_lon=lon,
            seed=seed,
            start=self.start_var.get(),
            time_of_day=self.time_var.get(),
            weather=self.weather_var.get(),
            tanker=self.tanker_var.get(),
            awacs=self.awacs_var.get(),
            loadout=self.loadout_var.get(),
            line_units=units,
            base_detail=self.base_detail_var.get(),
            output_dir=str(output),
            opponent=self.opponent_var.get(),
        ).validate()

    def _generate(self) -> None:
        if self._busy:
            return
        try:
            options = self.collect_options()
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Check mission settings", str(exc), parent=self)
            return
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

    def _poll_generation(self) -> None:
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
        if getattr(self, "_poll_timer", None):
            self.after_cancel(self._poll_timer)
            self._poll_timer = None
        super().destroy()

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="Mission output folder",
                                         initialdir=self.output_var.get(), mustexist=False)
        if folder:
            self.output_var.set(folder)

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
