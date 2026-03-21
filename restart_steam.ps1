# GameGen Steam Restarter (Silent Mode)
# ------------------------------------

$ErrorActionPreference = "SilentlyContinue"

# 1. Kill Steam
Stop-Process -Name "steam" -Force

# 2. Wait for it to clear from memory
$timeout = 10
while ((Get-Process "steam" -ErrorAction SilentlyContinue) -and ($timeout -gt 0)) {
    Start-Sleep -Seconds 1
    $timeout--
}

# 3. Locate SteamExe via Registry
$steamPath = (Get-ItemProperty -Path "HKCU:\Software\Valve\Steam" -Name "SteamExe").SteamExe

# 4. Fallback search if registry fails
if ($null -eq $steamPath -or -not (Test-Path $steamPath)) {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Steam\steam.exe",
        "C:\Program Files\Steam\steam.exe",
        "D:\Steam\steam.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $steamPath = $c; break }
    }
}

# 5. Relaunch silently
if (Test-Path $steamPath) {
    Start-Process -FilePath $steamPath -WindowStyle Hidden
}
