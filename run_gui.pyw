import os, sys, traceback

here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
sys.path.insert(0, here)


def fail(text):
    """.pyw has no console, so a startup error would vanish. Save it and show it."""
    try:
        with open(os.path.join(here, "gui_error.log"), "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Iron Anvil Missions - could not start", text[-1700:] + "\n\n(saved to gui_error.log)")
        root.destroy()
    except Exception:
        pass


try:
    from ironanvil.gui import run
    run()
except BaseException:
    tb = traceback.format_exc()
    hint = ""
    if "No module named" in tb:
        hint = ("\n\nA package is missing for THIS Python. Install with the same interpreter:\n"
                f'"{sys.executable}" -m pip install -r requirements.txt')
    fail(f"Python {sys.version.split()[0]}  ({sys.executable})\n\n{tb}{hint}")
