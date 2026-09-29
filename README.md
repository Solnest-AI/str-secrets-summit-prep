# STR Secrets Summit prep (the night before)

The one thing to do before Tuesday morning. Paste this repo's link into the Claude Code
desktop app and say **set this up**. It takes about 5 minutes on your home wifi and gets
your computer ready for Day 1: it checks every tool the summit runs on, installs any that
are missing, downloads **ffmpeg** (the video tool), and downloads the browser the Content
Studio uses for carousels.

**When Claude asks permission to run a command, click Allow.** If Claude says auto mode
blocked it, switch the mode picker next to the message box to **Ask permissions** and say
**set this up** again.

It does **not** install the Revenue Manager or the Content Studio. We set those up together
in the sessions on Tuesday, one link each, step by step. Please don't install them before
Tuesday morning.

Free from **Solnest AI**.

---

## Claude: someone pasted this link and said "set this up"

Do exactly this. You run every command yourself with your Bash tool; the person never opens
a terminal and never types a command. Nothing here needs an API key.

1. Tell them in one line: "Getting your computer ready for the summit: about 5 minutes,
   nothing for you to do."
2. Get the scripts, read them, then run them. Three separate steps, never one piped
   command. It is the same on Mac and on Windows (your Bash tool there is Git Bash).

   a. Clone the repo (or update it if it is already there):

      ```bash
      if [ -d ~/str-secrets-summit-prep/.git ]; then git -C ~/str-secrets-summit-prep pull --ff-only; else git clone --depth 1 https://github.com/Solnest-AI/str-secrets-summit-prep ~/str-secrets-summit-prep; fi
      ```

   b. Read `~/str-secrets-summit-prep/prep.sh` and `~/str-secrets-summit-prep/prep.py` in
      full before running anything. They install only to `~/.local/bin` and uv's Python
      folder, need no admin password, and read or write no keys.

   c. Run it, with a 20 minute tool timeout (the first run downloads about 300 MB):

      ```bash
      bash ~/str-secrets-summit-prep/prep.sh
      ```

   (Windows with no Bash tool at all: Git for Windows is missing. Tell them to install it
   from git-scm.com with every default, quit and reopen Claude Code, and say "set this up"
   again.)

   **If a command is blocked** (auto mode's safety check, or a permission denial): do not
   try to work around it with a different command or tool. Tell them: "Your Claude Code is
   in auto mode, which blocked the installer. Click the mode picker next to the message box,
   switch it to **Ask permissions**, then say **set this up** again and click **Allow** when
   I ask to run a command." If they are already in Ask permissions mode, just tell them to
   click **Allow** on the prompt.
3. Show them the lines it printed, then read the last line:
   - **`ALL SET.`** Say: "✅ **You're ready for the summit.** ffmpeg and every tool the
     summit needs are installed. Nothing else to install before Tuesday morning: we set up
     the Revenue Manager and the Content Studio together in the sessions."
   - **`ALL SET, RESTART ONCE`**: say the same ✅ line, then: "One last thing: fully quit
     Claude Code once so it sees the new tools. On Mac press Cmd+Q. On Windows close every
     Claude Code window, and if a Claude icon is still in the system tray (bottom right, near
     the clock), right-click it and quit."
   - **`NOT READY`**: a line starts with ❌ and says what to do. Do that one thing (or tell
     them the one thing they have to do, such as clicking Yes on a Windows prompt), then run
     step 2c again. It skips everything already done.
4. If they ask to install the Revenue Manager or the Content Studio now, tell them those are
   set up together in the sessions on Tuesday, so everyone does them the same way at the
   same time.

Running it again any time is safe: it only installs what is missing.

---

## What it installs, and where

| Item | Why | Where |
|---|---|---|
| Git | Claude Code uses it (Windows: it is the Bash tool) | checked only; the connections kit installed it |
| Node.js 20+ | runs the tool connections | winget (Windows) or Homebrew (Mac), if missing |
| uv | runs every Python step, no admin | `~/.local/bin` |
| Python 3.13 | the summit scripts | through uv; on Windows under `%USERPROFILE%\.uv\python` |
| ffmpeg + ffprobe | the Content Studio's videos | reused if you have it, else downloaded to `~/.local/bin` |
| Headless browser | the Content Studio's carousels | Playwright's Chromium shell, about 200 MB |

No admin password (Windows may show one permission prompt for Node.js: click Yes), nothing
added to the system beyond these, no keys read or written.

## For developers

```bash
python3 -m unittest discover -s tests -v    # offline, no network
bash prep.sh --check                        # report only, install nothing
```

The tool checks in `prep.sh` are the STR Secrets connections kit's `install-tools.sh`; the
ffmpeg download in `prep.py` is the Content Studio's, with the same mirrors.
