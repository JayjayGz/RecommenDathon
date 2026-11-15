param(
    [string]$PlanPath = (Join-Path $PSScriptRoot '../livrables/historique_hebdomadaire/nettoyage_telechargements_plan.json')
)

$ErrorActionPreference = 'Stop'
$workspaceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$downloadsRoot = (Resolve-Path -LiteralPath 'C:\Users\alibe\Downloads').ProviderPath.TrimEnd('\')
$nestedRoot = Join-Path $downloadsRoot 'Datathon2026\Datathon2026\alphaforge_starter'
$archiveRoot = Join-Path $workspaceRoot 'livrables\historique_hebdomadaire\archives_telechargements'
$resultPath = Join-Path $workspaceRoot 'livrables\historique_hebdomadaire\nettoyage_telechargements_resultat.json'
$plan = Get-Content -LiteralPath $PlanPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Assert-FileHash([string]$FilePath, [string]$ExpectedHash) {
    $item = Get-Item -LiteralPath $FilePath -Force
    if ($item.PSIsContainer -or (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw "Not a regular file: $FilePath"
    }
    if ((Get-FileHash -LiteralPath $FilePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedHash) {
        throw "File changed since inspection: $FilePath"
    }
}

if ($plan.keep.path -ne (Join-Path $downloadsRoot 'top100_hebdo_2016_complet.csv')) {
    throw 'Unexpected file to retain'
}
Assert-FileHash $plan.keep.path $plan.keep.sha256
Assert-FileHash $plan.preserve_source.path $plan.preserve_source.sha256
if ($plan.files.Count -ne 9) { throw 'Unexpected deletion scope' }

# Preflight every explicit file path. No wildcard or recursive deletion is used.
foreach ($entry in $plan.files) {
    $absoluteSource = (Resolve-Path -LiteralPath $entry.path).ProviderPath
    $sourceParent = Split-Path -Parent $absoluteSource
    $sourceName = Split-Path -Leaf $absoluteSource
    if ($sourceParent -notin @($downloadsRoot, $nestedRoot) -or
        -not $absoluteSource.StartsWith($downloadsRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
        -not $sourceName.StartsWith('top100_hebdo_2016', [StringComparison]::OrdinalIgnoreCase) -or
        $absoluteSource -eq $plan.keep.path) {
        throw "Out-of-scope deletion: $absoluteSource"
    }
    Assert-FileHash $absoluteSource $entry.sha256
    $absoluteArchive = [IO.Path]::GetFullPath($entry.archive)
    if (-not $absoluteArchive.StartsWith($archiveRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Out-of-scope archive: $absoluteArchive"
    }
}

# Archive and verify all nine files before removing any copy from Downloads.
foreach ($entry in $plan.files) {
    $archiveParent = Split-Path -Parent $entry.archive
    New-Item -ItemType Directory -Path $archiveParent -Force | Out-Null
    if (-not (Test-Path -LiteralPath $entry.archive)) {
        Copy-Item -LiteralPath $entry.path -Destination $entry.archive
    }
    Assert-FileHash $entry.archive $entry.sha256
}

$removed = @()
try {
    foreach ($entry in $plan.files) {
        Assert-FileHash $plan.keep.path $plan.keep.sha256
        Assert-FileHash $entry.path $entry.sha256
        Assert-FileHash $entry.archive $entry.sha256
        Remove-Item -LiteralPath $entry.path -Force
        if (Test-Path -LiteralPath $entry.path) { throw "Removal failed: $($entry.path)" }
        $removed += [ordered]@{ path = $entry.path; archive = $entry.archive; sha256 = $entry.sha256 }
    }
    Assert-FileHash $plan.keep.path $plan.keep.sha256
    Assert-FileHash $plan.preserve_source.path $plan.preserve_source.sha256
    $remaining = @(Get-ChildItem -LiteralPath $downloadsRoot -File -Filter 'top100_hebdo_2016*')
    $nestedRemaining = @(Get-ChildItem -LiteralPath $nestedRoot -File -Filter 'top100_hebdo_2016*')
    if ($remaining.Count -ne 1 -or $remaining[0].FullName -ne $plan.keep.path -or $nestedRemaining.Count -ne 0) {
        throw 'Unexpected remaining history files; no additional files removed'
    }
    $report = [ordered]@{
        status = 'complete'; removed_count = $removed.Count; removed_bytes = $plan.total_bytes
        retained = $plan.keep; source_preserved = $plan.preserve_source; removed = $removed
        checks = @('All archived file hashes match', 'Retained CSV unchanged', 'Selection source unchanged',
                   'Only one weekly-history file remains in Downloads', 'No wildcard or recursive deletion')
        handoff = @{ primary = 'infrastructure'; support = 'evidence'; status = 'complete'; next_owner = 'user' }
    }
} catch {
    $report = [ordered]@{ status = 'failed'; removed_count = $removed.Count; removed = $removed; error = $_.Exception.Message }
    [IO.File]::WriteAllText($resultPath, ($report | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    throw
}
[IO.File]::WriteAllText($resultPath, ($report | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
$report | Select-Object status, removed_count, removed_bytes, retained | ConvertTo-Json -Depth 4
