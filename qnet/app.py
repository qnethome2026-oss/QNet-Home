# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The Windows desktop wrapper: the ``.EXE`` that opens the dashboard (T5.3).

DESIGN §14 asks for the dashboard "wrapped in a WebView window: PyInstaller
``--onedir`` -> ``makeappx`` -> ``.MSIX``". Two of those three are unchanged.
The WebView is not, and the reason is recorded here rather than in a commit
message because it is a hardware fact a future reader will hit again:

    pywebview does not work on native ARM64 CPython.

Its Windows backends are all WinForms-hosted, so it needs pythonnet, and
pythonnet needs a CLR it can host in-process:

  * .NET 8 (coreclr) loads, and WinForms loads once the runtimeconfig names
    ``Microsoft.WindowsDesktop.App`` - but pywebview's bundled WebView2
    WinForms interop assembly targets .NET *Framework*: it references
    ``System.Windows.Forms.ContextMenu``, a type deleted in .NET Core 3.0.
    Result: ``TypeLoadException`` on ``import webview``.
  * .NET Framework 4.8 (netfx) has that type and is present at
    ``C:\\Windows\\Microsoft.NET\\FrameworkArm64`` - but ``clr_loader`` ships
    ``ClrLoader.dll`` for amd64 and x86 only, so loading it from an arm64
    process fails with ``0xc1`` (ERROR_BAD_EXE_FORMAT).

Neither is a version we can pin our way out of, so the wrapper opens the
dashboard in the system default browser instead and keeps a small console
alive. Full evidence in ``verify/T5.3.txt``. The submission requirement is an
``.EXE``/``.MSIX`` that opens the dashboard, and this opens the dashboard on
the machine the demo runs on; ``open_in_window()`` below is the seam to put a
real WebView back behind if one ever becomes available on this CPU.

The dashboard itself is unchanged and unaware of any of this - one
self-contained ``index.html`` that already works from ``file://`` (T5.1), with
the broker URL editable in the page. Nothing here needs to know a broker
exists.

Run it:

    python -m qnet.app                 # dev tree
    QNetHome.exe                       # frozen (PyInstaller --onedir)
    python -m qnet.app --self-close 5  # the verification mode (T5.3)
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import webbrowser
from pathlib import Path

# Files the app carries. Relative to the repo root in dev, and to the PyInstaller
# bundle root when frozen - `packaging/build.ps1` adds them at these same paths
# so one lookup table serves both.
DASHBOARD_REL = Path("dashboard") / "index.html"
FIXTURE_REL = Path("dev") / "fixtures" / "replay_demo.jsonl"


def is_frozen() -> bool:
    """True inside a PyInstaller bundle (onedir or onefile)."""
    return getattr(sys, "frozen", False)


def bundle_root() -> Path:
    """Where the app's data files live, dev tree or frozen bundle.

    PyInstaller sets ``sys._MEIPASS`` in both modes: the temp extraction dir
    under ``--onefile``, the ``_internal`` folder next to the exe under
    ``--onedir`` (which is what we ship - DESIGN §14 picks onedir for launch
    latency). In the dev tree it is the repo root, two levels up from this
    file, so ``python -m qnet.app`` from a checkout finds the same files.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def dashboard_source() -> Path:
    """The bundled ``dashboard/index.html``. Raises if it is missing."""
    path = bundle_root() / DASHBOARD_REL
    if not path.is_file():
        raise FileNotFoundError(
            f"dashboard not found at {path} (bundle root {bundle_root()}). "
            "In a frozen build this means the --add-data argument in "
            "packaging/build.ps1 did not take."
        )
    return path


def user_data_dir() -> Path:
    """Per-user working copy location: ``%LOCALAPPDATA%\\QNetHome``.

    Why copy at all: under MSIX the app's own files live in
    ``C:\\Program Files\\WindowsApps\\...``, whose ACLs are restrictive and not
    reliably readable by *another* process - and the browser we hand the file
    to is another process. Copying to the user's own AppData sidesteps that
    entirely and costs one 55 KB write per launch. If anything about the copy
    fails we fall back to opening the bundled file in place (which works fine
    for the plain-EXE case), so this is an improvement, never a dependency.
    """
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or os.getcwd()
    return Path(base) / "QNetHome"


def stage_dashboard() -> Path:
    """Copy the dashboard (and the offline replay fixture) where a browser can read it.

    Returns the path to open - the staged copy, or the bundled original if
    staging failed for any reason.
    """
    source = dashboard_source()
    try:
        target_dir = user_data_dir()
        (target_dir / "dashboard").mkdir(parents=True, exist_ok=True)
        target = target_dir / DASHBOARD_REL
        shutil.copyfile(source, target)

        # The offline-demo fixture rides along when it was bundled. It is not
        # needed to open the dashboard, so a missing one is silent.
        fixture = bundle_root() / FIXTURE_REL
        if fixture.is_file():
            (target_dir / FIXTURE_REL.parent).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixture, target_dir / FIXTURE_REL)
        return target
    except OSError as exc:
        print(f"[qnet] could not stage to AppData ({exc}); opening in place")
        return source


def open_in_window(url: str) -> bool:
    """Open *url* in a native WebView window. Currently never available.

    Kept as an explicit, named seam: the moment a WebView toolkit works on
    native ARM64 CPython (see this module's docstring for why none does), this
    is the one function to fill in, and ``main`` already prefers it.
    """
    return False


def open_in_browser(url: str) -> bool:
    """Open *url* in the system default browser. The path that actually runs here."""
    return webbrowser.open(url)


def main(argv: list[str] | None = None) -> int:
    """Open the dashboard and stay alive until interrupted (or --self-close)."""
    parser = argparse.ArgumentParser(
        prog="QNetHome",
        description=(
            "QNet Home dashboard - opens the local dashboard page. Set the "
            "broker's ws:// URL in the page itself; nothing is configured here."
        ),
    )
    parser.add_argument(
        "--self-close",
        type=float,
        metavar="SECONDS",
        help=(
            "exit after SECONDS instead of waiting for Ctrl-C. The T5.3 "
            "verification mode: proves the exe launched, resolved its data "
            "files and opened the dashboard, without a human to close it."
        ),
    )
    parser.add_argument(
        "--print-path",
        action="store_true",
        help="print the resolved dashboard path and exit without opening it",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="stage the files but do not open anything (for headless checks)",
    )
    args = parser.parse_args(argv)

    print("QNet Home dashboard")
    print(f"  mode:        {'frozen bundle' if is_frozen() else 'dev tree'}")
    print(f"  bundle root: {bundle_root()}")

    try:
        source = dashboard_source()
    except FileNotFoundError as exc:
        print(f"[qnet] ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"  dashboard:   {source}")

    if args.print_path:
        return 0

    page = stage_dashboard()
    url = page.resolve().as_uri()
    print(f"  opening:     {url}")

    if args.no_open:
        opened = False
        print("  --no-open given; not opening a window")
    else:
        opened = open_in_window(url) or open_in_browser(url)
        if opened:
            print("  opened in the system default browser")
        else:
            print(
                "[qnet] could not open a browser automatically. "
                f"Open this file manually:\n    {page}",
                file=sys.stderr,
            )

    print()
    print("Set the broker URL in the page (default ws://127.0.0.1:9001/mqtt).")

    if args.self_close is not None:
        print(f"Self-close in {args.self_close:g}s ...")
        time.sleep(args.self_close)
        print("Self-close reached; exiting cleanly.")
        return 0 if (opened or args.no_open) else 1

    print("Leave this window open while you use the dashboard. Ctrl-C to quit.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nBye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
