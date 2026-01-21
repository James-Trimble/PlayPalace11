"""Auto-updater for PlayPalace client."""

import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

import wx


class AutoUpdater:
    """Handles automatic client updates."""
    
    def __init__(self, main_window, current_version: str):
        """
        Initialize auto-updater.
        
        Args:
            main_window: Reference to MainWindow for callbacks
            current_version: Current client version (e.g., "11.2.2")
        """
        self.main_window = main_window
        self.current_version = current_version
        self.update_url = "https://playpalace.dev/downloads/latest.json"
        
    def check_for_updates(self, silent: bool = False):
        """
        Check for updates and prompt user if available.
        
        Args:
            silent: If True, only notify if update is available
        """
        thread = threading.Thread(
            target=self._check_for_updates_thread,
            args=(silent,),
            daemon=True
        )
        thread.start()
    
    def _check_for_updates_thread(self, silent: bool):
        """Background thread to check for updates."""
        try:
            # Fetch latest version info
            with urllib.request.urlopen(self.update_url, timeout=5) as response:
                data = json.loads(response.read().decode())
            
            latest_version = data.get("version", "0.0.0")
            download_url = data.get("download_url", "")
            changelog = data.get("changelog", "")
            
            # Compare versions
            if self._is_newer_version(latest_version):
                wx.CallAfter(
                    self._prompt_update,
                    latest_version,
                    download_url,
                    changelog
                )
            elif not silent:
                wx.CallAfter(
                    wx.MessageBox,
                    f"You are running the latest version ({self.current_version}).",
                    "No Updates Available",
                    wx.OK | wx.ICON_INFORMATION
                )
        except Exception as e:
            if not silent:
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to check for updates: {e}",
                    "Update Check Failed",
                    wx.OK | wx.ICON_ERROR
                )
    
    def _is_newer_version(self, latest: str) -> bool:
        """
        Compare version strings.
        
        Args:
            latest: Latest version string (e.g., "11.2.3")
            
        Returns:
            True if latest is newer than current
        """
        try:
            current_parts = [int(x) for x in self.current_version.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]
            
            # Pad to same length
            while len(current_parts) < len(latest_parts):
                current_parts.append(0)
            while len(latest_parts) < len(current_parts):
                latest_parts.append(0)
            
            return latest_parts > current_parts
        except (ValueError, AttributeError):
            return False
    
    def _prompt_update(self, version: str, download_url: str, changelog: str):
        """
        Prompt user to update.
        
        Args:
            version: New version string
            download_url: URL to download update
            changelog: Changelog text
        """
        message = (
            f"A new version of PlayPalace is available!\n\n"
            f"Current version: {self.current_version}\n"
            f"Latest version: {version}\n\n"
            f"Changes:\n{changelog}\n\n"
            f"Would you like to download and install it now?"
        )
        
        dlg = wx.MessageDialog(
            self.main_window,
            message,
            "Update Available",
            wx.YES_NO | wx.ICON_INFORMATION
        )
        
        if dlg.ShowModal() == wx.ID_YES:
            self._download_and_install(version, download_url)
        
        dlg.Destroy()
    
    def _download_and_install(self, version: str, download_url: str):
        """
        Download and install update.
        
        Args:
            version: New version string
            download_url: URL to download update
        """
        # Show progress dialog
        progress = wx.ProgressDialog(
            "Downloading Update",
            f"Downloading PlayPalace {version}...",
            maximum=100,
            parent=self.main_window,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )
        
        thread = threading.Thread(
            target=self._download_thread,
            args=(download_url, progress),
            daemon=True
        )
        thread.start()
    
    def _download_thread(self, download_url: str, progress: wx.ProgressDialog):
        """Background thread to download and install update."""
        temp_zip = None
        try:
            # Download to temp file
            temp_zip = os.path.join(tempfile.gettempdir(), "playpalace_update.zip")
            
            def reporthook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(int(block_num * block_size * 100 / total_size), 100)
                    wx.CallAfter(progress.Update, percent)
            
            urllib.request.urlretrieve(download_url, temp_zip, reporthook)
            wx.CallAfter(progress.Update, 100, "Installing update...")
            
            # Extract to temporary directory
            temp_dir = os.path.join(tempfile.gettempdir(), "playpalace_update")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            
            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Get current installation directory
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                current_dir = os.path.dirname(sys.executable)
            else:
                # Running as script
                current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Create update script
            if sys.platform == "win32":
                self._create_windows_update_script(current_dir, temp_dir)
            else:
                self._create_unix_update_script(current_dir, temp_dir)
            
            wx.CallAfter(progress.Destroy)
            wx.CallAfter(
                self._finish_update,
                "Update downloaded successfully!\n\nThe application will now restart to complete the installation."
            )
            
        except Exception as e:
            wx.CallAfter(progress.Destroy)
            wx.CallAfter(
                wx.MessageBox,
                f"Failed to download update: {e}",
                "Update Failed",
                wx.OK | wx.ICON_ERROR
            )
        finally:
            if temp_zip and os.path.exists(temp_zip):
                try:
                    os.remove(temp_zip)
                except:
                    pass
    
    def _create_windows_update_script(self, current_dir: str, temp_dir: str):
        """Create Windows batch script to replace files and restart."""
        script_path = os.path.join(tempfile.gettempdir(), "playpalace_update.bat")
        
        # Get executable name
        if getattr(sys, 'frozen', False):
            exe_name = os.path.basename(sys.executable)
        else:
            exe_name = "PlayPalace.exe"
        
        script_content = f'''@echo off
echo Updating PlayPalace...
timeout /t 2 /nobreak >nul

REM Copy new files
xcopy /E /I /Y "{temp_dir}\\*" "{current_dir}"

REM Clean up
rmdir /S /Q "{temp_dir}"
del "%~f0"

REM Restart application
cd /d "{current_dir}"
start "" "{exe_name}"
'''
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Store script path for execution
        self.update_script = script_path
    
    def _create_unix_update_script(self, current_dir: str, temp_dir: str):
        """Create Unix shell script to replace files and restart."""
        script_path = os.path.join(tempfile.gettempdir(), "playpalace_update.sh")
        
        # Get executable name
        if getattr(sys, 'frozen', False):
            exe_name = os.path.basename(sys.executable)
        else:
            exe_name = "PlayPalace"
        
        script_content = f'''#!/bin/bash
echo "Updating PlayPalace..."
sleep 2

# Copy new files
cp -rf "{temp_dir}"/* "{current_dir}"/

# Clean up
rm -rf "{temp_dir}"
rm "$0"

# Restart application
cd "{current_dir}"
./{exe_name} &
'''
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        os.chmod(script_path, 0o755)
        
        # Store script path for execution
        self.update_script = script_path
    
    def _finish_update(self, message: str):
        """
        Show completion message and restart.
        
        Args:
            message: Message to show user
        """
        dlg = wx.MessageDialog(
            self.main_window,
            message,
            "Update Ready",
            wx.OK | wx.ICON_INFORMATION
        )
        dlg.ShowModal()
        dlg.Destroy()
        
        # Launch update script and exit
        if sys.platform == "win32":
            os.startfile(self.update_script)
        else:
            os.system(f'nohup "{self.update_script}" >/dev/null 2>&1 &')
        
        # Exit current application
        wx.CallAfter(self.main_window.Close, True)
