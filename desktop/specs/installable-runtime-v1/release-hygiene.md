# Release Hygiene

Repository-level files under `config/` are development fixtures only. Production
installers must initialize user configuration from sanitized templates under
`desktop/src-tauri/resources/templates/config/`.

Release artifacts must not include runtime data, local backups, cache folders,
test output, or customer-specific files. Keep `data/`, `config/backups/`,
`__pycache__/`, `.m20-tmp/`, generated SQLite files, and private account/proxy
files out of packaged outputs.
