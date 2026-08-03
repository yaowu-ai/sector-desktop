$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = Join-Path $root "desktop"
$rustRoot = "D:\DesktopAPPs\Rust"
$runtimeBuildScript = Join-Path $root "runtime\build-runtime.ps1"
$runtimeResourceDir = Join-Path $desktop "src-tauri\resources\runtime"
$runtimeResourceExe = Join-Path $desktop "src-tauri\resources\runtime\account-matrix-runtime.exe"
$debugRuntimeDir = Join-Path $desktop "src-tauri\target\debug\resources\runtime"
$debugRuntimeExe = Join-Path $debugRuntimeDir "account-matrix-runtime.exe"
$runtimePythonExe = Join-Path $root ".runtime-build-venv\Scripts\python.exe"

$env:RUSTUP_HOME = Join-Path $rustRoot ".rustup"
$env:CARGO_HOME = Join-Path $rustRoot ".cargo"
$env:PATH = (Join-Path $env:CARGO_HOME "bin") + ";" + $env:PATH

$runtimeInputs = @(
  Get-ChildItem -Path (Join-Path $root "src") -Recurse -File -Filter "*.py"
  Get-ChildItem -Path (Join-Path $root "runtime\pyinstaller") -Recurse -File
  Get-Item -LiteralPath $runtimeBuildScript
  Get-Item -LiteralPath (Join-Path $root "runtime\runtime_manifest.py")
  Get-Item -LiteralPath (Join-Path $root "requirements.txt")
)
$latestRuntimeInput = $runtimeInputs |
  Sort-Object -Property LastWriteTimeUtc -Descending |
  Select-Object -First 1
$runtimeNeedsBuild = -not (Test-Path -LiteralPath $runtimeResourceExe)
if (-not $runtimeNeedsBuild -and $latestRuntimeInput) {
  $runtimeResource = Get-Item -LiteralPath $runtimeResourceExe
  $runtimeNeedsBuild = $latestRuntimeInput.LastWriteTimeUtc -gt $runtimeResource.LastWriteTimeUtc
}

if ($runtimeNeedsBuild) {
  $runtimePython = if (Test-Path -LiteralPath $runtimePythonExe) {
    $runtimePythonExe
  } else {
    "py -3.13"
  }
  Write-Host "Runtime sources changed; rebuilding bundled development runtime..."
  & $runtimeBuildScript -Python $runtimePython -CopyToTauriResources
  if ($LASTEXITCODE -ne 0) {
    throw "Runtime rebuild failed with exit code $LASTEXITCODE"
  }
}

$runtimeNeedsSync = -not (Test-Path -LiteralPath $debugRuntimeExe)
if (-not $runtimeNeedsSync) {
  $runtimeResource = Get-Item -LiteralPath $runtimeResourceExe
  $debugRuntime = Get-Item -LiteralPath $debugRuntimeExe
  $runtimeNeedsSync = $runtimeResource.LastWriteTimeUtc -gt $debugRuntime.LastWriteTimeUtc -or
    $runtimeResource.Length -ne $debugRuntime.Length
}

if ($runtimeNeedsSync) {
  Write-Host "Synchronizing bundled runtime into the Tauri debug resources..."
  New-Item -ItemType Directory -Force -Path $debugRuntimeDir | Out-Null
  Copy-Item -Path (Join-Path $runtimeResourceDir "*") -Destination $debugRuntimeDir -Recurse -Force
}

Set-Location $desktop
corepack pnpm tauri dev
