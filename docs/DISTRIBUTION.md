# Building and releasing Lisa2

## Run a clone without a release download

Install Python 3.12, clone this repository, then double-click `Lisa2.bat` on
Windows or run `bash Lisa2.sh` on Linux. The launchers create a local `.venv`,
install/check the exact runtime dependency versions and open Studio. They reuse
the environment on subsequent launches and do not install build tools.
`Lisa2.cmd` is an alias for the Windows launcher. Python itself is a prerequisite
for this source workflow; it is bundled only in release downloads.

On Linux, Python needs its matching Tk and venv packages (for a distribution
providing Python 3.12, commonly `python3.12-tk` and `python3.12-venv`). System
packages are not installed with sudo automatically. First setup needs internet;
subsequent runs need it only if the pinned dependencies change. Setup failures
stop before opening Studio and leave the environment available for retry.
If several Python installations coexist, `LISA2_PYTHON` can select a specific
Python 3.12 executable for creating a new environment.

For CI or setup without opening Studio use `Lisa2.bat --prepare-only` or
`bash Lisa2.sh --prepare-only`. Other arguments pass through to the application.

Every push to **master** builds the Windows x86-64 and Linux x86-64 application
on native GitHub-hosted runners. Pull requests build and test without publishing.
The workflow can also be run manually for master. A failed build or installed-app
test prevents publication of the entire release.

## What users download

- `Lisa2-Windows-Setup.exe`: per-user installer, Start-menu shortcut and uninstaller;
  no administrator rights are requested. Windows 10/11 x86-64 is the target.
- `Lisa2-Windows-Portable.zip`: extract and run `Lisa2/Lisa2.exe`.
- `Lisa2-Linux-x86_64.tar.gz`: extract and run `./Lisa2/start.sh`.
- `SHA256SUMS.txt`: hashes for all three packages.

Python, Tk, NumPy, SciPy, Numba, the LLVM backend and pygame are bundled. The
Linux launcher does not download packages, invoke pip, create a venv or require
root. Linux targets a glibc/X11-compatible desktop with an Ubuntu 22.04 baseline;
it is not a static binary for every distribution or architecture. On Wayland,
the desktop needs its usual XWayland support for Tk. The current native file-drop
bridge is Windows-only; Linux users click the four image slots instead.

The first evolution run compiles CPU kernels and can start more slowly than
later runs. Closing or stopping still follows the normal checkpoint rules.

## State lives outside the application

Installed/frozen builds keep diagnostic logs and the Numba cache in:

- Windows: `%LOCALAPPDATA%/Lisa2/`
- Linux: `$XDG_DATA_HOME/Lisa2/`, or `~/.local/share/Lisa2/`

Projects remain wherever the user saves them. Keep each project JSON together
with its companion data folder. The install directory can be read-only; updates
and uninstallation do not remove user projects. Portable here means a relocatable
application folder; cache/log state still uses the user's data directory. Set
`LISA2_DATA_DIR` to override that location. Source checkouts use `runs/runtime/`.

## The automatic pipeline

1. Install pinned Python and build dependencies on Windows and Ubuntu runners.
2. Run numerical/project checks.
3. Build a PyInstaller one-directory application and portable archive.
4. Run the packaged app's end-to-end release check. It initializes a tiny project,
   starts a bounded worker subprocess, resumes through Studio, runs a global RGB
   fit, checks history, renders four views and exports OBJ/GIF. The real preview
   subprocess uses SDL's dummy driver; Tk windows remain withdrawn.
5. Extract the Linux archive and test its launcher under Xvfb. Build the Windows
   installer with the signed, pinned Inno Setup compiler, silently install to a
   temporary directory and repeat the application check from that installation.
6. Run the same Linux archive on Ubuntu 24.04 without installing Python packages.
7. Only after all jobs pass, create a release targeting the exact source commit,
   upload all packages and hashes, and mark it latest.

Release tags are `build-<full commit SHA>`. Rerunning an already released commit
does not overwrite its assets. Release publication uses the repository's
short-lived `GITHUB_TOKEN` with `contents: write`; no personal token, signing
secret, manual tag push or separate package registry is required. Build jobs
have read-only repository permissions. Workflow diagnostics are Actions artifacts,
not extra public release downloads. Installed application tests do not publish
the temporary projects or their runtime timestamps.

## GitHub setup

Create an **empty repository**, then push master. Default settings on a personal
repository normally suffice. If account/organization policies disable Actions,
GitHub-hosted runners, or write-capable workflow tokens, the owner must allow
those capabilities. The workflow explicitly requests its own release permission.
No repository secrets or environment approvals are configured by this project.

The Windows application/installer is **unsigned**. Windows may display its
normal unknown-publisher/SmartScreen prompt. Signing is an optional later step
that requires a signing identity; it is not necessary for building releases.
GitHub itself records commit, workflow and release times. The project removes
historical experiment dates from source documents, not GitHub's service metadata.

## Build locally

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt -r requirements-build.txt
.venv\Scripts\python.exe packaging/build.py
$compiler = ./packaging/install-inno.ps1
& $compiler packaging/windows.iss
```

On Linux use the analogous `python` commands for dependencies and `build.py`;
there is no Inno Setup step. Artifacts go to ignored `dist/`, `build/` and
`release/` directories. Build on the target OS; PyInstaller does not cross-compile.

To run the installed-app check, set `LISA2_DATA_DIR` to a writable temporary
directory and execute:

```text
Lisa2 --smoke-test --report /absolute/path/to/report.json
```

On Windows call `Lisa2.exe` and wait for its exit code; it is a GUI executable.
On Linux use Xvfb for headless CI. A successful run writes `status: passed` to
the report and exits zero; failures are recorded in the report and user-data log.
