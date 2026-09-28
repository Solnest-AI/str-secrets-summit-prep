#!/usr/bin/env python3
"""STR Secrets Summit prep, part 2: ffmpeg + ffprobe, then the Content Studio's headless browser.

prep.sh runs this through uv after it has checked the tools. Standard library only.

  ffmpeg / ffprobe   reused if this machine already has a working copy (PATH, Homebrew,
                     winget, chocolatey, scoop, ~/.local/bin); otherwise downloaded into
                     ~/.local/bin (the folder uv lives in, so it is on the PATH after a restart,
                     and the Content Studio looks there too). No admin, nothing system-wide.
  headless browser   Playwright's Chromium shell and the Content Studio's Python packages,
                     fetched now so nobody downloads 200 MB on the venue wifi on Tuesday.

Exit 0: all set. Exit 3: all set and something was downloaded. Exit 1: something failed.
The download code is the Content Studio's own (scripts/setup.py), with the same mirrors.
"""
import gzip
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile

NEEDED = ("ffmpeg", "ffprobe")
EXE = ".exe" if os.name == "nt" else ""
HOME = pathlib.Path.home()
DEST = HOME / ".local" / "bin"
PLAYWRIGHT = "playwright==1.60.0"     # the Content Studio's pin; the browser build must match it
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

GH = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"
BTBN = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
MR = "https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release"


def _pair(tag):
    return [{"url": f"{GH}/ffmpeg-{tag}.gz", "gz": "ffmpeg"},
            {"url": f"{GH}/ffprobe-{tag}.gz", "gz": "ffprobe"}]


SOURCES = {
    ("Windows", "x64"): [
        ("gyan.dev", [{"url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"}]),
        ("BtbN on GitHub", [{"url": f"{BTBN}/ffmpeg-master-latest-win64-gpl.zip"}]),
        ("ffmpeg-static on GitHub", _pair("win32-x64")),
    ],
    ("Darwin", "arm64"): [
        ("ffmpeg-static on GitHub", _pair("darwin-arm64")),
        ("martin-riedl.de", [{"url": MR.format(arch="arm64") + "/ffmpeg.zip"},
                             {"url": MR.format(arch="arm64") + "/ffprobe.zip"}]),
    ],
    ("Darwin", "x64"): [
        ("ffmpeg-static on GitHub", _pair("darwin-x64")),
        ("martin-riedl.de", [{"url": MR.format(arch="amd64") + "/ffmpeg.zip"},
                             {"url": MR.format(arch="amd64") + "/ffprobe.zip"}]),
        ("evermeet.cx", [{"url": "https://evermeet.cx/ffmpeg/getrelease/zip"},
                         {"url": "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"}]),
    ],
    ("Linux", "x64"): [
        ("BtbN on GitHub", [{"url": f"{BTBN}/ffmpeg-master-latest-linux64-gpl.tar.xz"}]),
        ("ffmpeg-static on GitHub", _pair("linux-x64")),
    ],
    ("Linux", "arm64"): [
        ("BtbN on GitHub", [{"url": f"{BTBN}/ffmpeg-master-latest-linuxarm64-gpl.tar.xz"}]),
        ("ffmpeg-static on GitHub", _pair("linux-arm64")),
    ],
}
SOURCES[("Windows", "arm64")] = SOURCES[("Windows", "x64")]     # runs under emulation


def say(ok, text):
    print(("✅ " if ok else "❌ ") + text, flush=True)


def platform_key():
    m = platform.machine().lower()
    return platform.system(), ("arm64" if m in ("arm64", "aarch64") else "x64")


def candidates(name):
    """Every place a working ffmpeg/ffprobe might already be, most trusted first."""
    found = shutil.which(name)
    if found:
        yield pathlib.Path(found)
    yield DEST / f"{name}{EXE}"
    if os.name == "nt":
        local = pathlib.Path(os.environ.get("LOCALAPPDATA") or HOME / "AppData" / "Local")
        yield local / "Microsoft" / "WinGet" / "Links" / f"{name}.exe"
        try:
            yield from sorted((local / "Microsoft" / "WinGet" / "Packages").glob(f"Gyan.FFmpeg*/*/bin/{name}.exe"))
        except OSError:
            pass
        yield pathlib.Path(os.environ.get("ProgramData") or "C:/ProgramData") / "chocolatey" / "bin" / f"{name}.exe"
        yield HOME / "scoop" / "shims" / f"{name}.exe"
        yield pathlib.Path("C:/ffmpeg/bin") / f"{name}.exe"
    else:
        for d in ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin", "/usr/bin", "/snap/bin"):
            yield pathlib.Path(d) / name


