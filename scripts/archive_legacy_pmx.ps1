<#
.SYNOPSIS
    archive_legacy_pmx.ps1: Safe Archival Utility for Legacy portfolio_maximizer Codebase (PowerShell)
.DESCRIPTION
    Creates a compressed, cold-storage ZIP archive of the legacy trading codebase,
    excluding caches, virtual environments, and temporary directories, and computes
    its immutable SHA-256 cryptographic lineage hash.
#>
[CmdletBinding()]
param(
    [string]$LegacyPath = "../portfolio_maximizer_v45",
    [string]$DestinationDir = "./archive",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$ArchiveName = "legacy_pmx_cold_storage_${Timestamp}.zip"
$TargetPath = Join-Path $DestinationDir $ArchiveName

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "    LEGACY PMX COLD-STORAGE ARCHIVAL PROTOCOL (Phase 1 Transition)   " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Source Legacy Path : $LegacyPath"
Write-Host "Archive Target     : $TargetPath"

if (-not (Test-Path $LegacyPath)) {
    Write-Error "ERROR: Legacy directory '$LegacyPath' does not exist."
    exit 1
}

if ($DryRun) {
    Write-Host "[DRY-RUN] Directory verified. Skipping physical archive creation." -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $DestinationDir)) {
    New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null
}

$ResolvedSource = (Resolve-Path $LegacyPath).Path
$ExcludePatterns = @("__pycache__", ".pytest_cache", "venv", ".venv", "node_modules", ".hypothesis", ".git", ".tmp")

Write-Host "Creating compressed archive..." -ForegroundColor Gray
$TempStaging = Join-Path $env:TEMP "pmx_archive_staging_${Timestamp}"
New-Item -ItemType Directory -Path $TempStaging -Force | Out-Null

try {
    # Copy files excluding caches
    Get-ChildItem -Path $ResolvedSource -Recurse | Where-Object {
        $item = $_
        $relative = $item.FullName.Substring($ResolvedSource.Length)
        $shouldExclude = $false
        foreach ($pattern in $ExcludePatterns) {
            if ($relative -match [regex]::Escape($pattern)) {
                $shouldExclude = $true
                break
            }
        }
        -not $shouldExclude
    } | ForEach-Object {
        $targetItem = Join-Path $TempStaging $_.FullName.Substring($ResolvedSource.Length)
        if ($_.PSIsContainer) {
            if (-not (Test-Path $targetItem)) {
                New-Item -ItemType Directory -Path $targetItem -Force | Out-Null
            }
        } else {
            $parentDir = Split-Path $targetItem -Parent
            if (-not (Test-Path $parentDir)) {
                New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
            }
            Copy-Item -Path $_.FullName -Destination $targetItem -Force
        }
    }

    Compress-Archive -Path "$TempStaging\*" -DestinationPath $TargetPath -Force
    $Hash = (Get-FileHash -Path $TargetPath -Algorithm SHA256).Hash

    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "ARCHIVAL COMPLETE" -ForegroundColor Green
    Write-Host "Archive File : $TargetPath"
    Write-Host "SHA-256 Hash : $Hash"
    Write-Host "======================================================================" -ForegroundColor Green
}
finally {
    if (Test-Path $TempStaging) {
        Remove-Item -Path $TempStaging -Recurse -Force -ErrorAction SilentlyContinue
    }
}
