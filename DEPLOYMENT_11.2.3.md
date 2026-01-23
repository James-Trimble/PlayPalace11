# PlayPalace v11.2.3 Deployment Summary
**Deployment Date:** January 22, 2026  
**Server:** root@45.55.46.95 (playpalace.dev)

## Version Bump
- Updated from **11.2.2** to **11.2.3**
- Version constant updated in `server/core/server.py`

## Server Changes Deployed
1. **MOTD System Added**
   - New file: `/root/PlayPalace11/server/motd.json`
   - Modified: `/root/PlayPalace11/server/core/server.py`
   - Server now loads MOTD configuration on startup
   - Sends MOTD to clients after successful authorization

2. **Service Restarted**
   - `systemctl restart playpalace.service`
   - Server confirmed running with version 11.2.3
   - Status JSON updated: `https://playpalace.dev/status.json`

## Website Updates Deployed
1. **404 Page Updated**
   - File: `/var/www/playpalace/www/404.html`
   - Download link changed from direct zip to `/releases`
   - Version-agnostic link now points to releases page

2. **Releases Page Created**
   - New file: `/var/www/playpalace/www/releases/index.html`
   - Dynamically loads version info from latest.json
   - Displays what's new and download button
   - Accessible at: `https://playpalace.dev/releases`

3. **Latest Release Info Updated**
   - File: `/var/www/playpalace/www/releases/latest.json`
   - Version: 11.2.3
   - What's New: "Added server-side MOTD system with dismissal tracking."
   - Notes: "Server and client updates. MOTD dialog displays on connect with optional 'don't show again' per server."

## Server Cleanup Performed
- Removed all `__pycache__` directories (freed ~1MB)
- No unnecessary log files found
- Disk usage: 12% (3.7G used of 33G)
- Server is clean and optimized

## Client Status
⚠️ **Client needs recompilation** with MOTD support files:
- `client/ui/motd_dialog.py` (new)
- `client/network_manager.py` (modified - added "motd" packet handler)
- `client/ui/main_window.py` (modified - added on_server_motd handler)
- `client/config_manager.py` (modified - added dismissed MOTD tracking)

**Next Steps:**
1. Compile new Windows client with MOTD support
2. Upload to `/var/www/playpalace/www/releases/PlayPalace-11.2.3.zip`
3. Update `latest.json` sha256 hash after upload
4. Test MOTD system with new client

## URLs to Verify
- Server Status: https://playpalace.dev/status.json (shows v11.2.3 ✓)
- Release Info: https://playpalace.dev/releases/latest.json (shows v11.2.3 ✓)
- Releases Page: https://playpalace.dev/releases (live ✓)
- 404 Page: https://playpalace.dev/nonexistent (links to /releases ✓)

## Backward Compatibility
- Old v11.2.2 clients will continue to work
- They will gracefully ignore the "motd" packet
- MOTD only appears for v11.2.3+ clients