def version(path):
    """First line of `<tool> -version`, or '' if it does not run here."""
    try:
        r = subprocess.run([str(path), "-version"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    line = (r.stdout or "").splitlines()[0] if r.stdout else ""
    return line if r.returncode == 0 and "version" in line else ""


def find_working(name):
    for c in candidates(name):
        try:
            if c.is_file() and os.access(c, os.X_OK):
                v = version(c)
                if v:
                    return str(c), v
        except OSError:
            continue
    return None


def download(url, dest, timeout=60):
    """Stream url to dest, printing a dot every 4 MB. Returns bytes written."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    part = dest.with_name(dest.name + ".part")
    got, next_dot = 0, 4 * 1024 * 1024
    with urllib.request.urlopen(req, timeout=timeout) as r, open(part, "wb") as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if got >= next_dot:
                print(".", end="", flush=True)
                next_dot += 4 * 1024 * 1024
    part.replace(dest)
    return got


class PrepError(RuntimeError):
    pass


def harvest(archive, into, gz_name=None):
    """Pull ffmpeg/ffprobe out of a zip, a tar(.xz/.gz) or one gzipped binary into `into`."""
    archive, into = pathlib.Path(archive), pathlib.Path(into)
    into.mkdir(parents=True, exist_ok=True)
    wanted = {n + EXE: n for n in NEEDED}
    found = []
    if gz_name:
        with gzip.open(archive, "rb") as src, open(into / (gz_name + EXE), "wb") as dst:
            shutil.copyfileobj(src, dst)
        return [gz_name]
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                base = pathlib.PurePosixPath(info.filename).name
                if base in wanted and not info.is_dir():
                    with z.open(info) as src, open(into / base, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found.append(wanted[base])
        return found
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                base = pathlib.PurePosixPath(m.name).name
                if base in wanted and m.isfile():
                    src = t.extractfile(m)
                    with open(into / base, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    found.append(wanted[base])
        return found
    raise PrepError(f"{archive.name} is not a zip, tar or gz file")


def make_executable(path):
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass
    if sys.platform == "darwin":
        subprocess.run(["xattr", "-d", "com.apple.quarantine", str(path)], capture_output=True)


def ensure_ffmpeg(check=False):
    """Returns (ok, downloaded)."""
    have = {n: find_working(n) for n in NEEDED}
    if all(have.values()):
        for n in NEEDED:
            say(True, f"{n} {have[n][1].split(' Copyright')[0].split('version ')[-1]}   {have[n][0]}")
        return True, False
    if check:
        say(False, "ffmpeg: not installed yet (run without --check to add it)")
        return False, False
    system, arch = platform_key()
    srcs = SOURCES.get((system, arch), [])
    if not srcs:
        say(False, f"ffmpeg: no download for {system}/{arch}; install ffmpeg by hand")
        return False, False
    errors = []
    tmp = DEST / "_ffmpeg_download"
    for label, parts in srcs:
        print(f"   downloading ffmpeg from {label} ", end="", flush=True)
        try:
            tmp.mkdir(parents=True, exist_ok=True)
            for part in parts:
                name = part["url"].rsplit("/", 1)[-1].split("?")[0] or "download.bin"
                download(part["url"], tmp / name)
                harvest(tmp / name, DEST, gz_name=part.get("gz"))
            got = {}
            for n in NEEDED:
                p = DEST / (n + EXE)
                if not p.is_file():
                    raise PrepError(f"{label} did not contain {n}")
                make_executable(p)
                v = version(p)
                if not v:
                    raise PrepError(f"{n} from {label} does not run on this machine")
                got[n] = (str(p), v)
            print(" ok", flush=True)
            shutil.rmtree(tmp, ignore_errors=True)
            for n in NEEDED:
                say(True, f"{n} {got[n][1].split(' Copyright')[0].split('version ')[-1]}   {got[n][0]} (just downloaded)")
            return True, True
        except (urllib.error.URLError, TimeoutError, OSError, PrepError,
                zipfile.BadZipFile, tarfile.TarError, EOFError) as e:
            print(" failed", flush=True)
            errors.append(f"{label}: {str(e)[:140]}")
            for n in NEEDED:
                try:
                    (DEST / (n + EXE)).unlink()
                except OSError:
                    pass
    shutil.rmtree(tmp, ignore_errors=True)
    say(False, "ffmpeg: every download failed, usually the network. Run this again. (" + " | ".join(errors) + ")")
    return False, False


BROWSER_PROBE = ("from playwright.sync_api import sync_playwright\n"
                 "p = sync_playwright().start()\n"
                 "b = p.chromium.launch(); b.close(); p.stop(); print('browser ok')\n")


def uv_python(uv, code_or_args, timeout):
    cmd = [uv, "run", "--no-project", "--python", "3.13", "--with", PLAYWRIGHT, "--with", "pillow>=10", "python"]
    cmd += code_or_args
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def ensure_browser(uv, check=False):
    """The Content Studio's headless browser and packages, fetched ahead. Returns (ok, downloaded)."""
    if not uv:
        say(False, "headless browser: uv not found (the tools section above should have installed it)")
        return False, False
    try:
        r = uv_python(uv, ["-c", BROWSER_PROBE], 600)
        if r.returncode == 0 and "browser ok" in r.stdout:
            say(True, "headless browser for carousels (already here)")
            return True, False
        if check:
            say(False, "headless browser: not downloaded yet (run without --check to add it)")
            return False, False
        print("   downloading the headless browser for carousels (about 200 MB, one time) ...", flush=True)
        r = uv_python(uv, ["-m", "playwright", "install", "chromium", "--only-shell"], 1500)
        if r.returncode != 0:
            tail = " ".join((r.stderr or r.stdout or "").strip().splitlines()[-2:])[:200]
            say(False, f"headless browser: the download failed, usually the network. Run this again. ({tail})")
            return False, False
        r = uv_python(uv, ["-c", BROWSER_PROBE], 600)
        if r.returncode == 0 and "browser ok" in r.stdout:
            say(True, "headless browser for carousels (just downloaded)")
            return True, True
        tail = " ".join((r.stderr or r.stdout or "").strip().splitlines()[-2:])[:200]
        say(False, f"headless browser: downloaded but it does not start here ({tail})")
        return False, False
    except (OSError, subprocess.TimeoutExpired) as e:
        say(False, f"headless browser: did not finish ({e.__class__.__name__}). Run this again.")
        return False, False


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    check = "--check" in argv
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    fok, fnew = ensure_ffmpeg(check)
    bok, bnew = ensure_browser(os.environ.get("PREP_UV") or shutil.which("uv"), check)
    if not (fok and bok):
        return 1
    return 3 if (fnew or bnew) else 0


if __name__ == "__main__":
    sys.exit(main())
