# Lance toutes les suites de tests (moteur, API, front). Windows.
$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent $PSScriptRoot
$python = Join-Path $racine ".venv\Scripts\python.exe"
$echecs = @()

function Suite([string]$nom, [string]$dossier, [string]$commande, [string[]]$arguments) {
    Write-Host "`n==> $nom" -ForegroundColor Cyan
    Push-Location (Join-Path $racine $dossier)
    try { & $commande @arguments } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { $script:echecs += $nom }
}

Suite "Moteur" "engine" $python @("-m", "pytest", "-q")
Suite "API" "api" $python @("-m", "pytest", "-q", "-W", "ignore::DeprecationWarning")
Suite "Front" "web" "npm" @("test")

if ($echecs.Count -gt 0) { Write-Host "`nÉchec : $($echecs -join ', ')" -ForegroundColor Red; exit 1 }
Write-Host "`nTous les tests passent." -ForegroundColor Green
