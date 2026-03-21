# GameGen Plugin Auto-Updater
# ---------------------------
# Pulls the latest files from GitHub, preserves local data, and restarts Steam.

$repoUrl = "https://github.com/TheMich157/GameGenPlugin/archive/refs/heads/main.zip"
$tempZip = "update.zip"
$tempFolder = "temp_update"
$currentPath = (Get-Item .).FullName

Write-Host "Downloading latest update..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $repoUrl -OutFile $tempZip

Write-Host "Extracting files..." -ForegroundColor Cyan
Expand-Archive -Path $tempZip -DestinationPath $tempFolder -Force

# Determine the extracted folder name (usually RepoName-BranchName)
$extractedDir = Get-ChildItem -Path $tempFolder | Select-Object -ExpandProperty FullName

if (Test-Path $extractedDir) {
    Write-Host "Installing update..." -ForegroundColor Green
    
    # Files/Folders to update
    $toUpdate = @("backend", "public", "plugin.json", "restart_steam.ps1", "webkit")
    
    foreach ($item in $toUpdate) {
        $source = Join-Path $extractedDir $item
        if (Test-Path $source) {
            Copy-Item -Path $source -Destination $currentPath -Recurse -Force
            Write-Host "Updated: $item" -ForegroundColor Gray
        }
    }
    
    Write-Host "Update complete! Cleaning up..." -ForegroundColor Cyan
}

# Cleanup
Remove-Item -Path $tempZip -Force
Remove-Item -Path $tempFolder -Recurse -Force

Write-Host "Restarting Steam to apply changes..." -ForegroundColor Yellow
# Call the restart script in the current folder
& "$currentPath\restart_steam.ps1"
