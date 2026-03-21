# GameGen Plugin Auto-Updater (Improved v3.4.2)
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

    Write-Host "4. Installing update..." -ForegroundColor Green
    
    # Files/Folders to update
    $items = Get-ChildItem -Path $extractedSource
    foreach ($item in $items) {
        $dest = Join-Path $currentPath $item.Name
        if ($item.PSIsContainer) {
            Copy-Item -Path $item.FullName -Destination $currentPath -Recurse -Force
        } else {
            Copy-Item -Path $item.FullName -Destination $dest -Force
        }
        Write-Host "Updated: $($item.Name)" -ForegroundColor Gray
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
