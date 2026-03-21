# ==========================================
# GameGen Plugin Installer & Updater
# ==========================================

$ErrorActionPreference = "Stop"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "   GameGen Plugin Installer Started  " -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 1. Locate Steam Installation Directory
Write-Host "[1/5] Locating Steam installation..." -ForegroundColor Yellow
$steamPath = (Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam" -Name "InstallPath" -ErrorAction SilentlyContinue).InstallPath
if ([string]::IsNullOrEmpty($steamPath)) {
    $steamPath = (Get-ItemProperty -Path "HKCU:\SOFTWARE\Valve\Steam" -Name "SteamPath" -ErrorAction SilentlyContinue).SteamPath
}

if ([string]::IsNullOrEmpty($steamPath)) {
    Write-Host "Warning: Could not automatically detect Steam from Registry." -ForegroundColor Red
    $steamPath = "C:\Program Files (x86)\Steam"
    Write-Host "Falling back to default location: $steamPath" -ForegroundColor DarkGray
} else {
    Write-Host "Found Steam at: $steamPath" -ForegroundColor Green
}

$pluginsDir = Join-Path $steamPath "plugins"

# 2. Check for Millennium and install if missing
Write-Host ""
Write-Host "[2/5] Checking for Millennium Framework..." -ForegroundColor Yellow
if (-not (Test-Path $pluginsDir)) {
    Write-Host "Millennium is not installed (plugins directory missing)." -ForegroundColor Red
    Write-Host "Downloading MillenniumInstaller-Windows.exe..." -ForegroundColor Cyan
    
    $installerUrl = "https://github.com/SteamClientHomebrew/Installer/releases/latest/download/MillenniumInstaller-Windows.exe"
    $installerPath = Join-Path $env:TEMP "MillenniumInstaller-Windows.exe"
    
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
    
    Write-Host "`n*** ACTION REQUIRED ***" -ForegroundColor Magenta
    Write-Host "The Millennium installer has been launched." -ForegroundColor White
    Write-Host "Please follow the GUI installation steps. The script will wait until you close the installer." -ForegroundColor White
    
    # Launch and wait
    Start-Process -FilePath $installerPath -Wait -PassThru | Out-Null
    
    # Re-check after installation closes
    if (-not (Test-Path $pluginsDir)) {
        Write-Host "Installation cancelled or failed. Steam\plugins directory still missing." -ForegroundColor Red
        Write-Host "Aborting GameGen installation." -ForegroundColor Red
        Pause
        exit
    } else {
        Write-Host "Millennium framework has been successfully installed!" -ForegroundColor Green
    }
} else {
    Write-Host "Millennium is already installed." -ForegroundColor Green
}

# 3. Create target directory
Write-Host ""
Write-Host "[3/5] Setting up GameGenPlugin directory..." -ForegroundColor Yellow
$gameGenPluginDir = Join-Path $pluginsDir "GameGenPlugin"
if (-not (Test-Path $gameGenPluginDir)) {
    New-Item -ItemType Directory -Force -Path $gameGenPluginDir | Out-Null
    Write-Host "Created target directory: $gameGenPluginDir" -ForegroundColor DarkGray
}

# 4. Download and Extract GameGenPlugin Source
Write-Host ""
Write-Host "[4/5] Downloading GameGenPlugin from GitHub repository..." -ForegroundColor Yellow
$zipUrl = "https://github.com/TheMich157/GameGenPlugin/archive/refs/heads/main.zip"
$zipPath = Join-Path $env:TEMP "GameGenPlugin-main.zip"
$extractDir = Join-Path $env:TEMP "GameGenPlugin-Extraction"

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
if (Test-Path $extractDir) { Remove-Item -Recurse -Force $extractDir }

Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
Write-Host "Download complete. Extracting files..." -ForegroundColor DarkGray

New-Item -ItemType Directory -Force -Path $extractDir | Out-Null
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

# 5. Locate 'backend' folder skipping nested empty roots
Write-Host ""
Write-Host "[5/5] Searching for core plugin directories..." -ForegroundColor Yellow
$backendFolder = Get-ChildItem -Path $extractDir -Recurse -Directory -Filter "backend" | Select-Object -First 1

if ($null -ne $backendFolder) {
    # The parent of the 'backend' folder is the True Root of the repo 
    # (containing both backend/ and public/ usually alongside plugin.json)
    $sourceDir = $backendFolder.Parent.FullName
    Write-Host "Valid source root found at: $sourceDir" -ForegroundColor DarkGray
    
    Write-Host "Injecting files to Steam plugins directory..." -ForegroundColor Cyan
    Copy-Item -Path "$sourceDir\*" -Destination $gameGenPluginDir -Recurse -Force
    
    Write-Host "Cleanup..." -ForegroundColor DarkGray
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $extractDir -ErrorAction SilentlyContinue
    
    Write-Host ""
    Write-Host "=================================================" -ForegroundColor Green
    Write-Host "✨ GameGen Plugin successfully installed/updated!" -ForegroundColor Green
    Write-Host "Restart Steam to fully load the new files." -ForegroundColor Green
    Write-Host "=================================================" -ForegroundColor Green
} else {
    Write-Host "Error: Could not locate 'backend' directory within the downloaded ZIP." -ForegroundColor Red
    Write-Host "Is the repository structure correct?" -ForegroundColor Red
}

Write-Host ""
Write-Host "Press any key to exit..."
$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
