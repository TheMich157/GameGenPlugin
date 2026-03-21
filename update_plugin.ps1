# GameGen Plugin Auto-Updater (Improved v3.4.4)
# ---------------------------
# Pulls the latest files from GitHub, terminates Steam, applies update, and restarts.

$repoUrl = "https://github.com/TheMich157/GameGenPlugin/archive/refs/heads/main.zip"
$tempZip = "update.zip"
$tempFolder = "temp_update"
$currentPath = (Get-Item .).FullName

Write-Host "1. Downloading latest update..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $repoUrl -OutFile $tempZip -TimeoutSec 60

Write-Host "2. Extracting files..." -ForegroundColor Cyan
Expand-Archive -Path $tempZip -DestinationPath $tempFolder -Force

# Locate the extracted folder (GitHub adds the branch/repo name to the folder)
$extractedSource = Get-ChildItem -Path $tempFolder | Select-Object -ExpandProperty FullName

if (Test-Path $extractedSource) {
    Write-Host "3. Stopping Steam..." -ForegroundColor Yellow
    Stop-Process -Name "steam" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3 # Wait for it to close

    Write-Host "4. Installing update (clean install)..." -ForegroundColor Green
    
    # Logic to locate the plugin folder accurately
    $steamExe = (Get-ItemProperty -Path "HKCU:\Software\Valve\Steam" -Name "SteamExe").SteamExe
    if (Test-Path $steamExe) {
        $steamDir = Split-Path -Path $steamExe -Parent
        $pluginsDir = Join-Path -Path $steamDir -ChildPath "plugins\GameGenPlugin"
        if (Test-Path $pluginsDir) {
           $currentPath = $pluginsDir
        }
    }
    
    # Ensure we are in the GameGenPlugin directory
    if (-not (Test-Path (Join-Path $currentPath "public\gamegen.js"))) {
        Write-Host "Warning: Could not localize gamegen.js at $currentPath. Using identified path if possible." -ForegroundColor Yellow
    }

    # Define files/folders to preserve (only config.json as requested)
    $preserve = @("config.json")
    
    # Remove everything else in current path (except config.json)
    Write-Host "Clearing old files at $currentPath..." -ForegroundColor Gray
    Get-ChildItem -Path $currentPath | Where-Object { $preserve -notcontains $_.Name } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    # Install update by copying contents of extracted source (excluding config.json)
    Write-Host "Copying new files from $extractedSource..." -ForegroundColor Gray
    # Filter out config.json to ensure local user config is never overwritten by the update
    Get-ChildItem -Path $extractedSource | Where-Object { $_.Name -ne "config.json" } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $currentPath -Recurse -Force
    }
    
    Write-Host "Update applied!" -ForegroundColor Green
}

# Cleanup
Remove-Item -Path $tempZip -Force -ErrorAction SilentlyContinue
Remove-Item -Path $tempFolder -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "5. Restarting Steam..." -ForegroundColor Yellow
# Relaunch Steam via Registry
$steamExe = (Get-ItemProperty -Path "HKCU:\Software\Valve\Steam" -Name "SteamExe").SteamExe
if (Test-Path $steamExe) {
    Start-Process -FilePath $steamExe -WindowStyle Hidden
} else {
    Write-Host "Could not find SteamExe to relaunch." -ForegroundColor Red
}

Write-Host "Update process complete!" -ForegroundColor Green
