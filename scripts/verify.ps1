# scripts/verify.ps1 - Run full suite verification across backend and web UI

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Warehouse Video Intelligence: Full Verification" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Backend Pytest
Write-Host "`n[1/3] Running Backend Unit & Integration Tests..." -ForegroundColor Yellow
pytest backend/tests -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Backend tests failed!" -ForegroundColor Red
    exit 1
}
Write-Host "[PASS] All backend tests passed." -ForegroundColor Green

# 2. Frontend TypeScript Typecheck
Write-Host "`n[2/3] Checking Web UI TypeScript Types..." -ForegroundColor Yellow
pnpm --dir apps/web exec tsc --noEmit
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] TypeScript typecheck failed!" -ForegroundColor Red
    exit 1
}
Write-Host "[PASS] TypeScript compilation passed with zero errors." -ForegroundColor Green

# 3. Frontend Next.js Production Build
Write-Host "`n[3/3] Building Web UI Production Bundle..." -ForegroundColor Yellow
pnpm --dir apps/web build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Next.js build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "[PASS] Next.js production build succeeded." -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  ALL VERIFICATION GATES PASSED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
