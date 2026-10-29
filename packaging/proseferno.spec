# PyInstaller spec for the Windows build: one folder with Proseferno.exe, Python, the backend and the built web app.
# Build with packaging\build_windows.bat (it builds the frontend first).
# ruff: noqa
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH is defined by PyInstaller)

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend_dist"),
    *collect_data_files("proseferno"),  # prompt templates
]
binaries = []
hiddenimports = [
    *collect_submodules("proseferno"),
    *collect_submodules("uvicorn"),
    *collect_submodules("keyring.backends"),
]
# Packages with native libraries or data files that imports alone do not find.
for package in ("vl_convert", "resvg_py", "pymupdf", "trafilatura", "justext", "courlan", "htmldate", "pptx", "docx", "certifi"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception:  # a package that is not installed is simply skipped
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT / "backend" / "src")],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "mypy", "ruff"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Proseferno",
    icon=str(ROOT / "frontend" / "public" / "favicon.ico"),
    # A console window shows the server log; closing it stops Proseferno (like launch.bat).
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Proseferno")  # noqa: F821
