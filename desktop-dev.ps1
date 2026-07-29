$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = Join-Path $root "desktop"
$rustRoot = "D:\DesktopAPPs\Rust"

$env:RUSTUP_HOME = Join-Path $rustRoot ".rustup"
$env:CARGO_HOME = Join-Path $rustRoot ".cargo"
$env:PATH = (Join-Path $env:CARGO_HOME "bin") + ";" + $env:PATH

Set-Location $desktop
corepack pnpm tauri dev
