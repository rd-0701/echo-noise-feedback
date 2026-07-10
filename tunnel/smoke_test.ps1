$token = "fk8_gViRMN_H12ctG_mGRQ2JY0gMng1w"
$base = "http://127.0.0.1:8000"

function Test-Endpoint($name, $method, $path, $bodyJson=$null, $expect=200) {
    try {
        $headers = @{ "Authorization" = "Bearer $token" }
        if ($method -eq "GET") {
            $r = Invoke-WebRequest -Uri "$base$path" -Method GET -Headers $headers -UseBasicParsing -TimeoutSec 10
        } else {
            if ($bodyJson) {
                $r = Invoke-WebRequest -Uri "$base$path" -Method $method -Headers $headers -Body $bodyJson -ContentType "application/json" -UseBasicParsing -TimeoutSec 10
            } else {
                $r = Invoke-WebRequest -Uri "$base$path" -Method $method -Headers $headers -UseBasicParsing -TimeoutSec 10
            }
        }
        $ok = if ($r.StatusCode -eq $expect) { "OK" } else { "MISMATCH" }
        $body = if ($r.Content.Length -lt 400) { $r.Content } else { "(" + $r.Content.Length + " bytes)" }
        Write-Output "[$ok] $name -> $($r.StatusCode)  $body"
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        $ok = if ($code -eq $expect) { "OK" } else { "FAIL" }
        Write-Output "[$ok] $name -> $code"
    }
}

Write-Output "===== 1. Basic APIs ====="
Test-Endpoint "GET /health"          "GET"  "/health"
Test-Endpoint "GET /api/status"      "GET"  "/api/status"
Test-Endpoint "GET /api/config"      "GET"  "/api/config"
Test-Endpoint "GET /api/devices"     "GET"  "/api/devices"
Test-Endpoint "GET /api/sounds"      "GET"  "/api/sounds"
Test-Endpoint "GET /api/history"     "GET"  "/api/history?range_=day"

Write-Output ""
Write-Output "===== 2. Toggle (off then on) ====="
Test-Endpoint "POST /api/toggle off" "POST" "/api/toggle" '{"enabled":false}'
Test-Endpoint "POST /api/toggle on"  "POST" "/api/toggle" '{"enabled":true}'

Write-Output ""
Write-Output "===== 3. Baseline reset ====="
Test-Endpoint "POST /api/baseline/reset" "POST" "/api/baseline/reset"

Write-Output ""
Write-Output "===== 4. Trigger playback (auto level, expect 409 if BT down or 200 if BT up) ====="
Test-Endpoint "POST /api/trigger auto" "POST" "/api/trigger" '{}'

Write-Output ""
Write-Output "===== 5. Auth tests ====="
Test-Endpoint "GET /api/status no-token (expect 401)" "GET" "/api/status" $null 401

Write-Output ""
Write-Output "===== 6. Synthesize sound ====="
Test-Endpoint "POST /api/sounds/synthesize" "POST" "/api/sounds/synthesize" '{"name":"test_sweep","kind":"sweep","f0":40,"f1":150,"duration_s":2}'

Write-Output ""
Write-Output "===== 7. Cloudflare tunnel URL ====="
$log = "d:\桌面文件\echo-project\tunnel\tunnel.log"
if (Test-Path $log) {
    $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
    if ($m) { Write-Output "TUNNEL_URL: $($m.Matches[0].Value)" }
    else { Write-Output "TUNNEL_URL: not found in log" }
} else { Write-Output "tunnel.log not found" }
