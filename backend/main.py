import json
import os
import shutil
import urllib.request
import urllib.error
from typing import Any
import Millennium # type: ignore

GAMEGEN_BASE_URL = "https://gamegen.lol/api"
DEFAULT_API_KEY = ""
VERSION = "3.3.0"

class Plugin:
    def __init__(self):
        self.api_key = DEFAULT_API_KEY
        self.config_path = ""
        self.history_path = ""
        
    def _get_plugin_dir(self) -> str:
        # 1. Try current file context
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.exists(os.path.join(current_dir, "public")):
            return current_dir
            
        # 2. Try absolute path from Millennium if available
        try:
            mill_dir = os.path.join(Millennium.steam_path(), "plugins", "GameGenPlugin")
            if os.path.exists(mill_dir):
                return mill_dir
        except:
            pass
            
        # 3. Last resort fallback
        return os.path.dirname(os.path.abspath(__file__))

    def _inject_webkit_files(self):
        try:
            plugin_dir = self._get_plugin_dir()
            
            js_src = os.path.join(plugin_dir, "public", "gamegen.js")
            css_src = os.path.join(plugin_dir, "public", "gamegen.css")

            if not os.path.exists(js_src):
                with open(os.path.join(plugin_dir, "debug.txt"), "a") as f:
                    f.write(f"CRITICAL: Failed to locate public/gamegen.js inside {plugin_dir}\n")
                return

            steam_ui_dir = os.path.join(Millennium.steam_path(), "steamui", "gamegen_ui")
            os.makedirs(steam_ui_dir, exist_ok=True)
            
            js_dst = os.path.join(steam_ui_dir, "gamegen.js")
            css_dst = os.path.join(steam_ui_dir, "gamegen.css")
            
            shutil.copy(js_src, js_dst)
            if os.path.exists(css_src):
                shutil.copy(css_src, css_dst)
                
            # Millennium expects posix web paths explicitly!
            Millennium.add_browser_js("gamegen_ui/gamegen.js")
            
            try:
                Millennium.add_browser_css("gamegen_ui/gamegen.css")
            except Exception as e:
                with open(os.path.join(plugin_dir, "debug.txt"), "a") as f:
                    f.write(f"add browser css exception: {e}\n")
            print("[GameGen] Injected gamegen webkit natively.")
        except Exception as e:
            plugin_log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            with open(os.path.join(plugin_log_dir, "debug.txt"), "a") as f:
                f.write(f"FAILED TO INJECT: {e}\n")
            print(f"[GameGen] Failed to inject webkit files: {e}")

    def _load(self):
        try:
            Millennium.ready()
            print("[GameGen] Python plugin initialized.")
            
            plugin_dir = self._get_plugin_dir()
            self.config_path = os.path.join(plugin_dir, "config.json")
            self.history_path = os.path.join(plugin_dir, "history.json")
            
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.api_key = data.get("api_key", DEFAULT_API_KEY)
                except Exception as e:
                    print(f"[GameGen] Error loading config: {e}")
            
            self._inject_webkit_files()
                    
        except Exception as e:
            print(f"[GameGen] init exception: {e}")

    def _get_history(self) -> list[dict[str, Any]]:
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

    def _get_library_folders(self) -> list[str]:
        """Get all Steam library folders by parsing libraryfolders.vdf."""
        libraries = []
        try:
            steam_path = Millennium.steam_path()
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

    def _find_app_paths(self, app_id: str) -> dict[str, Any]:
        """Find where an app is installed among all libraries."""
        app_id_str = str(app_id).strip()
        libraries = self._get_library_folders()
        
        for lib in libraries:
            steamapps = os.path.join(lib, "steamapps")
            manifest = os.path.join(steamapps, f"{app_id_str}.manifest")
            lua = os.path.join(steamapps, f"{app_id_str}.lua")
            acf = os.path.join(steamapps, f"appmanifest_{app_id_str}.acf")
            
            if os.path.exists(manifest) or os.path.exists(lua) or os.path.exists(acf):
                return {
                    "library_path": lib,
                    "steamapps_path": steamapps,
                    "manifest_path": manifest,
                    "lua_path": lua,
                    "acf_path": acf,
                    "exists": True
                }
                
        # Default to main library if not found
        main_lib = Millennium.steam_path()
        main_steamapps = os.path.join(main_lib, "steamapps")
        return {
            "library_path": main_lib,
            "steamapps_path": main_steamapps,
            "manifest_path": os.path.join(main_steamapps, f"{app_id_str}.manifest"),
            "lua_path": os.path.join(main_steamapps, f"{app_id_str}.lua"),
            "acf_path": os.path.join(main_steamapps, f"appmanifest_{app_id_str}.acf"),
            "exists": False
        }

    def _front_end_loaded(self):
        try:
            self._inject_webkit_files()
        except Exception as e:
            print(f"[GameGen] frontend loaded exception: {e}")

    def _unload(self):
        print("[GameGen] plugin unloaded.")

