#
# validate-submission.ps1 — OpenEnv Submission Validator (Windows PowerShell)
#
# Checks that your HF Space is live, Docker image builds, and inference script passes.
#
# Prerequisites:
#   - Docker:       https://docs.docker.com/get-docker/
#   - Python:       With openai, asyncio, etc. installed
#   - curl (via Invoke-WebRequest)
#
# Run:
#   .\validate-submission.ps1 -PingUrl "https://your-space.hf.space"
#   .\validate-submission.ps1 -PingUrl "https://your-space.hf.space" -RepoDir ".\my-repo"
#
# Arguments:
#   -PingUrl    Your HuggingFace Space URL (e.g. https://your-space.hf.space)
#   -RepoDir    Path to your repo (default: current directory)
#

param(
    [Parameter(Mandatory=$true)]
    [string]$PingUrl,
    
    [Parameter(Mandatory=$false)]
    [string]$RepoDir = "."
)

$ErrorActionPreference = "Stop"

# Color helpers
$code_esc = [char]27
$RESET = "${code_esc}[0m"
$GREEN = "${code_esc}[32m"
$RED = "${code_esc}[31m"
$YELLOW = "${code_esc}[33m"
$BOLD = "${code_esc}[1m"

$PASS = 0
$FAIL = 0

function Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Pass {
    param([string]$Message)
    Log "$GREEN[PASSED]$RESET -- $Message"
    $script:PASS++
}

function Fail {
    param([string]$Message)
    Log "$RED[FAILED]$RESET -- $Message"
    $script:FAIL++
}

function Hint {
    param([string]$Message)
    Write-Host "  $YELLOW[Hint]$RESET $Message"
}

function StopAt {
    param([string]$Step)
    Write-Host ""
    Write-Host "$RED$BOLD❌ Validation stopped at $Step.$RESET"
    Write-Host "Fix the above before continuing."
    exit 1
}

# Validate repo directory exists
try {
    $RepoDir = (Resolve-Path $RepoDir -ErrorAction Stop).Path
}
catch {
    Write-Host "Error: directory '$RepoDir' not found"
    exit 1
}

# Normalize URL (remove trailing slash)
$PingUrl = $PingUrl.TrimEnd('/')

Write-Host ""
Write-Host "========================================"
Write-Host "  OpenEnv Submission Validator"
Write-Host "========================================"
Log "Repo:     $RepoDir"
Log "Ping URL: $PingUrl"
Write-Host ""

# ============================================================================
# STEP 1: Ping HF Space
# ============================================================================
Log "[Step 1/3] Pinging HF Space ($PingUrl/reset) ..."

try {
    $response = Invoke-WebRequest `
        -Uri "$PingUrl/reset" `
        -Method POST `
        -Headers @{"Content-Type" = "application/json"} `
        -Body '{}' `
        -UseBasicParsing `
        -TimeoutSec 30 `
        -ErrorAction Stop
    
    if ($response.StatusCode -eq 200) {
        Pass "HF Space is live and responds to /reset (HTTP 200)"
    }
    else {
        Fail "HF Space /reset returned HTTP $($response.StatusCode) (expected 200)"
        Hint "Make sure your Space is running and the URL is correct."
        StopAt "Step 1"
    }
}
catch {
    Fail "HF Space not reachable (connection failed)"
    Hint "Check your network connection and that the Space is running."
    Hint "Try opening $PingUrl in your browser first."
    Hint "Error: $($_.Exception.Message)"
    StopAt "Step 1"
}

# ============================================================================
# STEP 2: Docker Build
# ============================================================================
Log "$BOLD[Step 2/3] Running docker build$RESET ..."

# Find Dockerfile
$DockerfilePath = $null
$DockerContext = $null

if (Test-Path "$RepoDir/Dockerfile") {
    $DockerfilePath = "$RepoDir/Dockerfile"
    $DockerContext = $RepoDir
}
elseif (Test-Path "$RepoDir/my_env/server/Dockerfile") {
    $DockerfilePath = "$RepoDir/my_env/server/Dockerfile"
    $DockerContext = "$RepoDir/my_env/server"
}

if ($null -eq $DockerfilePath) {
    Fail "No Dockerfile found in repo root or my_env/server/ directory"
    StopAt "Step 2"
}

Log "  Found Dockerfile in $DockerContext"

# Check if docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "docker command not found"
    Hint "Install Docker: https://docs.docker.com/get-docker/"
    StopAt "Step 2"
}

# Run docker build with timeout
$buildCmd = "docker build `"$DockerContext`""
try {
    $buildOutput = & cmd /c "$buildCmd 2>&1" | Tee-Object -Variable buildLog
    Pass "Docker build succeeded"
}
catch {
    Fail "Docker build failed"
    Hint "Check the Dockerfile for syntax errors"
    Hint "Last 10 lines of build output:"
    if ($buildLog) { $buildLog | Select-Object -Last 10 | ForEach-Object { Write-Host "    $_" }}
    StopAt "Step 2"
}

# ============================================================================
# STEP 3: Inference Script Validation
# ============================================================================
Log "$BOLD[Step 3/3] Running inference script validation$RESET ..."

$inferenceScript = "$RepoDir/inference.py"
if (-not (Test-Path $inferenceScript)) {
    Fail "inference.py not found in repo root"
    Hint "Create $RepoDir/inference.py with proper OpenAI integration"
    StopAt "Step 3"
}

# Check required components in inference.py
$validationChecks = @{
    "OpenAI import" = "from openai import|import OpenAI"
    "[START] logging" = "\[START\]"
    "[STEP] logging" = "\[STEP\]"
    "[END] logging" = "\[END\]"
    "Score field" = "score="
    "Environment variables" = "API_BASE_URL|MODEL_NAME|HF_TOKEN"
    "Async support" = "async def|asyncio.run"
}

$allChecksPass = $true
foreach ($check in $validationChecks.GetEnumerator()) {
    $content = Get-Content $inferenceScript -Raw
    if ($content -match $check.Value) {
        Log "  ✓ $($check.Name) found"
    }
    else {
        Fail "  ✗ $($check.Name) not found"
        Hint "Update inference.py to include: $($check.Value)"
        $allChecksPass = $false
    }
}

if ($allChecksPass) {
    Pass "inference.py validation passed"
}
else {
    StopAt "Step 3"
}

# ============================================================================
# Final Summary
# ============================================================================
Write-Host ""
Write-Host "$BOLD========================================$RESET"
Write-Host "$GREEN$BOLD✅ All 3/3 checks passed!$RESET"
Write-Host "$GREEN$BOLD   Your submission is ready to submit.$RESET"
Write-Host "$BOLD========================================$RESET"
Write-Host ""

exit 0
