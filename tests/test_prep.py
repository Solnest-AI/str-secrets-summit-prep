"""Offline tests for the summit prep (no network). Run: python3 -m unittest discover -s tests -v"""
import gzip
import io
import pathlib
import re
import subprocess
import os
import sys
import tarfile
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import prep  # noqa: E402


class Sources(unittest.TestCase):
    def test_every_summit_platform_has_two_or_more_mirrors(self):
        for key in (("Windows", "x64"), ("Windows", "arm64"), ("Darwin", "arm64"), ("Darwin", "x64")):
            self.assertGreaterEqual(len(prep.SOURCES[key]), 2, key)

    def test_ffmpeg_goes_where_uv_lives(self):
        self.assertEqual(prep.DEST, pathlib.Path.home() / ".local" / "bin")
        self.assertIn(prep.DEST / f"ffmpeg{prep.EXE}", list(prep.candidates("ffmpeg")))

    def test_playwright_pin_matches_the_content_studio(self):
        self.assertEqual(prep.PLAYWRIGHT, "playwright==1.60.0")


class Harvest(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())

    def test_zip(self):
        z = self.d / "a.zip"
        with zipfile.ZipFile(z, "w") as f:
            f.writestr(f"ffmpeg-7/bin/ffmpeg{prep.EXE}", b"x")
            f.writestr(f"ffmpeg-7/bin/ffprobe{prep.EXE}", b"y")
            f.writestr("ffmpeg-7/doc/readme.txt", b"z")
        self.assertEqual(sorted(prep.harvest(z, self.d / "out")), ["ffmpeg", "ffprobe"])
        self.assertFalse((self.d / "out" / "readme.txt").exists())

    def test_single_gzipped_binary(self):
        g = self.d / "ffprobe.gz"
        with gzip.open(g, "wb") as f:
            f.write(b"bin")
        self.assertEqual(prep.harvest(g, self.d / "out", gz_name="ffprobe"), ["ffprobe"])
        self.assertEqual((self.d / "out" / f"ffprobe{prep.EXE}").read_bytes(), b"bin")

    def test_tar(self):
        t = self.d / "a.tar.gz"
        with tarfile.open(t, "w:gz") as f:
            for n in ("ffmpeg", "ffprobe"):
                data = b"b"
                info = tarfile.TarInfo(f"x/bin/{n}{prep.EXE}")
                info.size = len(data)
                f.addfile(info, io.BytesIO(data))
        self.assertEqual(sorted(prep.harvest(t, self.d / "out")), ["ffmpeg", "ffprobe"])

    def test_not_an_archive(self):
        (self.d / "page.html").write_text("<html>")
        with self.assertRaises(prep.PrepError):
            prep.harvest(self.d / "page.html", self.d / "out")


class ExitCodes(unittest.TestCase):
    def run_main(self, f, b, argv=()):
        with mock.patch.object(prep, "ensure_ffmpeg", return_value=f), \
                mock.patch.object(prep, "ensure_browser", return_value=b), redirect_stdout(io.StringIO()):
            return prep.main(list(argv))

    def test_all_present(self):
        self.assertEqual(self.run_main((True, False), (True, False)), 0)

    def test_something_downloaded_asks_for_one_restart(self):
        self.assertEqual(self.run_main((True, True), (True, False)), 3)

    def test_any_failure_is_not_ready(self):
        self.assertEqual(self.run_main((False, False), (True, True)), 1)

    def test_every_download_failing_says_so_and_leaves_nothing_behind(self):
        d = pathlib.Path(tempfile.mkdtemp())
        with mock.patch.object(prep, "DEST", d), mock.patch.object(prep, "find_working", return_value=None), \
                mock.patch.object(prep, "download", side_effect=OSError("offline")), redirect_stdout(io.StringIO()) as out:
            ok, new = prep.ensure_ffmpeg()
        self.assertEqual((ok, new), (False, False))
        self.assertIn("every download failed", out.getvalue())
        self.assertFalse((d / "_ffmpeg_download").exists())

    def test_check_mode_downloads_nothing(self):
        with mock.patch.object(prep, "find_working", return_value=None), \
                mock.patch.object(prep, "download") as dl, redirect_stdout(io.StringIO()):
            self.assertEqual(prep.ensure_ffmpeg(check=True), (False, False))
        dl.assert_not_called()


class WindowsConsole(unittest.TestCase):
    def test_a_cp1252_console_never_crashes_on_the_check_mark(self):
        # Windows, stdout piped by Claude's Bash tool, prep.py run directly: cp1252 (2026-09-28).
        raw = io.BytesIO()
        cp1252 = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
        with mock.patch.object(sys, "stdout", cp1252):
            prep.say(True, "ffmpeg 8.1")
            prep.say(False, "headless browser")
            cp1252.flush()
        out = raw.getvalue().decode("cp1252")
        self.assertIn("[ok] ffmpeg 8.1", out)
        self.assertIn("[!!] headless browser", out)


