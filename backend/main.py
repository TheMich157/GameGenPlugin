import json
import os
import shutil
import urllib.request
import urllib.error
import re
import sys
import threading
import datetime
import zipfile
import time
import io
from typing import Any, Dict, Optional, List
import Millennium # type: ignore

try:
    import winreg
except ImportError:
    winreg = None

_STEAM_INSTALL_PATH = None
_UPDATE_THREAD = None
_LAST_UPDATE_MESSAGE = ""

GAMEGEN_BASE_URL = "https://gamegen.lol/api"
DEFAULT_API_KEY = ""
VERSION = "3.4.6"
REPO_OWNER = "TheMich157"
REPO_NAME = "GameGenPlugin"
UPDATE_CHECK_INTERVAL = 3600 * 2 # 2 hours

class Plugin:
    def __init__(self):
        self.api_key = DEFAULT_API_KEY
        self.config_path = ""
        self.history_path = ""
        # New Settings
        self.auto_restart_steam = False
        self.beta_updates = False
        self.debug_logging = True
        self.notification_duration = 6 # seconds
        
    def _find_steam_path(self) -> str:
       
        global _STEAM_INSTALL_PATH
        if _STEAM_INSTALL_PATH:
            return _STEAM_INSTALL_PATH

        path = None
        if sys.platform.startswith("win") and winreg is not None:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                    path, _ = winreg.QueryValueEx(key, "SteamPath")
            except Exception:
                pass

        if not path:
            try:
                path = Millennium.steam_path()
            except Exception:
                pass

        _STEAM_INSTALL_PATH = path
        return _STEAM_INSTALL_PATH or ""

    def _get_plugin_dir(self) -> str:
        # 1. Try current file context
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.exists(os.path.join(current_dir, "public")):
            return current_dir
            
        # 2. Try absolute path from Millennium if available
        try:
            steam_path = self._find_steam_path()
            mill_dir = os.path.join(steam_path, "plugins", "GameGenPlugin")
            if os.path.exists(mill_dir):
                return mill_dir
        except:
            pass
            
        # 3. Last resort fallback
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _log_debug(self, message: str):
        try:
            # We skip this only if explicitly False
            if hasattr(self, "debug_logging") and self.debug_logging == False:
                return
                
            plugin_dir = self._get_plugin_dir()
            debug_path = os.path.join(plugin_dir, "debug.txt")
            import datetime
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(debug_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {message}\n")
        except:
            pass
    def _init_debug_log(self):
        try:
            plugin_dir = self._get_plugin_dir()
            debug_path = os.path.join(plugin_dir, "debug.txt")
            self._log_debug(f"DEBUG: Initializing. Plugin path: {plugin_dir}")
            self._log_debug(f"DEBUG: Config path: {os.path.join(plugin_dir, 'config.json')}")
        except:
            pass

    def _inject_webkit_files(self):
        try:
            plugin_dir = self._get_plugin_dir()
            
            js_src = os.path.join(plugin_dir, "public", "gamegen.js")
            css_src = os.path.join(plugin_dir, "public", "gamegen.css")

            if not os.path.exists(js_src):
                self._log_debug(f"CRITICAL: Failed to locate public/gamegen.js inside {plugin_dir}")
                return

            steam_path = self._find_steam_path()
            steam_ui_dir = os.path.join(steam_path, "steamui", "gamegen_ui")
            os.makedirs(steam_ui_dir, exist_ok=True)
            
            js_dst = os.path.join(steam_ui_dir, "gamegen.js")
            css_dst = os.path.join(steam_ui_dir, "gamegen.css")
            
            shutil.copy(js_src, js_dst)
            if os.path.exists(css_src):
                shutil.copy(css_src, css_dst)
                
            # Millennium expects posix web paths explicitly!
            Millennium.add_browser_js("gamegen_ui/gamegen.js")
            Millennium.add_browser_css("gamegen_ui/gamegen.css")
            print("[GameGen] Injected gamegen webkit natively.")
        except Exception as e:
            self._log_debug(f"FAILED TO INJECT: {e}")
            print(f"[GameGen] Failed to inject webkit files: {e}")

    def _load(self):
        try:
            Millennium.ready()
            print(f"[GameGen] Plugin v{VERSION} initialized.")
            self._init_debug_log()
            
            plugin_dir = self._get_plugin_dir()
            self.config_path = os.path.abspath(os.path.join(plugin_dir, "config.json"))
            self.history_path = os.path.abspath(os.path.join(plugin_dir, "history.json"))
            self._log_debug(f"DEBUG: Paths initialized - Config: {self.config_path}, History: {self.history_path}")
            
            # Apply any pending updates first
            msg = self._apply_pending_update()
            if msg:
                global _LAST_UPDATE_MESSAGE
                _LAST_UPDATE_MESSAGE = msg
                print(f"[GameGen] Update note: {msg}")

            if os.path.exists(self.config_path):
                self._log_debug("DEBUG: Config found, loading...")
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.api_key = str(data.get("api_key", DEFAULT_API_KEY))
                        self.auto_restart_steam = bool(data.get("auto_restart_steam", False))
                        self.beta_updates = bool(data.get("beta_updates", False))
                        self.debug_logging = bool(data.get("debug_logging", True))
                        self.notification_duration = int(data.get("notification_duration", 6))
                        self._log_debug("DEBUG: Config loaded successfully.")
                except Exception as e:
                    self._log_debug(f"Error loading config: {e}")
            else:
                 self._log_debug(f"DEBUG: No config found at {self.config_path}")
            
            self._inject_webkit_files()
            
            # Start background update checks
            self._start_update_thread()
                    
        except Exception as e:
            self._log_debug(f"init exception: {e}")
            print(f"[GameGen] init exception: {e}")

    def _apply_pending_update(self) -> str:
        """ Extract pending update if it exists """
        plugin_dir = self._get_plugin_dir()
        pending_zip = os.path.join(plugin_dir, "update_pending.zip")
        if os.path.exists(pending_zip):
            try:
                with zipfile.ZipFile(pending_zip, 'r') as z:
                    z.extractall(plugin_dir)
                os.remove(pending_zip)
                return "Latest update applied. Restart Steam to finish."
            except Exception as e:
                self._log_debug(f"Apply update failed: {e}")
        return ""

    def _start_update_thread(self):
        global _UPDATE_THREAD
        if _UPDATE_THREAD is None or not _UPDATE_THREAD.is_alive():
            _UPDATE_THREAD = threading.Thread(target=self._update_worker, daemon=True)
            _UPDATE_THREAD.start()

    def _update_worker(self):
        while True:
            try:
                time.sleep(60) # Fast check first time, then interval
                self._check_for_updates()
                time.sleep(UPDATE_CHECK_INTERVAL)
            except Exception as e:
                self._log_debug(f"Update worker error: {e}")
                time.sleep(300)

    def _check_for_updates(self, manual=False) -> str:
        try:
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
            headers = {"User-Agent": "GameGen-Plugin-Updater"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                remote_ver = data.get("tag_name", "").strip("v")
                
                if self._is_newer(remote_ver, VERSION):
                    self._log_debug(f"New version found: {remote_ver}")
                    assets = data.get("assets", [])
                    download_url = ""
                    for asset in assets:
                        if asset.get("name", "").endswith(".zip"):
                            download_url = asset.get("browser_download_url")
                            break
                    
                    if not download_url: # Fallback to source zip
                        download_url = data.get("zipball_url")
                    
                    if download_url:
                        ok = self._download_update(download_url)
                        msg = f"Update v{remote_ver} applied. Restart Steam to finish." if ok else f"Update v{remote_ver} download failed."
                        if not manual:
                            global _LAST_UPDATE_MESSAGE
                            _LAST_UPDATE_MESSAGE = msg
                        return msg
                elif manual:
                    return "Plugin is up to date."
        except Exception as e:
            self._log_debug(f"Check update failed: {e}")
            if manual: return f"Check failed: {e}"
        return ""

    def _is_newer(self, remote, local) -> bool:
        try:
            r_parts = [int(p) for p in remote.split(".")]
            l_parts = [int(p) for p in local.split(".")]
            return r_parts > l_parts
        except:
            return remote > local

    def _download_update(self, url: str) -> bool:
        plugin_dir = self._get_plugin_dir()
        data = self._download_with_retry(url, timeout=60)
        if data:
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    # Strip the leading directory (GitHub style)
                    for member in z.infolist():
                        filename = str(member.filename)
                        if '/' in filename:
                            # Strip the first part of the path (the repo folder)
                            prefix, rest = filename.split('/', 1)
                            member.filename = rest
                            
                        if not member.filename:
                            continue
                            
                        z.extract(member, plugin_dir)
                                
                self._log_debug(f"Update applied to {plugin_dir}")
                return True
            except Exception as e:
                self._log_debug(f"Update apply error: {e}")
        return False

    def _download_with_retry(self, url: str, timeout: int = 30, retries: int = 3) -> Optional[bytes]:
        """ Helper for robust downloads with retries for IncompleteRead etc. """
        import time
        import http.client
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GameGen-Plugin"}
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                    if data: return data
            except (urllib.error.URLError, ConnectionError, http.client.IncompleteRead, Exception) as e:
                self._log_debug(f"Download attempt {attempt+1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(1.5)
                else:
                    return None
        return None

    def _get_history(self) -> List[Dict[str, Any]]:
        if not self.history_path or not os.path.exists(self.history_path):
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except:
            return []

    def _add_to_history(self, app_id: str, name: str):
        if not self.history_path:
            return
            
        history = self._get_history()
        # Remove existing to move to top
        history = [item for item in history if isinstance(item, dict) and item.get("app_id") != app_id]
        
        timestamp = 0
        try:
            import time
            timestamp = int(time.time())
        except:
            pass
            
        history.insert(0, {"app_id": app_id, "name": name, "timestamp": timestamp})
        # Use while/pop as Pyre is having difficulty with slice and del on lists
        while len(history) > 50:
            history.pop()
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(history, f)
            print(f"[GameGen] Logged {name} ({app_id}) to history.")
        except Exception as e:
            print(f"[GameGen] HISTORY ERROR: {e}")

    def _parse_vdf(self, content: str) -> dict:
        """Simple VDF parser for libraryfolders.vdf."""
        data = {}
        stack = [data]
        import re
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("//"): continue
            if line == "{": continue
            if line == "}":
                if len(stack) > 1: stack.pop()
                continue
            
            matches = re.findall(r'"([^"]*)"', line)
            if len(matches) == 2:
                key, val = matches
                stack[-1][key] = val
            elif len(matches) == 1:
                key = matches[0]
                new_dict = {}
                stack[-1][key] = new_dict
                stack.append(new_dict)
        return data

    def _get_library_folders(self) -> List[str]:
        """Get all Steam library folders by parsing libraryfolders.vdf."""
        libraries = []
        try:
            steam_path = self._find_steam_path()
            libraries.append(steam_path) # Main library
            
            vdf_path = os.path.join(steam_path, "config", "libraryfolders.vdf")
            if os.path.exists(vdf_path):
                with open(vdf_path, "r", encoding="utf-8") as f:
                    vdf_data = self._parse_vdf(f.read())
                    
                folders = vdf_data.get("libraryfolders", {})
                for key in folders:
                    if isinstance(folders[key], dict):
                        path = folders[key].get("path")
                        if path and os.path.exists(path):
                            path = os.path.normpath(path)
                            if path not in libraries:
                                libraries.append(path)
        except Exception as e:
            print(f"[GameGen] Library folders error: {e}")
            
        return libraries

    def _find_app_paths(self, app_id: str) -> Dict[str, Any]:
        """Find where an app is installed among all libraries."""
        app_id_str = str(app_id).strip()
        libraries = self._get_library_folders()
        steam_path = self._find_steam_path()
        self._log_debug(f"DEBUG: Starting path search for AppID {app_id_str}. Library folders: {libraries}")
        
        # User specified system-wide paths
        depotcache_dir = os.path.join(steam_path, "depotcache")
        stplugin_config_dir = os.path.join(steam_path, "config", "stplug-in")
        
        # Priority system-wide files
        sys_manifest = os.path.join(depotcache_dir, f"{app_id_str}.manifest")
        sys_lua = os.path.join(stplugin_config_dir, f"{app_id_str}.lua")
        
        for lib in libraries:
            steamapps = os.path.join(lib, "steamapps")
            acf = os.path.join(steamapps, f"appmanifest_{app_id_str}.acf")
            self._log_debug(f"DEBUG: Checking {lib} -> ACF: {acf}")
            
            # If any of these exist, the app is "installed" via GameGen
            if os.path.exists(sys_manifest) or os.path.exists(sys_lua) or os.path.exists(acf):
                self._log_debug(f"DEBUG: Found existing files at {lib}")
                return {
                    "library_path": lib,
                    "steamapps_path": steamapps,
                    "acf_path": acf,
                    "manifest_path": sys_manifest,
                    "lua_path": sys_lua,
                    "exists": True
                }
                
        # Default to main library if not found
        main_lib = self._find_steam_path()
        main_steamapps = os.path.join(main_lib, "steamapps")
        default_acf = os.path.join(main_steamapps, f"appmanifest_{app_id_str}.acf")
        self._log_debug(f"DEBUG: No install found. Defaulting to: {default_acf}")
        return {
            "library_path": main_lib,
            "steamapps_path": main_steamapps,
            "acf_path": default_acf,
            "manifest_path": sys_manifest,
            "lua_path": sys_lua,
            "exists": False
        }

    def _front_end_loaded(self):
        try:
            self._inject_webkit_files()
        except Exception as e:
            print(f"[GameGen] frontend loaded exception: {e}")

    def _write_acf(self, z: "zipfile.ZipFile", name: str, pure_name: str, steamapps_dir: str) -> bool:
        try:
            acf_data = z.read(name)
            out_path = os.path.join(steamapps_dir, pure_name)
            with open(out_path, "wb") as f:
                f.write(acf_data)
            self._log_debug(f"DEBUG: ✅ Success Extract ACF -> {out_path}")
            return True
        except Exception as e:
            self._log_debug(f"DEBUG: ❌ FAIL Extract ACF {pure_name}: {e}")
            return False

    def _write_manifest(self, z: "zipfile.ZipFile", name: str, pure_name: str, depotcache_dir: str) -> bool:
        try:
            m_data = z.read(name)
            out_path = os.path.join(depotcache_dir, pure_name)
            with open(out_path, "wb") as f:
                f.write(m_data)
            self._log_debug(f"DEBUG: ✅ Success Extract Manifest -> {out_path}")
            return True
        except Exception as e:
            self._log_debug(f"DEBUG: ❌ FAIL Extract Manifest {pure_name}: {e}")
            return False

    def _write_lua(self, z: "zipfile.ZipFile", name: str, pure_name: str, app_id_str: str, stplugin_dir: str) -> bool:
        try:
            lua_data = z.read(name)
            dest_lua = os.path.join(stplugin_dir, f"{app_id_str}.lua")
            with open(dest_lua, "wb") as lf:
                lf.write(lua_data)
            self._log_debug(f"DEBUG: ✅ Success Extract LUA -> {dest_lua}")
            return True
        except Exception as e:
            self._log_debug(f"DEBUG: ❌ FAIL Extract LUA {pure_name}: {e}")
            return False

    def _extract_zip_contents(self, zip_data: bytes, app_id_str: str, game_target_dir: str, steamapps_dir: str):
        """ Robustly extract ACF, Manifest, and Lua files from ANY folder inside the ZIP """
        self._log_debug(f"DEBUG: EXTENSIVE EXTRACTION STARTED for AppID {app_id_str}")
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                z.extractall(game_target_dir)
                names = z.namelist()
                self._log_debug(f"DEBUG: Total files in ZIP: {len(names)}. Full list: {names}")

                steam_path = self._find_steam_path()
                depotcache_dir = os.path.join(steam_path, "depotcache")
                stplugin_dir = os.path.join(steam_path, "config", "stplug-in")
                os.makedirs(depotcache_dir, exist_ok=True)
                os.makedirs(stplugin_dir, exist_ok=True)
                self._log_debug(f"DEBUG: Paths - depotcache: {depotcache_dir}, stplug-in: {stplugin_dir}")

                for name in names:
                    pure_name = os.path.basename(name)
                    
                    # A. Extract ACF files to steamapps (Primary discovery)
                    is_acf = pure_name.endswith(".acf") and (pure_name.startswith("appmanifest_") or app_id_str in pure_name)
                    if is_acf:
                        self._log_debug(f"DEBUG: IDENTIFIED ACF inside Zip: {name}")
                        if self._write_acf(z, name, pure_name, steamapps_dir):
                            self._log_debug(f"DEBUG: Saved ACF to {steamapps_dir}")

                    # B. Extract Manifest files to depotcache
                    is_manifest = pure_name.endswith(".manifest")
                    if is_manifest:
                        self._log_debug(f"DEBUG: IDENTIFIED MANIFEST inside Zip: {name}")
                        if self._write_manifest(z, name, pure_name, depotcache_dir):
                            self._log_debug(f"DEBUG: Saved Manifest to {depotcache_dir}")

                    # C. Extract LUA scripts to stplug-in
                    is_lua = pure_name.endswith(".lua")
                    if is_lua:
                        self._log_debug(f"DEBUG: IDENTIFIED LUA inside Zip: {name}")
                        # If it matches appid or is the only one, or contains "script"
                        is_match = (app_id_str in pure_name) or (len([n for n in names if n.lower().endswith(".lua")]) == 1) or ("script" in pure_name.lower())
                        if is_match:
                            if self._write_lua(z, name, pure_name, app_id_str, stplugin_dir):
                                self._log_debug(f"DEBUG: Saved LUA to {stplugin_dir}")

                self._log_debug("DEBUG: Extraction process finished.")
        except Exception as e:
            self._log_debug(f"🛑 ZIP EXTRACTION GLOBAL INTERRUPT: {e}")

plugin = Plugin()

def _make_request(url: str, method: str = "GET", body: Optional[Dict] = None) -> Dict:
    req = urllib.request.Request(url, method=method)
    req.add_header('User-Agent', f'GameGen-Millennium-Plugin/{VERSION}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    
    data = None
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        
    try:
        with urllib.request.urlopen(req, data=data, timeout=10) as response:
            res_body = response.read().decode('utf-8')
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode('utf-8')
            return json.loads(err_body)
        except Exception:
            return {"error": f"HTTP Error {e.code}"}
    except Exception as e:
        return {"error": str(e)}

def set_api_key(key: str, contentScriptQuery: str = "") -> str:
    try:
        plugin._log_debug(f"DEBUG: set_api_key called with length {len(key)}")
        plugin.api_key = key
        save_config()
        return json.dumps({"success": True})
    except Exception as e:
        plugin._log_debug(f"DEBUG: set_api_key error: {e}")
        return json.dumps({"success": False, "error": str(e)})

def update_settings(settings: Any = None, **kwargs) -> str:
    try:
        raw_data = settings if settings is not None else kwargs.get("settings", kwargs)
        
        # Determine the final dictionary to work with
        if isinstance(raw_data, str) and raw_data:
            try:
                data = json.loads(raw_data)
            except:
                return json.dumps({"success": False, "error": "Invalid JSON format in settings"})
        elif isinstance(raw_data, dict):
            data = raw_data
        else:
            return json.dumps({"success": False, "error": f"Unexpected data type: {type(raw_data)}"})
            
        # If payload is wrapped in another 'settings' key
        if isinstance(data, dict) and "settings" in data:
            data = data["settings"]
            
        if not isinstance(data, dict):
             return json.dumps({"success": False, "error": "Settings payload must be a dictionary"})

        # Apply settings with type safety
        if "api_key" in data:
            plugin.api_key = str(data["api_key"])
        if "auto_restart_steam" in data:
            plugin.auto_restart_steam = bool(data["auto_restart_steam"])
        if "beta_updates" in data:
            plugin.beta_updates = bool(data["beta_updates"])
        if "debug_logging" in data:
            plugin.debug_logging = bool(data["debug_logging"])
        if "notification_duration" in data:
            try:
                val = int(data["notification_duration"])
                if 0 < val < 3600:
                    plugin.notification_duration = val
            except:
                pass
        
        plugin._log_debug(f"DEBUG: Applied settings update. New key len: {len(plugin.api_key)}")
        save_config()
        return json.dumps({"success": True})
    except Exception as e:
        plugin._log_debug(f"CRITICAL ERROR in update_settings: {e}")
        return json.dumps({"success": False, "error": str(e)})

def get_settings(contentScriptQuery: str = "") -> str:
    return json.dumps({
        "api_key": plugin.api_key,
        "auto_restart_steam": plugin.auto_restart_steam,
        "beta_updates": plugin.beta_updates,
        "debug_logging": plugin.debug_logging,
        "notification_duration": plugin.notification_duration
    })

def save_config():
    try:
        if not plugin.config_path:
            p_dir = plugin._get_plugin_dir()
            plugin.config_path = os.path.abspath(os.path.join(p_dir, "config.json"))
            
        data_to_save = {
            "api_key": plugin.api_key,
            "auto_restart_steam": plugin.auto_restart_steam,
            "beta_updates": plugin.beta_updates,
            "debug_logging": plugin.debug_logging,
            "notification_duration": plugin.notification_duration
        }
        plugin._log_debug(f"DEBUG: Writing config to {plugin.config_path} with data: {data_to_save}")
        
        with open(plugin.config_path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4)
        plugin._log_debug("DEBUG: Config saved successfully.")
    except Exception as e:
        plugin._log_debug(f"FAILED TO SAVE CONFIG: {e}")
        raise e



def generate_manifest(app_id: str, contentScriptQuery: str = "") -> str:
    try:
        app_id_str = str(app_id).strip()
        if not plugin.api_key:
            return json.dumps({"success": False, "error": "API key not configured"})
            
        # Use new library detection logic
        paths = plugin._find_app_paths(app_id_str)
        steamapps_dir = paths["steamapps_path"]
        acf_path = paths["acf_path"]
        already_existed = paths["exists"]

        url = f"{GAMEGEN_BASE_URL}/{plugin.api_key}/generate/{app_id_str}"
        plugin._log_debug(f"Requesting generation for {app_id_str} from {url}")
        result = _make_request(url, method="GET")
        
        if not result.get("success"):
            plugin._log_debug(f"API Error for {app_id_str}: {result}")
            return json.dumps(result)
            
        m = result.get("manifest", {})
        game_name = m.get("name") or result.get("name") or f"App {app_id_str}"
        download_url = m.get("downloadUrl") or m.get("download_url") or m.get("url") or m.get("fileUrl")
        
        # New ZIP logic
        zip_url = result.get("zipUrl") or result.get("zip_url") or m.get("zipUrl") or m.get("zip_url") or result.get("content_url")
        installdir = m.get("installdir") or m.get("install_dir") or game_name
        
        manifest_installed = False
        zip_installed = False

        # 1. ZIP Processing / Game Content (contains .lua and .manifest and game files)
        if zip_url:
            try:
                common_dir = os.path.join(steamapps_dir, "common")
                game_target_dir = os.path.join(common_dir, installdir)
                os.makedirs(game_target_dir, exist_ok=True)
                
                plugin._log_debug(f"Downloading ZIP: {zip_url}")
                
                zip_data = plugin._download_with_retry(zip_url, timeout=60)
                if zip_data:
                    plugin._extract_zip_contents(zip_data, app_id_str, game_target_dir, steamapps_dir)
                
                zip_installed = True
                plugin._log_debug(f"Successfully extracted ZIP for {app_id_str} to {game_target_dir}")
            except Exception as e:
                plugin._log_debug(f"ZIP extraction failed for {app_id_str}: {e}")
                result["_zip_error"] = str(e)

        # 2. Singular Manifest / Script Downloads
        # Support both consolidated and granular URLs
        acf_dl_url = m.get("acfUrl") or m.get("acf_url") or download_url
        manifest_dl_url = m.get("manifestUrl") or m.get("manifest_url")
        lua_dl_url = m.get("luaUrl") or m.get("lua_url")

        if acf_dl_url or manifest_dl_url or lua_dl_url:
            try:
                # Ensure directories exist
                os.makedirs(steamapps_dir, exist_ok=True)
                os.makedirs(os.path.dirname(paths["manifest_path"]), exist_ok=True)
                os.makedirs(os.path.dirname(paths["lua_path"]), exist_ok=True)
                
                # A. ACF
                if acf_dl_url:
                    data = plugin._download_with_retry(acf_dl_url, timeout=30)
                    if data:
                        with open(acf_path, 'wb') as f:
                            f.write(data)
                        manifest_installed = True
                        plugin._log_debug(f"Successfully saved .acf for {app_id_str}")

                # B. Manifest
                if manifest_dl_url:
                    m_data = plugin._download_with_retry(manifest_dl_url, timeout=30)
                    if m_data:
                        with open(paths["manifest_path"], 'wb') as f:
                            f.write(m_data)
                        plugin._log_debug(f"Successfully saved .manifest for {app_id_str}")

                # C. Lua
                if lua_dl_url:
                    l_data = plugin._download_with_retry(lua_dl_url, timeout=30)
                    if l_data:
                        with open(paths["lua_path"], 'wb') as f:
                            f.write(l_data)
                        plugin._log_debug(f"Successfully saved .lua for {app_id_str}")

            except Exception as e:
                plugin._log_debug(f"Granular manifest download failed for {app_id_str}: {e}")
                result["_manifest_error"] = str(e)
                
        # Update result and history if something was successful
        if manifest_installed or zip_installed:
            result["success"] = True # Force success if at least one part worked
            result["_auto_installed"] = manifest_installed
            result["_zip_installed"] = zip_installed
            result["_already_existed"] = already_existed
            result["_should_restart"] = plugin.auto_restart_steam
            plugin._add_to_history(app_id_str, game_name)
            plugin._log_debug(f"Generation workflow completed for {app_id_str}")
            
            if plugin.auto_restart_steam:
                plugin._log_debug("Auto-restarting Steam as requested by settings.")
                # We do this in a slight delay to ensure the API response is sent back to UI first
                threading.Timer(2.0, restart_steam).start()
                
        return json.dumps(result)
    except Exception as e:
        plugin._log_debug(f"generate_manifest global error: {e}")
        return json.dumps({"success": False, "error": str(e)})

def get_newly_added(contentScriptQuery: str = "") -> str:
    try:
        import time
        now = int(time.time())
        history = plugin._get_history()
        # Find games added in the last 15 minutes (900 seconds)
        new_games = [item for item in history if now - item.get("timestamp", 0) < 900]
        return json.dumps({"success": True, "games": new_games})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def get_history(contentScriptQuery: str = "") -> str:
    return json.dumps(plugin._get_history())

def clear_history(contentScriptQuery: str = "") -> str:
    try:
        if os.path.exists(plugin.history_path):
            os.remove(plugin.history_path)
        return json.dumps({"success": True})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


def request_game(app_id: str, reason: str = "", contentScriptQuery: str = "") -> str:
    try:
        app_id_str = str(app_id)
        if not plugin.api_key:
            return json.dumps({"success": False, "error": "API key not configured"})
            
        url = f"{GAMEGEN_BASE_URL}/{plugin.api_key}/request/{app_id_str}"
        payload = {"reason": reason or "User request via GameGen plugin"}
        result = _make_request(url, method="POST", body=payload)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def uninstall_manifest(app_id: str, contentScriptQuery: str = "") -> str:
    try:
        app_id_str = str(app_id).strip()
        paths = plugin._find_app_paths(app_id_str)
        
        if not paths["exists"]:
            return json.dumps({"success": False, "error": "No manifest or affiliated files found for this App ID."})
            
        # Files to remove for a complete cleanup
        files_to_remove = [paths["acf_path"], paths["manifest_path"], paths["lua_path"]]
        
        any_removed = False
        for file_path in files_to_remove:
            if os.path.exists(file_path):
                os.remove(file_path)
                any_removed = True
                
        if any_removed:
            # Clean from history
            history = plugin._get_history()
            history = [item for item in history if item.get("app_id") != app_id_str]
            try:
                with open(plugin.history_path, "w", encoding="utf-8") as f:
                    json.dump(history, f)
            except:
                pass
            return json.dumps({"success": True})
        return json.dumps({"success": False, "error": "No manifest or affiliated files found for this App ID."})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def update_plugin(contentScriptQuery: str = "") -> str:
    try:
        import subprocess
        plugin_dir = plugin._get_plugin_dir()
        script_path = os.path.join(plugin_dir, "update_plugin.ps1")
        
        if os.path.exists(script_path):
            print(f"[GameGen] Updating plugin via fixed script: {script_path}")
            # Run PowerShell script without waiting (using 0x08000000 which is CREATE_NO_WINDOW on Windows)
            subprocess.Popen(["powershell.exe", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", script_path], 
                             creationflags=0x08000000)
            return json.dumps({"success": True, "message": "Manual update started. Steam will restart shortly."})
        else:
            msg = plugin._check_for_updates(manual=True)
            return json.dumps({"success": True, "message": msg or "Checking for updates..."})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def get_update_notification(contentScriptQuery: str = "") -> str:
    global _LAST_UPDATE_MESSAGE
    msg = _LAST_UPDATE_MESSAGE
    _LAST_UPDATE_MESSAGE = ""
    return json.dumps({"message": msg})

def restart_steam(contentScriptQuery: str = "") -> str:
    try:
        import subprocess
        plugin_dir = plugin._get_plugin_dir()
        script_path = os.path.join(plugin_dir, "restart_steam.ps1")
        
        if os.path.exists(script_path):
            print(f"[GameGen] Restarting Steam via custom script: {script_path}")
            # Run PowerShell script silently (using 0x08000000 which is CREATE_NO_WINDOW on Windows)
            subprocess.Popen(["powershell.exe", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", script_path], 
                             creationflags=0x08000000)
            return json.dumps({"success": True, "method": "powershell"})
        else:
            # Fallback to internal method if script is missing
            Millennium.restart()
            return json.dumps({"success": True, "method": "internal"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

def check_manifest_exists(app_id: str, contentScriptQuery: str = "") -> str:
    try:
        app_id_str = str(app_id).strip()
        paths = plugin._find_app_paths(app_id_str)
        
        return json.dumps({
            "exists": paths["exists"],
            "has_manifest": os.path.exists(paths["manifest_path"]),
            "has_lua": os.path.exists(paths["lua_path"]),
            "has_acf": os.path.exists(paths["acf_path"]),
            "library": paths["library_path"]
        })
    except Exception as e:
        return json.dumps({"exists": False, "error": str(e)})

def get_stats(contentScriptQuery: str = "") -> str:
    try:
        if not plugin.api_key:
            return json.dumps({"success": False, "error": "API key not configured"})
            
        # Try /usage first as it's more detailed, fallback to /stats
        url = f"{GAMEGEN_BASE_URL}/{plugin.api_key}/usage"
        result = _make_request(url, method="GET")
        
        # If /usage fails or isn't what we expect, try /stats
        if not result.get("success") or "data" not in result:
            url = f"{GAMEGEN_BASE_URL}/{plugin.api_key}/stats"
            result = _make_request(url, method="GET")

        # Parse according to documentation
        data = result.get("data", {})
        rate_limit = result.get("rateLimit", {})
        
        remaining = data.get("remaining") or rate_limit.get("remaining") or result.get("remaining") or 0
        limit = data.get("dailyLimit") or rate_limit.get("limit") or result.get("limit") or "∞"
        
        return json.dumps({
            "success": True,
            "remaining": remaining,
            "limit": limit,
            "total_requests": data.get("totalRequests", 0),
            "today_usage": data.get("todayUsage", 0),
            "error": result.get("error") if not result.get("success") else None
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "remaining": 0, "limit": "∞"})

# Initialize plugin state on startup
try:
    plugin._load()
except Exception as e:
    print(f"[GameGen] Failed to auto-initialize: {e}")