plugin = Plugin()

def _make_request(url: str, method: str = "GET", body: dict | None = None) -> dict:
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
        plugin.api_key = key
        if plugin.config_path:
            with open(plugin.config_path, "w", encoding="utf-8") as f:
                json.dump({"api_key": key}, f)
        return json.dumps({"success": True})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

import zipfile
import io

def generate_manifest(app_id: str, contentScriptQuery: str = "") -> str:
    try:
        app_id_str = str(app_id).strip()
        if not plugin.api_key:
            return json.dumps({"success": False, "error": "API key not configured"})
            
        # Use new library detection logic
        paths = plugin._find_app_paths(app_id_str)
        steamapps_dir = paths["steamapps_path"]
        dest_path = paths["acf_path"]
        already_existed = paths["exists"]

        url = f"{GAMEGEN_BASE_URL}/{plugin.api_key}/generate/{app_id_str}"
        result = _make_request(url, method="GET")
        
        if not result.get("success"):
            return json.dumps(result)
            
        m = result.get("manifest", {})
        game_name = m.get("name", f"App {app_id_str}")
        download_url = m.get("downloadUrl") or m.get("download_url") or m.get("url") or m.get("fileUrl")
        
        # New ZIP logic
        zip_url = result.get("zipUrl") or result.get("zip_url") or m.get("zipUrl") or m.get("zip_url") or result.get("contentUrl")
        installdir = m.get("installdir") or m.get("install_dir") or game_name
        
        # 1. Manifest / Script Downloads
        if download_url:
            try:
                os.makedirs(steamapps_dir, exist_ok=True)
                dl_req = urllib.request.Request(download_url)
                dl_req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                with urllib.request.urlopen(dl_req, timeout=30) as resp:
                    data = resp.read()
                    
                    # Save all required formats as the user indicated .lua and .manifest are main
                    with open(dest_path, 'wb') as f: # .acf
                        f.write(data)
                    with open(os.path.join(steamapps_dir, f"{app_id_str}.manifest"), 'wb') as f:
                        f.write(data)
                    with open(os.path.join(steamapps_dir, f"{app_id_str}.lua"), 'wb') as f:
                        f.write(data)
                
                result["_auto_installed"] = True
                result["_already_existed"] = already_existed
                plugin._add_to_history(app_id_str, game_name)
            except Exception as e:
                result["_manifest_error"] = f"Manifest download failed: {str(e)}"
        
        # 2. ZIP Processing / Game Content
        if zip_url:
            try:
                common_dir = os.path.join(steamapps_dir, "common")
                game_target_dir = os.path.join(common_dir, installdir)
                os.makedirs(game_target_dir, exist_ok=True)
                
                print(f"[GameGen] Downloading content from {zip_url} to {game_target_dir}")
                
                zip_req = urllib.request.Request(zip_url)
                zip_req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                
                with urllib.request.urlopen(zip_req, timeout=60) as resp:
                    zip_data = resp.read()
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                        z.extractall(game_target_dir)
                
                result["_zip_installed"] = True
                print(f"[GameGen] Successfully extracted ZIP for {game_name}")
            except Exception as e:
                result["_zip_error"] = f"ZIP extraction failed: {str(e)}"
                print(f"[GameGen] ZIP ERROR: {e}")
                
        return json.dumps(result)
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

