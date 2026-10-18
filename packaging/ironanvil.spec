# Build on Windows x64 using CPython 3.12: tools/build_windows.ps1
# A one-folder bundle starts without a console, an installer, or user Python.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parent
# pydcs selects terrain and aircraft modules dynamically. Collect every module
# so Caucasus, Syria and Germany all work from the frozen executable.
dcs_data, dcs_binaries, dcs_imports = collect_all("dcs")
proj_data, proj_binaries, proj_imports = collect_all("pyproj")
pil_data, pil_binaries, pil_imports = collect_all("PIL")
app_data = collect_data_files("ironanvil")
metadata = copy_metadata("pydcs") + copy_metadata("pyproj") + copy_metadata("Pillow")
icon = root / "ironanvil" / "assets" / "ironanvil.ico"

analysis = Analysis(
    [str(root / "packaging" / "entrypoint.py")],
    pathex=[str(root)],
    binaries=dcs_binaries + proj_binaries + pil_binaries,
    datas=dcs_data + proj_data + pil_data + app_data + metadata,
    hiddenimports=dcs_imports + proj_imports + pil_imports + ["ironanvil.gui", "tkinter", "PIL.ImageTk"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest", "pip", "setuptools", "IPython", "jupyter", "matplotlib"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="IronAnvil",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    version=str(root / "packaging" / "version_info.txt"),
    icon=str(icon) if icon.is_file() else None,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="IronAnvil",
)
