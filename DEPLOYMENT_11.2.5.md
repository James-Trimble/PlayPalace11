# PlayPalace v11.2.5 Deployment Summary
**Deployment Date:** January 23, 2026  
**Server:** root@45.55.46.95 (playpalace.dev)

## Version Bump
- Updated from **11.2.4** to **11.2.5**
- Version constant updated in `server/core/server.py`
- `MIN_CLIENT_VERSION = (11, 2, 5)` - enforces version gate

## Major Features Added

### 1. Version Gate System (CRITICAL)
**Files Modified:**
- `server/core/server.py` - Authorization handler with version checking
- `client/network_manager.py` - Version packet sending
- `client/ui/main_window.py` - Disconnect handling and UpdateRequiredDialog

**How It Works:**
- Client sends `(major, minor, patch)` in authorize packet
- Server compares against `MIN_CLIENT_VERSION`
- If client too old: sends disconnect packet with download URL, waits 500ms, closes connection
- **NEW:** Client shows custom dialog with "Download Update" button that opens browser

**Configuration:**
```python
# In server/core/server.py
MIN_CLIENT_VERSION = (11, 2, 5)  # Change this tuple to enforce updates
```

**Example rejection message:**
```
"Please update to PlayPalace 11.2.5 or newer to continue. 
This version is required for improved security and features. 
Download the latest client at https://playpalace.dev/releases/PlayPalace-11.2.5.zip"
```

**Race Condition Fixes:**
- Added `asyncio.sleep(0.5)` after sending disconnect packet before closing connection
- Set `expecting_disconnect = True` before showing dialogs to prevent "connection lost" errors
- Cancel connection timeout timer on intentional disconnect
- Stop ConnectLoop music immediately on disconnect

### 2. ARIA Accessibility Improvements
**Files Modified:**
- `tmp_feedback.html` - Bug report form

**Changes:**
- Success messages: `aria-live="polite"`  
- Error messages: `aria-live="assertive"` with `role="status"`
- Screen reader announces form submission results

### 3. MOTD Bullet Point Fix
**Files Modified:**
- `client/ui/motd_dialog.py`

**Fix:**
- Changed bullet regex from simple backreference to lambda function
- Preserves text content: `lambda m: '• ' + m.group(1).strip() + '\n'`
- Screen readers now read bullet text properly

### 4. Connection Error Dialog Management
**Files Modified:**
- `client/ui/main_window.py`

**Improvements:**
- Exit menu items (exit/disconnect/quit/logout) now set `expecting_disconnect = True`
- No more "Connection lost!" dialogs when user intentionally exits
- Clean application shutdown

**Connection Dialogs:**
1. **Update Required** - Version gate rejection with download button
2. **Connection Closed** - Generic disconnect (old clients)
3. **Connection Error: Connection lost!** - Unexpected network drop
4. **Connection Error: Connection timeout** - Can't reach server (10s)
5. **Connection Error: Failed to start connection** - Network manager failure

## Server Changes Deployed

### Version Gate Configuration
```python
# server/core/server.py lines 21-32
VERSION = "11.2.5"

# Minimum client version required to connect
# Format: (major, minor, patch)
# Examples:
#   (11, 2, 5) - Requires exactly 11.2.5 or newer
#   (12, 0, 0) - Force all clients to upgrade to v12
#   (11, 0, 0) - Allow any 11.x.x client (most lenient)
# 
# When to tighten: protocol changes, security fixes, required features
# When to relax: bug fixes only, backward-compatible changes
MIN_CLIENT_VERSION = (11, 2, 5)
```

### Authorization Handler
```python
# Dynamic rejection message generation
min_ver_str = f"{MIN_CLIENT_VERSION[0]}.{MIN_CLIENT_VERSION[1]}.{MIN_CLIENT_VERSION[2]}"
rejection_reason = (
    f"Please update to PlayPalace {min_ver_str} or newer to continue. "
    "This version is required for improved security and features. "
    f"Download the latest client at https://playpalace.dev/releases/PlayPalace-{min_ver_str}.zip"
)
```

## Client Changes

### New Dialog Class
**`UpdateRequiredDialog`** in `client/ui/main_window.py`:
- Custom wx.Dialog with download button
- Opens browser to download URL when clicked
- Accessible (screen reader friendly)
- Auto-detects URLs in rejection messages

### Network Manager Updates
- CLIENT_VERSION sent as tuple in authorize packet
- Handles disconnect packets before connection closes
- Proper cleanup on intentional disconnection

## Repository Cleanup
- Removed all `__pycache__` directories
- Removed `*.pyc` and `*.pyo` files  
- Removed `build/` and `dist/` directories from client
- Removed temporary files and test scripts

## Deployment Steps

### 1. Server Deployment
```bash
# On playpalace.dev server
cd /root/PlayPalace11
git pull origin main
systemctl restart playpalace.service
systemctl status playpalace.service

# Verify version
curl https://playpalace.dev/status.json
```

### 2. Client Build
```bash
# On dev machine
cd client
pyinstaller PlayPalace.spec --clean

# Package with sounds
cd dist
Copy-Item -Recurse ../sounds PlayPalace/
Compress-Archive -Path PlayPalace/* -DestinationPath PlayPalace-11.2.5.zip
```

### 3. Upload Client
```bash
# On playpalace.dev server
cd /var/www/playpalace/www/releases
# Upload PlayPalace-11.2.5.zip via scp or FTP

# Update latest.json
nano latest.json
```

### 4. Update latest.json
```json
{
  "version": "11.2.5",
  "released": "2026-01-23",
  "download_url": "https://playpalace.dev/releases/PlayPalace-11.2.5.zip",
  "sha256": "<hash after upload>",
  "whats_new": "Version gate system with download button, ARIA accessibility improvements, MOTD bullet fix, connection dialog cleanup",
  "notes": "Major update - all clients should upgrade. New version gate prevents old clients from connecting. Download dialog helps users update easily."
}
```

### 5. Generate SHA256
```bash
# On server
cd /var/www/playpalace/www/releases
sha256sum PlayPalace-11.2.5.zip
# Update sha256 in latest.json
```

## Testing Checklist

- [ ] Old client (11.2.4) connects → Gets rejection dialog with download button
- [ ] New client (11.2.5) connects → Works normally  
- [ ] Click "Download Update" button → Browser opens to download URL
- [ ] Select "Exit" from menu → No "Connection lost!" dialog
- [ ] Server crash while connected → Shows "Connection lost!" dialog
- [ ] Can't reach server → Shows "Connection timeout" dialog
- [ ] MOTD bullets readable by screen readers
- [ ] Bug report form success/error announced by screen readers

## URLs to Verify
- Server Status: https://playpalace.dev/status.json (should show v11.2.5)
- Release Info: https://playpalace.dev/releases/latest.json (should show v11.2.5)
- Download: https://playpalace.dev/releases/PlayPalace-11.2.5.zip (should exist)
- Releases Page: https://playpalace.dev/releases (should display 11.2.5)

## Rollback Plan
If issues occur:
```bash
# On server
cd /root/PlayPalace11
git checkout main~1
systemctl restart playpalace.service

# Revert latest.json to 11.2.4
cd /var/www/playpalace/www/releases
# Restore previous latest.json from backup
```

## Known Issues
- None currently

## Future Enhancements
- [ ] Add "Check for Updates" menu option in client
- [ ] Auto-download and apply updates
- [ ] Version gate bypass for admins/testers
- [ ] Configurable rejection messages per MIN_CLIENT_VERSION
