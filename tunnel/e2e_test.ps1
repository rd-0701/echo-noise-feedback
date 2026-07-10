# 端到端公网验证
$pub = "https://band-coaching-charles-national.trycloudflare.com"
$token = "fk8_gViRMN_H12ctG_mGRQ2JY0gMng1w"

Write-Output "===== E2E via public URL ====="
Write-Output "URL: $pub"
Write-Output ""

# 1. public endpoints
Write-Output "--- 1. Public endpoints ---"
try {
    $r = Invoke-WebRequest -Uri "$pub/" -UseBasicParsing -TimeoutSec 30
    Write-Output ("[OK]   GET /            -> {0}  ({1} bytes)" -f $r.StatusCode, $r.Content.Length)
} catch { Write-Output "[FAIL] GET /  : $($_.Exception.Message)" }

try {
    $r = Invoke-WebRequest -Uri "$pub/health" -UseBasicParsing -TimeoutSec 30
    Write-Output ("[OK]   GET /health      -> {0}  {1}" -f $r.StatusCode, $r.Content)
} catch { Write-Output "[FAIL] GET /health : $($_.Exception.Message)" }

try {
    $r = Invoke-WebRequest -Uri "$pub/manifest.json" -UseBasicParsing -TimeoutSec 30
    Write-Output ("[OK]   GET /manifest    -> {0}  ({1} bytes)" -f $r.StatusCode, $r.Content.Length)
} catch { Write-Output "[FAIL] GET /manifest : $($_.Exception.Message)" }

try {
    $r = Invoke-WebRequest -Uri "$pub/js/app.js" -UseBasicParsing -TimeoutSec 30
    Write-Output ("[OK]   GET /js/app.js   -> {0}  ({1} bytes)" -f $r.StatusCode, $r.Content.Length)
} catch { Write-Output "[FAIL] GET /js/app.js : $($_.Exception.Message)" }

# 2. protected endpoints with token
Write-Output ""
Write-Output "--- 2. Protected endpoints (with token) ---"
$h = @{Authorization="Bearer $token"}

try {
    $r = Invoke-WebRequest -Uri "$pub/api/status" -Headers $h -UseBasicParsing -TimeoutSec 30
    Write-Output ("[OK]   GET /api/status  -> {0}" -f $r.StatusCode)
} catch { Write-Output "[FAIL] GET /api/status : $($_.Exception.Message)" }

try {
    $r = Invoke-WebRequest -Uri "$pub/api/sounds" -Headers $h -UseBasicParsing -TimeoutSec 30
    Write-Output ("[OK]   GET /api/sounds  -> {0}  ({1} bytes)" -f $r.StatusCode, $r.Content.Length)
} catch { Write-Output "[FAIL] GET /api/sounds : $($_.Exception.Message)" }

try {
    $r = Invoke-WebRequest -Uri "$pub/api/history?range_=week" -Headers $h -UseBasicParsing -TimeoutSec 30
    Write-Output ("[OK]   GET /api/history -> {0}  ({1} bytes)" -f $r.StatusCode, $r.Content.Length)
} catch { Write-Output "[FAIL] GET /api/history : $($_.Exception.Message)" }

# 3. WebSocket test (using .NET ClientWebSocket)
Write-Output ""
Write-Output "--- 3. WebSocket via public URL ---"
try {
    $ws = New-Object System.Net.WebSockets.ClientWebSocket
    $ct = New-Object System.Threading.CancellationTokenSource(15000)
    $task = $ws.ConnectAsync("$pub/ws?token=$token" -replace "^http", "ws", $ct.Token)
    $task.Wait(15000) | Out-Null
    if ($ws.State -eq "Open") {
        Write-Output "[OK]   WS connected"
        # Wait briefly for any pushed message
        Start-Sleep -Milliseconds 1500
        $buf = New-Object byte[] 8192
        $seg = [ArraySegment[byte]]::new($buf)
        $rtask = $ws.ReceiveAsync($seg, $ct.Token)
        if ($rtask.Wait(3000)) {
            $msg = [System.Text.Encoding]::UTF8.GetString($buf, 0, $rtask.Result.Count)
            $preview = if ($msg.Length -gt 120) { $msg.Substring(0,120) + "..." } else { $msg }
            Write-Output "[OK]   WS received: $preview"
        } else {
            Write-Output "[WARN] WS no message in 3s (acceptable if quiet)"
        }
        $ct2 = New-Object System.Threading.CancellationTokenSource(3000)
        $ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "bye", $ct2.Token).Wait(3000) | Out-Null
    } else {
        Write-Output "[FAIL] WS state = $($ws.State)"
    }
} catch {
    Write-Output "[FAIL] WS: $($_.Exception.Message)"
    if ($_.Exception.InnerException) { Write-Output "        Inner: $($_.Exception.InnerException.Message)" }
}
