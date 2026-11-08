"""Check GitHub Releases and apply Windows portable-EXE updates."""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

log = logging.getLogger("hh.updater")

_REPO = "AMonRa19/bluetooth-haptics"
_API_URL = f"https://api.github.com/repos/{_REPO}/releases?per_page=20"
_LOCAL_APP = getattr(sys, "frozen", False)
_APP_DIR = (
    Path(sys.executable).resolve().parent
    if _LOCAL_APP
    else Path(__file__).parent.resolve()
)
_LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
_STAGING = _LOCAL_APPDATA / "HorizonHaptics" / "update"


_RELEASE_TAG_PATTERN = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _parse_release_version(tag: str) -> tuple[int, int, int] | None:
    """Parse only public vMAJOR.MINOR.PATCH tags; ignore development tags."""
    match = _RELEASE_TAG_PATTERN.fullmatch(tag)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def check_for_update() -> tuple[str, str] | None:
    """Return the newest Windows portable package when a newer release exists."""
    if sys.platform != "win32" or not _LOCAL_APP:
        return None

    from version import __version__

    current_version = _parse_release_version(f"v{__version__}")
    if current_version is None:
        log.warning("Invalid application version %r; update checks disabled.", __version__)
        return None
    try:
        req = urllib.request.Request(
            _API_URL,
            headers={"User-Agent": "HorizonHaptics-Bluetooth"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            releases = json.loads(resp.read())

        candidates = []
        for release in releases if isinstance(releases, list) else []:
            tag = release.get("tag_name", "")
            parsed = _parse_release_version(tag)
            if parsed is None or parsed <= current_version:
                continue
            for asset in release.get("assets", []):
                name = asset.get("name", "")
                if name.endswith("-win64.zip"):
                    candidates.append((parsed, tag, asset["browser_download_url"]))
                    break

        if candidates:
            _, tag, url = max(candidates, key=lambda item: item[0])
            return tag, url
    except Exception as exc:
        log.debug("Update check failed: %s", exc)

    return None


def download_update(url: str, tag: str, progress_cb=None) -> Path | None:
    """Download the portable Windows update package."""
    try:
        _STAGING.mkdir(parents=True, exist_ok=True)
        dest = _STAGING / f"HorizonHaptics-{tag}-win64.zip"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "HorizonHaptics-Bluetooth"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            with open(dest, "wb") as fh:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded / total * 100)
        return dest
    except Exception as exc:
        log.error("Download failed: %s", exc)
        return None


def _ps_quote(value: str | Path) -> str:
    """Quote a path as a PowerShell single-quoted string."""
    return "'" + str(value).replace("'", "''") + "'"


def _apply_frozen_windows_update(zip_path: Path) -> None:
    """Replace the running one-file EXE after the current process exits."""
    app_exe = Path(sys.executable).resolve()
    helper = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".ps1",
        delete=False,
        prefix="hh_update_",
        encoding="utf-8",
    )
    helper.write(
        "$ErrorActionPreference = 'Stop'\n"
        f"$ZipPath = {_ps_quote(zip_path)}\n"
        f"$AppExe = {_ps_quote(app_exe)}\n"
        "$ExtractDir = Join-Path $env:TEMP ('HorizonHaptics-' + [guid]::NewGuid().ToString('N'))\n"
        "try {\n"
        "  Start-Sleep -Seconds 3\n"
        "  New-Item -ItemType Directory -Path $ExtractDir -Force | Out-Null\n"
        "  Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractDir -Force\n"
        "  $SourceExe = Join-Path $ExtractDir 'HorizonHaptics-Bluetooth.exe'\n"
        "  if (-not (Test-Path -LiteralPath $SourceExe)) { throw 'The update package does not contain the application EXE.' }\n"
        "  $Copied = $false\n"
        "  for ($i = 0; $i -lt 40; $i++) {\n"
        "    try {\n"
        "      Copy-Item -LiteralPath $SourceExe -Destination $AppExe -Force -ErrorAction Stop\n"
        "      $Copied = $true\n"
        "      break\n"
        "    } catch { Start-Sleep -Milliseconds 500 }\n"
        "  }\n"
        "  if (-not $Copied) { throw 'Could not replace the application EXE.' }\n"
        "  Start-Process -FilePath $AppExe -WorkingDirectory (Split-Path -Parent $AppExe)\n"
        "} catch {\n"
        "  Add-Content -LiteralPath (Join-Path $env:TEMP 'HorizonHaptics-update-error.log') -Value $_\n"
        "} finally {\n"
        "  Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue\n"
        "  Remove-Item -LiteralPath $ExtractDir -Recurse -Force -ErrorAction SilentlyContinue\n"
        "  Start-Sleep -Milliseconds 500\n"
        "  Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue\n"
        "}\n"
    )
    helper.close()

    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            helper.name,
        ],
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    log.info("Portable update helper launched.")


def apply_and_restart(zip_path: Path) -> None:
    """Launch the external updater; the caller should quit the application."""
    if sys.platform == "win32" and _LOCAL_APP:
        _apply_frozen_windows_update(zip_path)
        return

    log.warning("Automatic updates are available only in the Windows portable build.")


def start_check(callback) -> None:
    """Check for updates in the background and call callback(tag, URL)."""
    def _run():
        result = check_for_update()
        if result:
            callback(*result)

    threading.Thread(target=_run, daemon=True, name="hh-update-check").start()
