<#
.SYNOPSIS
Builds a standalone Windows executable for the Trade Automation tool.

.DESCRIPTION
Runs PyInstaller against Auto.py, placing the resulting executable under dist/.
Copies config.json and the templates/ directory (if present) next to the exe so
the bundled defaults keep working out of the box.

.EXAMPLE
./build_exe.ps1
#>

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSCommandPath
$exeName = "TradeAutomation"
$distDir = Join-Path $projectRoot "dist"
$buildDir = Join-Path $projectRoot "build"
$specPath = Join-Path $projectRoot "$exeName.spec"

Write-Host "Building $exeName executable..." -ForegroundColor Cyan

$pyInstallerArgs = @(
    "--clean",
    "--name", $exeName,
    "--onefile",
    "--noconfirm",
    "--add-data", "config.json;."
)

# Include templates if the folder exists so bundled config works immediately.
if (Test-Path (Join-Path $projectRoot "templates")) {
    $pyInstallerArgs += @("--add-data", "templates;templates")
}

Push-Location $projectRoot
try {
    python -m PyInstaller @pyInstallerArgs Auto.py

    if (-not (Test-Path $distDir)) {
        throw "PyInstaller did not create the dist/ directory as expected."
    }

    if (Test-Path $specPath) {
        Remove-Item -LiteralPath $specPath -Force
    }

    if (Test-Path $buildDir) {
        Remove-Item -LiteralPath $buildDir -Recurse -Force
    }

    $targetConfig = Join-Path $distDir "config.json"
    Copy-Item -LiteralPath (Join-Path $projectRoot "config.json") -Destination $targetConfig -Force

    $templatesDir = Join-Path $projectRoot "templates"
    if (Test-Path $templatesDir) {
        Copy-Item -LiteralPath $templatesDir -Destination $distDir -Recurse -Force
    }

    Write-Host "Executable created at $(Join-Path $distDir "$exeName.exe")" -ForegroundColor Green
}
finally {
    Pop-Location
}
