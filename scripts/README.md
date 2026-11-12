# PowerShell startup

Double-click `scripts/start.cmd`, or right-click `scripts/start.ps1` and choose **Run with PowerShell**. The command wrapper only launches this script; it changes the execution policy for that PowerShell process, not the machine's settings. No executable or command wrapper is placed in the repository root.

The script supports Windows 10/11 x64 and needs internet access for the first setup. It installs the pinned official Astral uv release from `uv.json`, verifies the archive's size and SHA-256, and checks extraction paths. The uv binary, managed Python 3.12, uv cache and Chromium stay under `.runtimes`. Locked application dependencies go into `.venv`; no Python, uv or developer compiler installation is required beforehand.

Chromium is prepared with `python -m src.runtime --ensure`, so a verified browser is reused instead of downloaded on every start. After import validation, the script launches the scanner with `pythonw.exe`. Errors remain visible when launched through the command wrapper; a transcript is saved in `data/startup.log`.

For preparation-only diagnostics, run `scripts/start.ps1 -PrepareOnly`. It performs the same setup but does not open the application. A successful run exits with code zero.

Existing `data` and browser profiles are retained. The startup script does not clear saved credentials. Keep the whole repository together so its relative paths continue to work.

Validation: in an isolated directory with Chinese characters and spaces, without `.venv` or `.runtimes`, Windows PowerShell 5.1 downloaded uv, managed Python, dependencies and Chromium successfully. A repeated `-PrepareOnly` run returned code zero in approximately 1.2 seconds and reused the installed files.
