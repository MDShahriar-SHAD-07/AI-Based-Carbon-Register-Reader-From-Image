param(
  [int]$ApiPort = 8000,
  [int]$WebPort = 5500
)

Write-Host "Starting Resistor Reader..." -ForegroundColor Cyan

# --- Set env (edit your real key) ---
$env:GOOGLE_API_KEY = "YOUR_API_KEY"
$env:GEMINI_MODEL   = "gemini-2.5-flash"

# --- Activate venv ---
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot
$venv = Join-Path $scriptRoot "venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv } else { Write-Error "venv not found: $venv"; exit 1 }

# --- Detect LAN IP (fallback to localhost) ---
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
  Sort-Object InterfaceMetric |
  Select-Object -First 1 -ExpandProperty IPAddress)
if (-not $ip) { $ip = "127.0.0.1" }

# --- Start static server for /web in a new minimized window ---
$webDir = Join-Path (Split-Path $scriptRoot -Parent) "web"
if (Test-Path $webDir) {
  Write-Host "Serving frontend from: $webDir" -ForegroundColor Yellow
  Start-Process -WindowStyle Minimized powershell -ArgumentList "-NoProfile","-Command","cd `"$webDir`"; python -m http.server ${WebPort}"
} else {
  Write-Warning "Web folder not found at $webDir (frontend won't be served)"
}

# --- Print URLs (use ${} to avoid the ':' gotcha) ---
$frontendUrl = "http://${ip}:${WebPort}/index.html?api=http://${ip}:${ApiPort}"
Write-Host ""
Write-Host ("Backend:  http://{0}:{1}/" -f $ip, $ApiPort) -ForegroundColor Green
Write-Host ("Frontend: {0}" -f $frontendUrl) -ForegroundColor Green
Write-Host "(Same Wi-Fi on phone, open the Frontend URL)" -ForegroundColor DarkGray
Write-Host ""

# --- Run backend bound to LAN ---
# Ensure CORS in main.py allows your phone origin (or use allow_origins=['*'] for testing)
uvicorn main:app --host 0.0.0.0 --port ${ApiPort} --reload

