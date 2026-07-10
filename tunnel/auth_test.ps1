$base = "http://127.0.0.1:8000"

Write-Output "===== Auth security tests ====="

# Test A: no token at all -> expect 401
try {
    $r = Invoke-WebRequest -Uri "$base/api/status" -UseBasicParsing -TimeoutSec 5
    Write-Output "[FAIL] no-token -> $($r.StatusCode) (expected 401)"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    $ok = if ($code -eq 401) { "OK" } else { "FAIL" }
    Write-Output "[$ok] no-token -> $code"
}

# Test B: wrong token -> expect 401
try {
    $r = Invoke-WebRequest -Uri "$base/api/status" -Headers @{Authorization="Bearer WRONG"} -UseBasicParsing -TimeoutSec 5
    Write-Output "[FAIL] wrong-token -> $($r.StatusCode) (expected 401)"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    $ok = if ($code -eq 401) { "OK" } else { "FAIL" }
    Write-Output "[$ok] wrong-token -> $code"
}

# Test C: correct token -> expect 200
try {
    $r = Invoke-WebRequest -Uri "$base/api/status" -Headers @{Authorization="Bearer fk8_gViRMN_H12ctG_mGRQ2JY0gMng1w"} -UseBasicParsing -TimeoutSec 5
    $ok = if ($r.StatusCode -eq 200) { "OK" } else { "FAIL" }
    Write-Output "[$ok] correct-token -> $($r.StatusCode)"
} catch {
    Write-Output "[FAIL] correct-token threw: $($_.Exception.Message)"
}

# Test D: token via query param -> expect 200
try {
    $r = Invoke-WebRequest -Uri "$base/api/status?token=fk8_gViRMN_H12ctG_mGRQ2JY0gMng1w" -UseBasicParsing -TimeoutSec 5
    $ok = if ($r.StatusCode -eq 200) { "OK" } else { "FAIL" }
    Write-Output "[$ok] query-param-token -> $($r.StatusCode)"
} catch {
    Write-Output "[FAIL] query-param-token threw: $($_.Exception.Message)"
}

# Test E: static asset without token -> expect 200 (public)
try {
    $r = Invoke-WebRequest -Uri "$base/" -UseBasicParsing -TimeoutSec 5
    $ok = if ($r.StatusCode -eq 200) { "OK" } else { "FAIL" }
    Write-Output "[$ok] static-index-no-token -> $($r.StatusCode)"
} catch {
    Write-Output "[FAIL] static-index threw: $($_.Exception.Message)"
}

# Test F: /health without token -> expect 200 (public)
try {
    $r = Invoke-WebRequest -Uri "$base/health" -UseBasicParsing -TimeoutSec 5
    $ok = if ($r.StatusCode -eq 200) { "OK" } else { "FAIL" }
    Write-Output "[$ok] health-no-token -> $($r.StatusCode)"
} catch {
    Write-Output "[FAIL] health threw: $($_.Exception.Message)"
}

Write-Output ""
Write-Output "===== Process & port check ====="
$proc = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
if ($proc) { Write-Output "[OK] cloudflared running (PID $($proc.Id))" }
else { Write-Output "[FAIL] cloudflared not running" }

$py = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*backend*" -or $true }
if ($py) { Write-Output "[OK] python running (PID $($py.Id -join ','))" }
else { Write-Output "[FAIL] python not running" }

$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($conns) { Write-Output "[OK] port 8000 listening" }
else { Write-Output "[FAIL] port 8000 not listening" }
