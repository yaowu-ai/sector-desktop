# Installable Runtime V1 Validation

Date: 2026-07-27
Host: Windows 11, local clean-directory validation under this workspace
Version: 0.1.0

## Artifacts

- Runtime build command:
  `powershell -ExecutionPolicy Bypass -File .\desktop-build.ps1 -Python ".\.runtime-build-venv\Scripts\python.exe"`
- Runtime resource output:
  `desktop/src-tauri/resources/runtime/account-matrix-runtime.exe`
- Runtime manifest:
  `desktop/src-tauri/resources/runtime/runtime-manifest.json`
- Installer build command:
  `$env:RUSTUP_TOOLCHAIN='stable'; corepack pnpm tauri build --bundles nsis`
- NSIS installer:
  `desktop/src-tauri/target/release/bundle/nsis/Account Matrix_0.1.0_x64-setup.exe`
- Installer size:
  `18,657,443` bytes

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| NSIS installer contains bundled runtime | Pass | Silent install to `desktop/.m9-install-test/AccountMatrix3`; installed `resources/runtime/account-matrix-runtime.exe`, `runtime-manifest.json`, and recursive `_internal/python313.dll`. |
| Runtime does not require system Python | Pass | With `PATH=C:\Windows\System32;C:\Windows`, installed runtime returned `version --json` successfully. |
| Runtime diagnostic works from clean install dir | Pass | With stripped PATH and installed template config, `diagnostic --json` returned `status: ok` after creating `desktop/.m9-install-test/RuntimeData2`. |
| App starts without source repo path | Pass | Installed `account-matrix-desktop.exe` was launched from `desktop/.m9-install-test` with isolated `APPDATA`/`LOCALAPPDATA`; no `ACCOUNT_MATRIX_ROOT` was set. |
| First launch creates user config | Pass | Created `desktop/.m9-appdata/Roaming/Account Matrix/config/accounts.yaml`, `comments.txt`, `comments_brand.txt`, and `settings/local-settings.json`. |
| First launch creates user data/log dirs | Pass | Created `desktop/.m9-appdata/Local/Account Matrix/data/` and `logs/`. |
| Production defaults bundled | Pass | Generated `local-settings.json` contains `"runtimeMode": "bundled"` and `"projectRoot": null`. |
| Passwords/user data stay out of install dir | Pass | No `actions.db`, `sessions.log`, `run.lock`, or `local-settings.json` were found under `desktop/.m9-install-test/AccountMatrix2`; the same packaging layout was rebuilt and reinstalled to `AccountMatrix3`. |
| BitBrowser stopped state is detectable | Pass | `Test-NetConnection 127.0.0.1:54345` returned `False` earlier in the run; existing desktop diagnostics report this API state as unavailable. Later M20 also observed the API reachable after BitBrowser became available. |
| BitBrowser running preflight | Partial | Installed bundled runtime reached `BitBrowserClient.open_browser(...)` via `diagnostic --kind comment --no-post`, but BitBrowser returned `权限不足，无法执行此操作！`, so browser preview was not reached on this host. |
| SQLite task-write path | Not verified | Avoided running a real account task from installer validation because it can mutate live BitBrowser/TikTok state. Existing desktop M20 smoke verifies SQLite read/query behavior with temp data. |
| Upgrade preserves user config | Pass | Added `# preserve-check: m9` to isolated `accounts.yaml`, reran silent installer over the same install dir, relaunched app, marker remained. |
| Uninstall keeps user data | Pass | Ran installed `uninstall.exe /S`; install exe was removed while isolated `accounts.yaml` and the marker remained. |

## Commands Run

```powershell
.\.runtime-build-venv\Scripts\python.exe -m pip install -r requirements.txt PyInstaller
powershell -ExecutionPolicy Bypass -File .\desktop-build.ps1 -Python ".\.runtime-build-venv\Scripts\python.exe"
desktop\src-tauri\resources\runtime\account-matrix-runtime.exe version --json
desktop\src-tauri\resources\runtime\account-matrix-runtime.exe diagnostic --json --config desktop\src-tauri\resources\templates\config\accounts.yaml --data-dir runtime\dist-smoke-data
$env:RUSTUP_TOOLCHAIN='stable'; corepack pnpm tauri build --bundles nsis
desktop\src-tauri\target\release\bundle\nsis\Account Matrix_0.1.0_x64-setup.exe /S /D=...\desktop\.m9-install-test\AccountMatrix3
...\AccountMatrix3\resources\runtime\account-matrix-runtime.exe diagnostic --kind comment --account tiktok_1 --no-post --max-scroll 1 --min 999999999 --config ...\config\accounts.yaml
```

## Notes

- The first installer attempt exposed a packaging defect: `resources/runtime/*` only included top-level runtime files and omitted `_internal`. The resource glob was changed to `resources/runtime/**/*`, and the rebuilt installer passed the stripped-PATH runtime checks.
- The first interactive diagnostic attempt exposed a PyInstaller hidden-import gap for `test_comment`. The runtime spec now collects local top-level diagnostic modules plus `core` and `platforms` submodules.
- This validation was performed in clean directories on the current Windows host, not in a separate clean VM. A separate clean VM pass is still recommended before external distribution.
- `corepack pnpm tauri build --bundles nsis` produced the expected Vite chunk-size warning; it did not block the build.
