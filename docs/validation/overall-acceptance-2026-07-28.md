# Overall Acceptance Validation - 2026-07-28

Scope:
- `desktop/specs/installable-runtime-v1`
- `desktop/specs/multi-browser-adapter-v1`
- `desktop/specs/platform-auto-login-v1`

Environment:
- Workspace: `E:\YAOWU\yangHao\account-matrix`
- OS/runtime: Windows 11, PowerShell
- Validation date: 2026-07-28, Asia/Shanghai

## Executive Result

Automated regression, bundled runtime smoke tests, installer artifact checks, provider diagnostics, and password redaction checks passed.

Full acceptance is conditional because the local BitBrowser API was not reachable during validation. Existing `config/accounts.yaml` compatibility was verified statically and through diagnostics, but a live "already logged-in BitBrowser account runs TikTok task" check could not be executed on this machine.

One build-process finding was also observed: `desktop-build.ps1` generated the NSIS installer, but the runtime rebuild pre-step reported `No module named PyInstaller` and the script still returned success. The produced package uses the already bundled runtime and passes runtime smoke checks, but the build script should fail fast when `runtime/build-runtime.ps1` fails.

## Regression Commands

| Area | Command | Result |
| --- | --- | --- |
| Python integration | `py -3.13 tests/m14_python_integration.py` from `desktop` | PASS, `M14 python integration checks passed` |
| Frontend typecheck | `.\node_modules\.bin\tsc.cmd --noEmit` from `desktop` | PASS |
| Frontend M14 checks | `node tests/m14_frontend_checks.cjs` from `desktop` | PASS, `M14 frontend checks passed` |
| M15 acceptance | `node tests/m15_acceptance_checks.cjs` from `desktop` | PASS, `M15 acceptance checks passed` |
| M20 acceptance | `py -3.13 tests/m20_acceptance.py` from `desktop` | PASS; BitBrowser socket probe reported local API unavailable as expected diagnostic warning |
| Python syntax compile | `py -3.13 -B -c "... compile src/**/*.py ..."` | PASS, 41 Python files compiled |
| Rust/Tauri tests | `cargo +stable test --target-dir E:\YAOWU\yangHao\account-matrix\codex-cargo-target` from `desktop/src-tauri` | PASS, 30 passed, 0 failed; 4 dead-code warnings |
| Frontend production build | `.\node_modules\.bin\vite.cmd build` from `desktop` | PASS; large chunk warning only |
| Desktop package build | `.\desktop-build.ps1` from repo root | NSIS package generated; runtime rebuild pre-step reported missing PyInstaller, see finding below |

## Installable Runtime Validation

Artifacts verified:
- `desktop/src-tauri/target/release/bundle/nsis/Account Matrix_0.1.0_x64-setup.exe`, 18,728,781 bytes.
- `desktop/src-tauri/target/release/resources/runtime/account-matrix-runtime.exe`, 7,460,812 bytes.
- `desktop/src-tauri/resources/runtime/account-matrix-runtime.exe`, 7,460,812 bytes.
- `desktop/.m9-install-test/AccountMatrix3/resources/runtime/account-matrix-runtime.exe`, 7,460,812 bytes.

Manifest:
- `runtimeVersion`: `0.1.0`
- `schemaVersion`: `1`
- `supportedCommands`: `run`, `scheduler`, `gmail`, `diagnostic`, `version`
- Bundled runtime contains `_internal/python313.dll`, so the runtime carries Python with the package.

No-system-Python smoke:
- Command: run `desktop/.m9-install-test/AccountMatrix3/resources/runtime/account-matrix-runtime.exe version --json` with `PATH=C:\Windows\System32;C:\Windows` and without `PYTHONHOME`/`PYTHONPATH`.
- Result: PASS. The installed-style runtime returned version JSON without using system Python or source checkout imports.

Template diagnostic:
- Command: bundled runtime `diagnostic --config desktop/src-tauri/resources/templates/config/accounts.yaml --data-dir desktop/tests --json`.
- Result: PASS, status `ok`.

Build-process finding:
- `runtime/build-runtime.ps1` correctly has `$ErrorActionPreference = "Stop"` and throws on PyInstaller failure.
- `desktop-build.ps1` invokes it through a nested `powershell -File ...`; during this validation that nested command printed `No module named PyInstaller`, then `corepack pnpm tauri build --bundles nsis` still ran and the top-level script exited `0`.
- Recommended fix before release signing: make `desktop-build.ps1` check `$LASTEXITCODE` after the nested PowerShell call, or invoke it in a way that propagates the thrown failure.

