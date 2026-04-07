#!/usr/bin/env pwsh
# Pre-submission validation script for OpenEnv submission
# Tests: 1) HF Space connectivity (or local server), 2) Docker build, 3) openenv validate

# Color codes
$GREEN = "`e[32m"
$RED = "`e[31m"
$YELLOW = "`e[33m"
$BOLD = "`e[1m"
$NC = "`e[0m"

# Configuration
$REPO_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$DOCKER_BUILD_TIMEOUT = 300  # 5 minutes
$HF_SPACE_URL = if ($env:HF_SPACE_URL) { $env:HF_SPACE_URL } else { "http://localhost:8000" }
$PING_URL = "$HF_SPACE_URL"

function pass {
    param([string]$message)
    Write-Host "${GREEN}✓${NC} $message" -ForegroundColor Green
}

function fail {
    param([string]$message)
    Write-Host "${RED}✗${NC} $message" -ForegroundColor Red
}

function hint {
    param([string]$message)
    Write-Host "  ${YELLOW}→${NC} $message" -ForegroundColor Yellow
}

function log {
    param([string]$message)
    Write-Host "$message"
}

function stop_at {
    param([string]$step)
    Write-Host ""
    Write-Host "${RED}Validation stopped at $step.${NC}" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "${BOLD}========================================${NC}"
Write-Host "${BOLD}  OpenEnv Pre-Submission Validation${NC}"
Write-Host "${BOLD}========================================${NC}"
Write-Host ""

# Step 1: Check HF Space connectivity
log "${BOLD}Step 1/3: Checking HF Space connectivity (or local server)${NC} ..."
log "  Pinging: $PING_URL/reset"

try {
    $response = Invoke-WebRequest -Uri "$PING_URL/reset" -Method POST -TimeoutSec 10 -SkipHttpErrorCheck
    $HTTP_CODE = $response.StatusCode
} catch {
    $HTTP_CODE = "000"
}

if ($HTTP_CODE -eq 200) {
    pass "HF Space is live and responds to /reset"
} elseif ($HTTP_CODE -eq "000") {
    fail "HF Space not reachable (connection failed or timed out)"
    hint "Check your network connection and that the Space is running."
    hint "Try: Invoke-WebRequest -Uri '$PING_URL/reset' -Method POST -SkipHttpErrorCheck"
    stop_at "Step 1"
} else {
    fail "HF Space /reset returned HTTP $HTTP_CODE (expected 200)"
    hint "Make sure your Space is running and the URL is correct."
    hint "Try opening $PING_URL in your browser first."
    stop_at "Step 1"
}

# Step 2: Check Docker build
log ""
log "${BOLD}Step 2/3: Running docker build${NC} ..."

$DOCKER_FOUND = Get-Command docker -ErrorAction SilentlyContinue
if (-not $DOCKER_FOUND) {
    fail "docker command not found"
    hint "Install Docker: https://docs.docker.com/get-docker/"
    stop_at "Step 2"
}

# Find Dockerfile
$DOCKERFILE_LOCATION = $null
if (Test-Path "$REPO_DIR/Dockerfile") {
    $DOCKERFILE_LOCATION = "$REPO_DIR"
} elseif (Test-Path "$REPO_DIR/server/Dockerfile") {
    $DOCKERFILE_LOCATION = "$REPO_DIR/server"
} else {
    fail "No Dockerfile found in repo root or server/ directory"
    stop_at "Step 2"
}

log "  Found Dockerfile in $DOCKERFILE_LOCATION"

# Build Docker image with timeout
$BUILD_OK = $false
$BUILD_OUTPUT = @()

try {
    $BUILD_OUTPUT = & docker build $DOCKERFILE_LOCATION 2>&1
    $BUILD_OK = $LASTEXITCODE -eq 0
} catch {
    $BUILD_OUTPUT = $_.ToString()
    $BUILD_OK = $false
}

if ($BUILD_OK) {
    pass "Docker build succeeded"
} else {
    fail "Docker build failed"
    ($BUILD_OUTPUT | Select-Object -Last 20) | ForEach-Object { log "  $_" }
    stop_at "Step 2"
}

# Step 3: Run openenv validate
log ""
log "${BOLD}Step 3/3: Running openenv validate${NC} ..."

$OPENENV_FOUND = Get-Command openenv -ErrorAction SilentlyContinue
if (-not $OPENENV_FOUND) {
    fail "openenv command not found"
    hint "Install it: pip install openenv-core"
    stop_at "Step 3"
}

$VALIDATE_OK = $false
$VALIDATE_OUTPUT = @()

try {
    Push-Location $REPO_DIR
    $VALIDATE_OUTPUT = & openenv validate 2>&1
    $VALIDATE_OK = $LASTEXITCODE -eq 0
} catch {
    $VALIDATE_OUTPUT = $_.ToString()
    $VALIDATE_OK = $false
} finally {
    Pop-Location
}

if ($VALIDATE_OK) {
    pass "openenv validate passed"
    if ($VALIDATE_OUTPUT) {
        log "  $($VALIDATE_OUTPUT -join "`n  ")"
    }
} else {
    fail "openenv validate failed"
    $VALIDATE_OUTPUT | ForEach-Object { log "  $_" }
    stop_at "Step 3"
}

Write-Host ""
Write-Host "${BOLD}========================================${NC}"
Write-Host "${GREEN}${BOLD}  All 3/3 checks passed!${NC}"
Write-Host "${GREEN}${BOLD}  Your submission is ready to submit.${NC}"
Write-Host "${BOLD}========================================${NC}"
Write-Host ""

exit 0
