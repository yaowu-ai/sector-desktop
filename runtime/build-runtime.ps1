param(
  [string]$Python = "py -3.13",
  [string]$DistDir = "runtime/dist",
  [string]$WorkDir = "build",
  [switch]$CopyToTauriResources
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$spec = Join-Path $repo "runtime/pyinstaller/account-matrix-runtime.spec"
$dist = Join-Path $repo $DistDir
$work = Join-Path $repo $WorkDir

Push-Location $repo
try {
  $pythonParts = $Python -split " "
  $pythonExe = $pythonParts[0]
  $pythonArgs = @()
  if ($pythonParts.Length -gt 1) {
    $pythonArgs = $pythonParts[1..($pythonParts.Length - 1)]
  }
  & $pythonExe @pythonArgs -m PyInstaller --clean --noconfirm --distpath $dist --workpath $work $spec
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
  }

  $runtimeDir = Join-Path $dist "account-matrix-runtime"
  & $pythonExe @pythonArgs runtime/runtime_manifest.py --runtime-dir $runtimeDir
  if ($LASTEXITCODE -ne 0) {
    throw "runtime manifest generation failed with exit code $LASTEXITCODE"
  }

  if ($CopyToTauriResources) {
    $target = Join-Path $repo "desktop/src-tauri/resources/runtime"
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Copy-Item -Path (Join-Path $runtimeDir "*") -Destination $target -Recurse -Force
  }
} finally {
  Pop-Location
}
