param(
  [string]$Python = "py -3.13",
  [ValidateSet("test", "prod", "production")]
  [string]$BuildMode = "production"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = Join-Path $root "desktop"
$rustRoot = $env:ACCOUNT_MATRIX_RUST_ROOT
if ([string]::IsNullOrWhiteSpace($rustRoot)) {
  if (Test-Path "D:\DesktopAPPs\Rust") {
    $rustRoot = "D:\DesktopAPPs\Rust"
  }
  else {
    $rustRoot = $env:USERPROFILE
  }
}

$env:RUSTUP_HOME = Join-Path $rustRoot ".rustup"
$env:CARGO_HOME = Join-Path $rustRoot ".cargo"
$env:PATH = (Join-Path $env:CARGO_HOME "bin") + ";" + $env:PATH
$env:RUSTUP_TOOLCHAIN = "stable"

Set-Location $root
powershell -ExecutionPolicy Bypass -File runtime\build-runtime.ps1 -Python $Python -CopyToTauriResources
if ($LASTEXITCODE -ne 0) {
  throw "runtime build failed with exit code $LASTEXITCODE"
}
Set-Location $desktop
$env:DESKTOP_BUILD_MODE = if ($BuildMode -eq "prod") { "production" } else { $BuildMode }
corepack pnpm tauri build --bundles nsis
if ($LASTEXITCODE -ne 0) {
  throw "desktop package build failed with exit code $LASTEXITCODE"
}
