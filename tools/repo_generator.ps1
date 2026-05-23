$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$ZipRoot = Join-Path $Root "zips"
$ExcludeDirs = @("__pycache__", ".git", ".github", "tools", "zips")
$ExcludeFiles = @(".gitignore", ".DS_Store", "Thumbs.db")

function Get-AddonDirs {
    $paths = @()
    $repoAddon = Join-Path $Root "repository.signaturerepo"
    if (Test-Path (Join-Path $repoAddon "addon.xml")) {
        $paths += $repoAddon
    }
    $addonsRoot = Join-Path $Root "addons"
    if (Test-Path $addonsRoot) {
        Get-ChildItem $addonsRoot -Directory | ForEach-Object {
            if (Test-Path (Join-Path $_.FullName "addon.xml")) {
                $paths += $_.FullName
            }
        }
    }
    return $paths
}

function Get-AddonMeta($AddonDir) {
    $content = Get-Content (Join-Path $AddonDir "addon.xml") -Raw
    if ($content -notmatch '(?s)(<addon\b.*?</addon>)') {
        throw "Could not parse addon block in $AddonDir"
    }
    $block = $Matches[1].Trim()
    [xml]$xml = $content
    return @{
        Id = $xml.addon.id
        Version = $xml.addon.version
        Block = $block
    }
}

function Should-Skip($FullPath) {
    foreach ($part in $ExcludeDirs) {
        if ($FullPath -match "[\\/]$([regex]::Escape($part))([\\/]|$)") { return $true }
    }
    $name = Split-Path $FullPath -Leaf
    if ($ExcludeFiles -contains $name) { return $true }
    if ($name -match '\.(pyc|pyo)$') { return $true }
    return $false
}

function Build-Zip($AddonDir) {
    $meta = Get-AddonMeta $AddonDir
    $targetDir = Join-Path $ZipRoot $meta.Id
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    $zipPath = Join-Path $targetDir "$($meta.Id)-$($meta.Version).zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)

    try {
        Get-ChildItem $AddonDir -Recurse -File | ForEach-Object {
            if (Should-Skip $_.FullName) { return }
            $relative = $_.FullName.Substring($AddonDir.Length).TrimStart('\', '/')
            $entryName = ($meta.Id + '/' + $relative).Replace('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $_.FullName, $entryName) | Out-Null
        }
    }
    finally {
        $archive.Dispose()
    }

    return $zipPath
}

if (Test-Path $ZipRoot) {
    Remove-Item $ZipRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ZipRoot | Out-Null

$addonDirs = Get-AddonDirs
if (-not $addonDirs.Count) {
    throw "No add-ons found."
}

$blocks = @()
foreach ($addonDir in $addonDirs) {
    $zipPath = Build-Zip $addonDir
    Write-Output "Built $zipPath"
    $blocks += (Get-AddonMeta $addonDir).Block
}

$addonsXml = @"
<?xml version="1.0" encoding="UTF-8"?>
<addons>
$($blocks | ForEach-Object { "  $_" } | Out-String)
</addons>
"@

$addonsPath = Join-Path $Root "addons.xml"
Set-Content -Path $addonsPath -Value $addonsXml.TrimEnd() -Encoding UTF8

$md5 = (Get-FileHash $addonsPath -Algorithm MD5).Hash.ToLower()
Set-Content -Path (Join-Path $Root "addons.xml.md5") -Value $md5 -Encoding ASCII -NoNewline

Write-Output "Updated addons.xml and addons.xml.md5"
