"""Tk map planner: geographic outlines, opt-in OSM, and offline DCS chart import."""
from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import math
from pathlib import Path
from queue import Empty, Queue
from threading import Event
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from .mapdata import (Chart, ChartStore, CITIES, COUNTRY_POLYGONS, OSM_ATTRIBUTION,
                      TILE_SIZE, TileCache, Viewport, validate_bounds)


class MapView(ttk.Frame):
    """Select a (latitude, longitude); right-click reports (None, None).

    No network request occurs until the user enables Internet basemap. Tk and
    ImageTk remain on the UI thread; tile downloads/decoding use two workers.
    """
    def __init__(self, parent, on_select=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_select = on_select or (lambda lat, lon: None)
        self.viewport = Viewport()
        self.theatre = None
        self.target = None
        self._airports = []
        self._home_airport = None
        self._map_colors = {"ocean": "#a8c8d8", "land": "#e4dec5", "outline": "#a49e83",
                            "text": "#35423f", "label": "#f5f2e7", "grid": "#738994",
                            "boundary": "#4f5362", "neutral": "#65717b", "friendly": "#1263b5",
                            "enemy": "#b52f2c", "target": "#da2831"}
        self._chart = None
        self._chart_image = None
        self._store = ChartStore()
        self._cache = TileCache()
        self._tiles = OrderedDict()
        self._pending = set()
        self._failures = {}
        self._results = Queue()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ironanvil-map")
        self._network_enabled = Event()
        self._images = []
        self._drag = None
        self._fitted = False
        self._fit_to_theatre = True
        self._destroyed = False
        self._render_timer = None
        self._online = tk.BooleanVar(value=False)
        self._message = tk.StringVar(value="Drag to pan · scroll to zoom · click to place a target · right-click to clear")
        self._coordinates = tk.StringVar(value="")
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="+", width=3, command=self.zoom_in).pack(side="left")
        ttk.Button(toolbar, text="-", width=3, command=self.zoom_out).pack(side="left", padx=(2, 3))
        ttk.Button(toolbar, text="Fit map", command=self.fit).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(toolbar, text="Internet map (OSM)", variable=self._online,
                        command=self._online_changed).pack(side="left")
        chart_toolbar = ttk.Frame(self)
        chart_toolbar.pack(fill="x", pady=(3, 0))
        ttk.Button(chart_toolbar, text="Import DCS chart...", command=self._import_dialog).pack(side="left", padx=(0, 3))
        ttk.Button(chart_toolbar, text="Clear chart", command=self.clear_overlay).pack(side="left")
        self.canvas = tk.Canvas(self, width=720, height=420, background="#a8c8d8", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=4)
        self._coordinate_label = ttk.Label(self, textvariable=self._coordinates, wraplength=650)
        self._coordinate_label.pack(anchor="w")
        self._status_label = ttk.Label(self, textvariable=self._message, wraplength=650)
        self._status_label.pack(anchor="w")
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Button-3>", self._clear_target)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda e: self._wheel(e, 1))
        self.canvas.bind("<Button-5>", lambda e: self._wheel(e, -1))
        self.bind("<Destroy>", self._dispose, add=True)
        self._poll_timer = self.after(100, self._poll)

    def set_theatre(self, theatre):
        self.theatre = theatre
        self.target = None
        self._airports = list(theatre.airports()) if callable(getattr(theatre, "airports", None)) else []
        self._chart, self._chart_image = None, None
        try:
            chart = self._store.load(theatre.key)
            if chart:
                self._load_chart(chart)
        except (OSError, ValueError, KeyError) as exc:
            self._message.set(f"Saved chart could not be loaded: {exc}")
        self.fit()

    def set_theme(self, palette):
        """Theme offline geometry and labels; leave imported/online imagery intact."""
        dark = palette.get("theme", "dark") == "dark"
        self._map_colors.update({
            "ocean": "#142837" if dark else "#a8c8d8",
            "land": "#293b49" if dark else "#e4dec5",
            "outline": "#526777" if dark else "#a49e83",
            "text": palette.get("foreground", "#35423f"),
            "label": palette.get("field", "#f5f2e7"),
            "grid": "#627c90" if dark else "#738994",
            "boundary": "#9ab7d2" if dark else "#4f5362",
            "neutral": "#9daebb" if dark else "#65717b",
            "friendly": "#69b9ff" if dark else "#1263b5",
            "enemy": "#ff9690" if dark else "#b52f2c",
            "target": "#ff7777" if dark else "#da2831",
        })
        self.canvas.configure(background=self._map_colors["ocean"])
        self._schedule_render()

    def set_home_airport(self, name):
        self._home_airport = name
        self._schedule_render()

    def set_target(self, lat, lon=None):
        self.target = None if lat is None or lon is None else (float(lat), float(lon))
        self._schedule_render()

    def fit(self):
        self._fit_to_theatre = True
        if self.theatre:
            width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
            if width > 20 and height > 20:
                self.viewport.width, self.viewport.height = width, height
            self.viewport.fit(self.theatre.bounds, padding=12)
            self._fitted = self.canvas.winfo_width() > 20
        self._schedule_render()

    def zoom_in(self):
        self._fit_to_theatre = False
        self.viewport.zoom_at(1)
        self._schedule_render()

    def zoom_out(self):
        self._fit_to_theatre = False
        self.viewport.zoom_at(-1)
        self._schedule_render()

    def set_online(self, enabled):
        self._online.set(bool(enabled))
        self._online_changed()

    def _online_changed(self):
        if self._online.get():
            self._network_enabled.set()
        else:
            self._network_enabled.clear()
        self._failures.clear()
        self._schedule_render()

    def _load_chart(self, chart):
        with Image.open(chart.path) as source:
            self._chart_image = source.convert("RGB")
        self._chart = chart

    def import_overlay(self, path, bounds=None, crs="EPSG:4326"):
        if self.theatre is None:
            raise ValueError("Choose a theatre first")
        chart = ChartStore.metadata(path) if bounds is None else Chart(Path(path), bounds, crs)
        if chart is None:
            raise ValueError("Chart needs a JSON sidecar or west, south, east, north bounds")
        stored = self._store.save(self.theatre.key, chart)
        self._load_chart(stored)
        self._schedule_render()
        return stored

    def clear_overlay(self):
        if self.theatre:
            self._store.clear(self.theatre.key)
        self._chart, self._chart_image = None, None
        self._schedule_render()

    def _import_dialog(self):
        if self.theatre is None:
            return
        path = filedialog.askopenfilename(parent=self, title="Import a georeferenced DCS chart",
                filetypes=[("Chart images", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"), ("All files", "*")])
        if not path:
            return
        try:
            chart = ChartStore.metadata(path)
            if chart is None:
                text = simpledialog.askstring("Geographic chart bounds",
                    "Use a north-up, georeferenced chart exported from your DCS map.\n"
                    "Raw perspective screenshots need georeferencing first.\n\n"
                    "Enter bounds as west, south, east, north in decimal degrees:\n"
                    "For automatic import, place these in image.png.json as\n"
                    '{"bounds": [west, south, east, north], "crs": "EPSG:4326"}', parent=self)
                if text is None:
                    return
                bounds = validate_bounds([part.strip() for part in text.split(",")])
                projection = simpledialog.askstring("Chart pixel projection",
                    "EPSG:4326 = image rows evenly spaced in latitude.\n"
                    "EPSG:3857 = Web Mercator image.\n"
                    "Bounds are geographic degrees for either projection.\n\n"
                    "Enter the chart's actual projection:", initialvalue="EPSG:4326", parent=self)
                if projection is None:
                    return
                self.import_overlay(path, bounds, projection.strip().upper())
            else:
                self.import_overlay(path)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("Cannot import chart", str(exc), parent=self)

    def _resize(self, event):
        self.viewport.width, self.viewport.height = max(1, event.width), max(1, event.height)
        self._coordinate_label.configure(wraplength=max(100, event.width - 8))
        self._status_label.configure(wraplength=max(100, event.width - 8))
        if self.theatre and self._fit_to_theatre:
            self.fit()
        self._schedule_render()

    def _press(self, event):
        self._drag = (event.x, event.y, self.viewport.center_x, self.viewport.center_y, False)
        self.canvas.configure(cursor="fleur")

    def _motion(self, event):
        if self._drag:
            x, y, cx, cy, moved = self._drag
            moved = moved or abs(event.x - x) + abs(event.y - y) > 5
            self._drag = (x, y, cx, cy, moved)
            if moved:
                self._fit_to_theatre = False
                self.viewport.center_x = max(0, min(1, cx - (event.x - x) / self.viewport.scale))
                self.viewport.center_y = max(0, min(1, cy - (event.y - y) / self.viewport.scale))
                self._schedule_render()
        self._hover(event)

    def _release(self, event):
        drag, self._drag = self._drag, None
        self.canvas.configure(cursor="")
        if drag is None or drag[4] or self.theatre is None:
            return
        lat, lon = self.viewport.to_latlon(event.x, event.y)
        west, south, east, north = self.theatre.bounds
        if west <= lon <= east and south <= lat <= north:
            self.set_target(lat, lon)
            self.on_select(lat, lon)
        else:
            self._message.set("Choose a target inside the dashed theatre boundary.")

    def _hover(self, event):
        lat, lon = self.viewport.to_latlon(event.x, event.y)
        hovered = next((a["name"] for a in self._airports
                        if math.dist(self.viewport.to_pixel(a["lat"], a["lon"]), (event.x, event.y)) < 9), None)
        suffix = f"   |   {hovered}" if hovered else "   |   Blue: friendly, red: enemy, gray: neutral"
        self._coordinates.set(f"Cursor: {lat:.5f}°, {lon:.5f}°   |   Zoom {self.viewport.zoom}{suffix}")

    def _clear_target(self, event=None):
        self.set_target(None, None)
        self.on_select(None, None)

    def _wheel(self, event, delta=None):
        self._fit_to_theatre = False
        delta = delta if delta is not None else (1 if event.delta > 0 else -1)
        self.viewport.zoom_at(delta, event.x, event.y)
        self._schedule_render()
        return "break"

    def _schedule_render(self):
        if not self._destroyed and self._render_timer is None:
            self._render_timer = self.after_idle(self._render)

    def _render(self):
        self._render_timer = None
        if self._destroyed:
            return
        canvas = self.canvas
        canvas.delete("all")
        self._images.clear()
        if self.theatre is None:
            canvas.create_text(20, 20, anchor="nw", text="Choose a map to plan a target.", fill=self._map_colors["text"])
            return
        for _name, polygon in COUNTRY_POLYGONS:
            points = [self.viewport.to_pixel(lat, lon) for lon, lat in polygon]
            xs, ys = zip(*points)
            if max(xs) < 0 or min(xs) > self.viewport.width or max(ys) < 0 or min(ys) > self.viewport.height:
                continue
            canvas.create_polygon(points, fill=self._map_colors["land"], outline=self._map_colors["outline"], width=1)
        if self._online.get() and self._chart_image is None:
            self._draw_tiles()
        if self._chart_image is not None:
            self._draw_chart()
        self._draw_grid()
        west, south, east, north = self.theatre.bounds
        x1, y1 = self.viewport.to_pixel(north, west)
        x2, y2 = self.viewport.to_pixel(south, east)
        canvas.create_rectangle(x1, y1, x2, y2, outline=self._map_colors["boundary"], dash=(5, 4), width=2)
        for lat, lon, name in CITIES.get(self.theatre.key, ()):
            x, y = self.viewport.to_pixel(lat, lon)
            if -80 <= x <= self.viewport.width + 80 and -20 <= y <= self.viewport.height + 20:
                canvas.create_oval(x-2, y-2, x+2, y+2, fill=self._map_colors["text"], outline="")
                self._label(x+5, y-4, name)
        label_boxes = []
        airports = sorted(self._airports, key=lambda a: (a["name"] != self._home_airport,
                           a.get("friendly") is not True, a.get("helicopter_only", False), a["name"]))
        for airport in airports:
            x, y = self.viewport.to_pixel(airport["lat"], airport["lon"])
            if not (-8 <= x <= self.viewport.width + 8 and -8 <= y <= self.viewport.height + 8):
                continue
            selected = airport["name"] == self._home_airport
            side = "friendly" if selected or airport.get("friendly") is True else (
                "enemy" if airport.get("friendly") is False else "neutral")
            color = self._map_colors[side]
            canvas.create_rectangle(x-3, y-3, x+3, y+3, fill=color, outline=self._map_colors["label"])
            if selected:
                canvas.create_oval(x-9, y-9, x+9, y+9, outline=color, width=2)
            text = ("Home: " if selected else "") + airport["name"]
            box = (x+7, y+4, x+12+len(text)*6.5, y+20)
            if selected or not any(box[0] < old[2] and box[2] > old[0]
                                   and box[1] < old[3] and box[3] > old[1] for old in label_boxes):
                self._label(x+7, y+5, text, color)
                label_boxes.append(box)
        if self.target:
            lat, lon = self.target
            x, y = self.viewport.to_pixel(lat, lon)
            canvas.create_oval(x-8, y-8, x+8, y+8, outline=self._map_colors["target"], width=3)
            canvas.create_line(x-13, y, x+13, y, fill=self._map_colors["target"], width=2)
            canvas.create_line(x, y-13, x, y+13, fill=self._map_colors["target"], width=2)
            self._label(x+12, y-12, f"Target {lat:.4f}, {lon:.4f}", self._map_colors["target"])
        if self._chart:
            self._message.set(f"Local DCS chart: {self._chart.path.name} · {self._chart.crs} · cached offline · accuracy depends on georeferencing")
        elif self._online.get():
            suffix = " · Some tiles unavailable; geographic outlines shown" if self._failures else ""
            self._message.set(OSM_ATTRIBUTION + suffix)
        else:
            self._message.set("Natural Earth geography (public domain, coarse coastlines) · Import a georeferenced DCS chart for its actual map imagery")

    def _label(self, x, y, text, color=None):
        item = self.canvas.create_text(x, y, anchor="nw", text=text,
                                       fill=color or self._map_colors["text"], font=("TkDefaultFont", 9))
        bounds = self.canvas.bbox(item)
        if bounds:
            background = self.canvas.create_rectangle(bounds, fill=self._map_colors["label"], outline="")
            self.canvas.tag_lower(background, item)

    def _draw_grid(self):
        south, west = self.viewport.to_latlon(0, self.viewport.height)
        north, east = self.viewport.to_latlon(self.viewport.width, 0)
        span = max(east-west, north-south)
        step = next((v for v in (.02, .05, .1, .25, .5, 1, 2, 5, 10, 20, 45) if span / v <= 10), 90)
        lon = math.ceil(west / step) * step
        for _ in range(14):
            if lon > east:
                break
            x, _y = self.viewport.to_pixel(north, lon)
            self.canvas.create_line(x, 0, x, self.viewport.height, fill=self._map_colors["grid"], dash=(2, 6), stipple="gray50")
            self._label(x+3, 4, f"{lon:.2f}°")
            lon += step
        lat = math.ceil(south / step) * step
        for _ in range(14):
            if lat > north:
                break
            _x, y = self.viewport.to_pixel(lat, west)
            self.canvas.create_line(0, y, self.viewport.width, y, fill=self._map_colors["grid"], dash=(2, 6), stipple="gray50")
            self._label(4, y+2, f"{lat:.2f}°")
            lat += step

    def _draw_tiles(self):
        scale = self.viewport.scale
        left = self.viewport.center_x * scale - self.viewport.width / 2
        top = self.viewport.center_y * scale - self.viewport.height / 2
        zoom = self.viewport.zoom
        maximum = 2 ** zoom
        for tx in range(max(0, math.floor(left / TILE_SIZE)), min(maximum, math.ceil((left+self.viewport.width) / TILE_SIZE))):
            for ty in range(max(0, math.floor(top / TILE_SIZE)), min(maximum, math.ceil((top+self.viewport.height) / TILE_SIZE))):
                key = (zoom, tx, ty)
                tile = self._tiles.get(key)
                if tile is not None:
                    self._tiles.move_to_end(key)
                    photo = ImageTk.PhotoImage(tile, master=self.canvas)
                    self._images.append(photo)
                    self.canvas.create_image(tx*TILE_SIZE-left, ty*TILE_SIZE-top, anchor="nw", image=photo)
                elif (key not in self._pending and len(self._pending) < 24
                      and time.monotonic() - self._failures.get(key, -1000) > 60):
                    self._pending.add(key)
                    future = self._executor.submit(self._fetch_tile, key)
                    future.add_done_callback(lambda done, tile_key=key: self._queue_tile(tile_key, done))

    def _fetch_tile(self, key):
        # Recheck consent when a queued task starts, so turning Internet off
        # stops queued downloads as well as preventing new submissions.
        return self._cache.get(*key, online=self._network_enabled.is_set())

    def _queue_tile(self, key, future):
        try:
            self._results.put((key, future.result(), None))
        except Exception as exc:
            self._results.put((key, None, str(exc)))

    def _poll(self):
        changed = False
        try:
            while True:
                key, result, error = self._results.get_nowait()
                self._pending.discard(key)
                if error:
                    self._failures[key] = time.monotonic()
                elif result is not None:
                    self._tiles[key] = result
                    while len(self._tiles) > 128:
                        self._tiles.popitem(last=False)
                changed = True
        except Empty:
            pass
        if changed:
            self._schedule_render()
        if not self._destroyed:
            self._poll_timer = self.after(100, self._poll)

    def _draw_chart(self):
        west, south, east, north = self._chart.bounds
        x0, y0 = self.viewport.to_pixel(north, west)
        x1, y1 = self.viewport.to_pixel(south, east)
        left, top = max(0, math.floor(x0)), max(0, math.floor(y0))
        right, bottom = min(self.viewport.width, math.ceil(x1)), min(self.viewport.height, math.ceil(y1))
        if right <= left or bottom <= top:
            return
        # Row-wise mesh warps a geographic image into Mercator. It also crops to
        # the viewport before allocation, keeping large zoom levels inexpensive.
        width, height = right-left, bottom-top
        mesh = []
        for y in range(0, height, 16):
            next_y = min(height, y+16)
            quad = []
            for px, py in ((left, top+y), (left, top+next_y), (right, top+next_y), (right, top+y)):
                quad.extend(self._chart.source_pixel(*self.viewport.to_latlon(px, py), self._chart_image.size))
            mesh.append(((0, y, width, next_y), tuple(quad)))
        rendered = self._chart_image.transform((width, height), Image.Transform.MESH, mesh,
                                                resample=Image.Resampling.BILINEAR)
        photo = ImageTk.PhotoImage(rendered, master=self.canvas)
        self._images.append(photo)
        self.canvas.create_image(left, top, anchor="nw", image=photo)

    def _dispose(self, event):
        if event.widget is not self or self._destroyed:
            return
        self._destroyed = True
        self._network_enabled.clear()
        self.after_cancel(self._poll_timer)
        if self._render_timer is not None:
            self.after_cancel(self._render_timer)
        self._executor.shutdown(wait=False, cancel_futures=True)
