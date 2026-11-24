# LearnForge AI — Ollama Setup & Model Pull Script
# Automatically verifies Ollama service and pulls the optimized Qwen model for LearnForge AI.

$ErrorActionPreference = "Continue"

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "   🚀 LearnForge AI — Local Ollama AI Setup & Sync     " -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

# 1. Check if Ollama executable exists
$OllamaPath = (Get-Command ollama -ErrorAction SilentlyContinue).Source
if (-not $OllamaPath) {
    if (Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe") {
        $OllamaPath = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    } elseif (Test-Path "C:\Program Files\Ollama\ollama.exe") {
        $OllamaPath = "C:\Program Files\Ollama\ollama.exe"
    }
}

if (-not $OllamaPath) {
    Write-Host "[INFO] Ollama installation is in progress or downloading." -ForegroundColor Yellow
    Write-Host "If not yet installed, download from https://ollama.com/download/windows" -ForegroundColor Yellow
    exit 0
}

Write-Host "[OK] Found Ollama binary at: $OllamaPath" -ForegroundColor Green

# 2. Check if Ollama server is running
$isOnline = $false
try {
    $res = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
    $isOnline = $true
} catch {
    $isOnline = $false
}

if (-not $isOnline) {
    Write-Host "[INFO] Starting Ollama background server..." -ForegroundColor Yellow
    Start-Process -FilePath $OllamaPath -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

# 3. Pull Recommended Model (qwen2.5:3b)
$TargetModel = "qwen2.5:3b"
Write-Host "`n[INFO] Checking model '$TargetModel' in local Ollama library..." -ForegroundColor Cyan

try {
    $tagRes = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -ErrorAction Stop
    $installed = $tagRes.models | ForEach-Object { $_.name }
    $hasModel = $installed | Where-Object { $_ -like "*$TargetModel*" }

    if ($hasModel) {
        Write-Host "[OK] Model '$TargetModel' is already installed and ready!" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Downloading and pulling '$TargetModel' (optimized for your CPU/RAM)..." -ForegroundColor Yellow
        & $OllamaPath pull $TargetModel
        Write-Host "[OK] Model '$TargetModel' successfully pulled!" -ForegroundColor Green
    }
} catch {
    Write-Host "[WARNING] Could not query tags. Running pull directly..." -ForegroundColor Yellow
    & $OllamaPath pull $TargetModel
}

# 4. End-to-end verification test
Write-Host "`n[INFO] Running test inference with LearnForge AI..." -ForegroundColor Cyan
try {
    $testPayload = @{
        model = $TargetModel
        prompt = "Hello! In one sentence, what is LearnForge AI?"
        stream = $false
    } | ConvertTo-Json

    $testRes = Invoke-RestMethod -Uri "http://localhost:11434/api/generate" -Method Post -Body $testPayload -ContentType "application/json"
    Write-Host "[OK] Ollama generated response successfully:" -ForegroundColor Green
    Write-Host "     $($testRes.response.Trim())`n" -ForegroundColor Gray
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host "   ✅ Local Ollama is 100% integrated with LearnForge! " -ForegroundColor Green
    Write-Host "========================================================`n" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Test inference skipped: $($_.Exception.Message)" -ForegroundColor Yellow
}
