# Installe l'environnement de développement (Windows, PowerShell 5.1+).
#   powershell -ExecutionPolicy Bypass -File scripts\installer-dev.ps1
#   ... -BaseSeulement   : recrée seulement la base SQLite de démo
param([switch]$BaseSeulement)

$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent $PSScriptRoot
Set-Location $racine
$python = Join-Path $racine ".venv\Scripts\python.exe"

function Etape([string]$titre) { Write-Host "`n==> $titre" -ForegroundColor Cyan }

# Les commandes externes ne lèvent pas d'exception en PowerShell : on vérifie le code retour.
function Executer([string]$commande, [string[]]$arguments) {
    & $commande @arguments
    if ($LASTEXITCODE -ne 0) { throw "Échec : $commande $($arguments -join ' ')" }
}

if (-not $BaseSeulement) {
    Etape "Vérification des prérequis"
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3.11+ introuvable : https://www.python.org/downloads/" }
    Executer python @("-c", "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 ou plus requis, trouvé ' + sys.version")
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Node.js 20+ introuvable : https://nodejs.org/" }

    Etape "Environnement Python (.venv)"
    if (-not (Test-Path $python)) { Executer python @("-m", "venv", ".venv") }
    Executer $python @("-m", "pip", "install", "--quiet", "--upgrade", "pip")
    # -e : installation « éditable », les modifications du code sont prises en compte sans réinstaller.
    Executer $python @("-m", "pip", "install", "--quiet", "-e", ".\engine[dev]", "-e", ".\api[dev]")

    Etape "Dépendances du front (npm ci)"
    Push-Location web
    try { Executer npm @("ci", "--no-audit", "--no-fund") } finally { Pop-Location }
}

Etape "Base de démo SQLite (api\pkp.db)"
Push-Location api
try {
    if (Test-Path pkp.db) { Remove-Item pkp.db }
    Executer $python @("-m", "alembic", "upgrade", "head")
    Executer $python @("-m", "app.db.seed")
} finally { Pop-Location }

Write-Host "`nPrêt." -ForegroundColor Green
Write-Host "Dans VS Code : ouvrir pkp-math-lycee.code-workspace, puis Exécuter et déboguer > « ▶ API + Front »."
Write-Host "Front : http://localhost:5173  ·  Enseignant : /enseignant (demo@pkp.test, mot de passe dans api\app\db\seed.py)"