class Script(unittest.TestCase):
    def test_prep_sh_parses_and_points_nowhere_it_cannot_reach(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(ROOT / "prep.sh")]).returncode, 0)
        text = (ROOT / "prep.sh").read_text(encoding="utf-8")
        self.assertNotIn("connectors/", text)   # the kit's files are not in this repo
        self.assertNotIn("\r\n", text)
        for last in ("ALL SET. Nothing else", "ALL SET, RESTART ONCE", "NOT READY"):
            self.assertIn(last, text)

    def test_readme_command_and_final_lines_match_the_script(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('git -C "$D" remote add origin https://github.com/Solnest-AI/str-secrets-summit-prep', readme)
        self.assertIn('git -C "$D" fetch -q --depth 1 origin main', readme)
        self.assertIn("bash ~/str-secrets-summit-prep/prep.sh", readme)
        self.assertNotIn("| bash", readme)      # auto mode blocks download-and-run pipes
        self.assertIn("Ask permissions", readme)
        for last in ("`ALL SET.`", "`ALL SET, RESTART ONCE`", "`NOT READY`"):
            self.assertIn(last, readme)
        self.assertNotIn("—", readme)
        self.assertEqual(re.findall(r"\$\d", readme), [])



def run_git_block(git_stub, win=0, check=0):
    """Run prep.sh's Git block alone, with `git` and `xcode-select` replaced by stubs, so no test
    installs anything. Returns (printed lines, BROKEN, whether xcode-select was called)."""
    text = (ROOT / "prep.sh").read_text(encoding="utf-8")
    block = text[text.index("# ---------------------------------------------------------------- git --"):
                 text.index("# --------------------------------------------------------------- node --")]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "git").write_text("#!/bin/sh\n" + git_stub + "\n", encoding="utf-8")
        (tmp / "xcode-select").write_text("#!/bin/sh\ntouch \"$(dirname \"$0\")/xcode-select-called\"\n", encoding="utf-8")
        for f in ("git", "xcode-select"):
            (tmp / f).chmod(0o755)
        script = ("ok() { printf 'OK %s\\n' \"$1\"; }\nbad() { printf 'BAD %s\\n' \"$1\"; BROKEN=1; }\n"
                  "warn() { printf 'WARN %s\\n' \"$1\"; }\nBROKEN=0\n" + block + "\necho \"BROKEN=$BROKEN\"\n")
        env = dict(os.environ, PATH=f"{tmp}:/usr/bin:/bin", WIN=str(win), CHECK=str(check))
        out = subprocess.run(["bash", "-c", f"WIN={win}; CHECK={check}; " + script], env=env,
                             capture_output=True, text=True).stdout
        return out, "BROKEN=1" in out, (tmp / "xcode-select-called").exists()


APPLE_STUB = 'echo "xcrun: error: invalid active developer path (/Library/Developer/CommandLineTools)" >&2; exit 1'


class GitCheck(unittest.TestCase):
    def test_a_working_git_passes_with_its_version(self):
        out, broken, opened = run_git_block('echo "git version 2.50.1"')
        self.assertIn("OK Git 2.50.1", out)
        self.assertFalse(broken)
        self.assertFalse(opened)

    def test_apples_stub_on_a_mac_warns_and_opens_the_installer(self):
        out, broken, opened = run_git_block(APPLE_STUB)
        self.assertNotIn("OK Git", out)         # the 2026-09-28 false pass
        self.assertIn("WARN Git: Apple's command line tools are missing", out)
        self.assertFalse(broken)                # a Mac does not need Git once the scripts are here
        self.assertTrue(opened)

    def test_check_mode_never_opens_the_installer(self):
        out, broken, opened = run_git_block(APPLE_STUB, check=1)
        self.assertIn("WARN Git", out)
        self.assertFalse(opened)

    def test_windows_with_no_git_still_stops(self):
        out, broken, opened = run_git_block("exit 127", win=1)
        self.assertIn("BAD Git: not found", out)
        self.assertTrue(broken)
        self.assertFalse(opened)

    def test_readme_gets_the_scripts_without_git_on_a_mac(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("invalid active developer path", readme)
        self.assertIn('curl -fsSL -o "$D.tar.gz" https://github.com/Solnest-AI/str-secrets-summit-prep/archive/refs/heads/main.tar.gz', readme)
        self.assertIn('tar -xzf "$D.tar.gz" -C "$D" --strip-components 1', readme)
        self.assertNotIn("| tar", readme)       # a download piped into anything is what auto mode blocks

    def test_winget_names_its_source_and_says_why_it_failed(self):
        text = (ROOT / "prep.sh").read_text(encoding="utf-8")
        self.assertIn("winget install --id OpenJS.NodeJS.LTS -e --source winget", text)
        self.assertIn("winget said:", text)


if __name__ == "__main__":
    unittest.main()