## Multi-Browser Adapter Validation

Provider capability matrix was present in runtime diagnostic output:

| Provider | Implemented | Production ready | Launch | Close | CDP endpoint | TikTok | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `bitbrowser` | yes | yes | yes | yes | yes | yes | stable |
| `builtin_chromium` | yes | no | yes | yes | yes | yes | experimental |

Production default:
- Runtime diagnostic for real `config/accounts.yaml` reported 25 accounts total, 25 enabled.
- Static compatibility check reported 25/25 accounts have no new `browser_provider` or `login` fields, 25/25 still resolve effectively to `bitbrowser`, and 25/25 have `bitbrowser_profile_id`.
- This verifies old `accounts.yaml` remains backward compatible and TikTok production default remains BitBrowser.

Live BitBrowser check:
- Probe: `Invoke-WebRequest http://127.0.0.1:54345/health -TimeoutSec 5`.
- Result: BLOCKED by environment, `无法连接到远程服务器`.
- Runtime diagnostic for all 25 real accounts completed with status `warning`, with each account browser detail still `bitbrowser`.
- No productive TikTok actions were executed because BitBrowser Local API was unavailable.

## Platform Auto Login Validation

Configuration and credential handling:
- Rust tests passed:
  - `account_payload_serializes_login_metadata_without_plaintext_password`
  - `validation_rejects_enabled_login_without_required_fields`
  - `redacts_explicit_secret_values`
  - `redacts_multiline_text`
  - `redacts_sensitive_key_value_tokens`
- Real `config/accounts.yaml` remains legacy-compatible and does not require `login` fields.

Password non-disclosure checks:
- Scanned `config`, `config/backups`, `desktop/.m9-appdata/Roaming/Account Matrix/config/backups`, `data`, `desktop/src-tauri/resources/templates/config`, and `desktop/tests` for:
  - `AM_LOGIN_PASSWORD`
  - `login_password`
  - `loginPassword`
  - `password:`
  - `credential_secret`
  - validation test token
- Result: PASS, no matches.

Runtime log redaction smoke:
- Set `AM_LOGIN_PASSWORD` to a synthetic validation token and wrote a session log message containing that token.
- Result: PASS. The written line was `secret *** marker`; the plaintext token did not appear.
- Cleanup note: Windows denied deletion of `desktop/tests/validation-redaction-smoke.log`. The file is 50 bytes and contains only the masked line.

Command-line check:
- A read-only process command-line scan was run with patterns constructed at runtime to avoid self-matching.
- Result: PASS, no process command line contained the login password environment variable name or synthetic validation token.

## Acceptance Checklist

| Requirement | Status | Evidence |
| --- | --- | --- |
| Run full regression | PASS | Python, Node, Rust, Vite, M14/M15/M20 checks passed |
| Old `accounts.yaml` needs no new fields | PASS | 25/25 real accounts lack new fields and still resolve to BitBrowser |
| Existing BitBrowser logged-in account runs old logic | BLOCKED | BitBrowser Local API on `127.0.0.1:54345` was unavailable; no live TikTok run performed |
| TikTok production default remains BitBrowser | PASS | Diagnostics and static config resolution show 25/25 effective BitBrowser |
| Install package does not depend on source/system Python | PASS | Installed-style runtime launched with Python removed from `PATH`; bundled `_internal/python313.dll` present |
| Password not in config | PASS | No sensitive-field matches |
| Password not in backups | PASS | No sensitive-field matches in real and install-test backup dirs |
| Password not in command line | PASS | Runtime process scan had no matches |
| Password not in logs | PASS | Data/log scan no matches; redaction smoke wrote only `***` |
| UI marks builtin Chromium experimental | PASS by prior implementation/tests | M20 acceptance and frontend checks passed |
| Browser environments limited to BitBrowser and builtin Chromium | PASS by follow-up scope | Third provider is no longer part of the target browser matrix |

## Final Decision

Automated and package-level validation passed. Do not sign this as a complete production acceptance until:

1. BitBrowser Local API is running and at least one already logged-in legacy BitBrowser TikTok account completes a non-destructive or explicitly approved production task path.
2. `desktop-build.ps1` is fixed to fail when `runtime/build-runtime.ps1` fails, then the package build is rerun from a clean environment with PyInstaller available.
