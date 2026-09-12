param(
    [Parameter(Mandatory=$true)][string]$Workspace,
    [string]$SkillHome = $(if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }),
    [switch]$SkipDependencies
)
$ErrorActionPreference = 'Stop'
$sourceSkill = [IO.Path]::GetFullPath($PSScriptRoot)
$targetHome = [IO.Path]::GetFullPath($SkillHome)
$targetSkill = Join-Path $targetHome 'exam-register'
$workRoot = [IO.Path]::GetFullPath($Workspace)
if ($workRoot.StartsWith($targetSkill + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or $workRoot -eq $targetSkill) { throw 'Workspace must be outside the installed skill' }
if ($targetSkill.StartsWith($sourceSkill + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Cannot install inside source skill' }
foreach ($name in @('config','inputs','cache','runs')) { New-Item -ItemType Directory -Path (Join-Path $workRoot $name) -Force | Out-Null }
$localSettings = Join-Path $workRoot 'config/settings.local.json'
if (-not (Test-Path -LiteralPath $localSettings)) { Copy-Item -LiteralPath (Join-Path $sourceSkill 'config/settings.example.json') -Destination $localSettings }
if (-not $SkipDependencies) {
    $venvPython = Join-Path $workRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & python -m venv (Join-Path $workRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
    }
    & $venvPython -m pip install -r (Join-Path $sourceSkill 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; installed skill was not changed' }
    & $venvPython (Join-Path $sourceSkill 'scripts/check_env.py') --workspace $workRoot
    if ($LASTEXITCODE -ne 0) { throw 'Environment check failed' }
}
$backup = $null
if ($sourceSkill -ne $targetSkill) {
    New-Item -ItemType Directory -Path $targetHome -Force | Out-Null
    if (Test-Path -LiteralPath $targetSkill) {
        $backupRoot = Join-Path $targetHome '.backups'
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        $backup = Join-Path $backupRoot ('exam-register-' + [Guid]::NewGuid().ToString('N'))
        if (-not $backup.StartsWith($targetHome + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid backup path' }
        # Both resolved paths are inside the explicitly selected skill home.
        Move-Item -LiteralPath $targetSkill -Destination $backup
    }
    try {
        New-Item -ItemType Directory -Path $targetSkill -Force | Out-Null
        foreach ($sourceFile in (Get-ChildItem -LiteralPath $sourceSkill -File -Recurse)) {
            $relativeFile = [IO.Path]::GetRelativePath($sourceSkill, $sourceFile.FullName)
            if ($relativeFile -match '(^|[\\/])(__pycache__|\.git)([\\/]|$)' -or $sourceFile.Name -like '*.pyc' -or $sourceFile.Name -like '.env*' -or $sourceFile.Name -like '*.local.json') { continue }
            $destinationFile = Join-Path $targetSkill $relativeFile
            New-Item -ItemType Directory -Path (Split-Path $destinationFile -Parent) -Force | Out-Null
            Copy-Item -LiteralPath $sourceFile.FullName -Destination $destinationFile
        }
    }
    catch {
        if (Test-Path -LiteralPath $targetSkill) {
            $failedCopy = Join-Path $targetHome ('.failed-exam-register-' + [Guid]::NewGuid().ToString('N'))
            Move-Item -LiteralPath $targetSkill -Destination $failedCopy
        }
        if ($backup) { Move-Item -LiteralPath $backup -Destination $targetSkill }
        throw
    }
}
@{ installedSkill=$targetSkill; workspace=$workRoot; backup=$backup; dependenciesSkipped=[bool]$SkipDependencies; mcp='Check teamsword_ping in Codex'; recognition='Verify skill in next turn' } | ConvertTo-Json
