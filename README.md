# GameGen Plugin for Millennium 🎮✨

[![Version 4.0.0](https://img.shields.io/badge/version-4.0.0-blue.svg)](https://github.com/TheMich157/GameGenPlugin)
[![API](https://img.shields.io/badge/Powered_by-GameGen.lol-purple.svg)](https://gamegen.lol)

A powerful, native Steam plugin built on the [Millennium Framework](https://steambrew.app/) designed for generating, downloading, and injecting Steam game manifests directly via the **GameGen API**.

Bring instantaneous, seamless license injections straight to the Steam Store with a beautiful natively injected UI.

## 🌟 Features

- **Native Interface**: Injects a premium, dynamic UI right into the Steam client. Adds an "Add to GameGen" button seamlessly onto Store pages.
- **One-Click Generation**: Automatically triggers generation, unpacks ZIP archives, and safely deploys `.acf`, `.manifest`, and `.lua` dependencies into your Steam directories.
- **Automatic Smart Restarts**: Restarts Steam securely upon successful game manifest deployment, applying licenses on the fly.
- **Built-in Auto-Updater**: The backend regularly searches for new releases on GitHub and prepares background updates automatically.
- **Robust ZIP Engine**: Safely sanitizes Windows directory names and smartly bypasses unnecessary wrapper folders.

## 🚀 Installation

We provide an automated, foolproof installation script that ensures both Millennium and the plugin are securely configured.

### Method 1: One-Line Install Script (Recommended)

Open **PowerShell** and run the following command to automatically install and configure everything:

```powershell
irm https://raw.githubusercontent.com/TheMich157/GameGenPlugin/refs/heads/main/install.ps1 | iex
```

**What it does:**
   - Detects if you have the **Millennium Framework**. If not, it drops the GUI installer and pauses while you set it up.
   - Automatically downloads the absolute latest version of the plugin straight from the `main` branch.
   - Safely bypasses GitHub root folders and cleanly pastes the backend into your `[Steam]/plugins/GameGenPlugin` directory.
   - Restarts your Steam client to inject the UI!

### Method 2: Manual Installation

1. Install the [Millennium Framework](https://github.com/SteamClientHomebrew/Installer/releases/latest) globally.
2. Download the [Latest Release](https://github.com/TheMich157/GameGenPlugin/releases/latest) of GameGen Plugin.
3. Open your Steam directory (commonly `C:\Program Files (x86)\Steam`).
4. Navigate to `plugins` and create a new folder named `GameGenPlugin`.
5. Extract the contents of the ZIP explicitly into that folder. (Ensure that `backend`, `public`, and `plugin.json` exist at the absolute root of the `GameGenPlugin` folder).
6. Fully restart Steam.

## ⚙️ Configuration

1. Launch Steam after installing the plugin.
2. Click the floating **GameGen Launcher Icon** (gradient squared star) positioned in the bottom-right corner of the Steam client.
3. Access the **Settings Tab**.
4. Enter your personal **GameGen API Key** obtained via [GameGen.lol](https://gamegen.lol).
5. Toggle your preferred preferences (e.g., Auto-Restart on Install, Debug Logging).

## 🧰 How It Works

Once your API key is validated, navigating to **any Game Store Page** automatically updates the purchase element with an interactive **Add to GameGen** button.

1. **Request**: Calling the API locates game archives automatically.
2. **Extraction**: Safe sanitization and unpacking extracts the vital GameGen payloads:
   * **manifests** → `Steam/depotcache/[AppID].manifest`
   * **lualocks** → `Steam/config/stplug-in/[AppID].lua`
   * **acf triggers** → `Steam/steamapps/appmanifest_[AppID].acf`
3. **Finish**: Steam reloads, and the game behaves as natively owned!

## 📜 Support & API

Requires an active subscription or plan registered at [GameGen.lol](https://gamegen.lol) to successfully access generation endpoints. Ensure your tokens remain active.
