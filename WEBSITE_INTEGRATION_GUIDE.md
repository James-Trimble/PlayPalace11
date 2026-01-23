# Website Integration Guide - Online Player Tracking

This guide explains how to integrate the PlayPalace server's online player tracking system into your website.

## Quick Start

The PlayPalace server writes a live `status.json` file that your website can read to display:
- Number of online players
- List of online player names
- Server status
- Number of active games

## Setup

### 1. Configure Server to Write Status File

When starting the PlayPalace server, use the `--status-file` flag:

```bash
python -m server.main \
  --host 0.0.0.0 \
  --port 8000 \
  --status-file /var/www/playpalace.dev/status.json
```

This writes a JSON file that your web server can serve to clients.

### 2. Serve Status File from Web Server

**Nginx Example:**
```nginx
location /api/status {
    alias /var/www/playpalace.dev/status.json;
    add_header Cache-Control "no-cache, must-revalidate";
    add_header Content-Type "application/json";
}
```

**Apache Example:**
```apache
Alias /api/status /var/www/playpalace.dev/status.json
<Directory /var/www/playpalace.dev>
    Header set Cache-Control "no-cache, must-revalidate"
    Header set Content-Type "application/json"
</Directory>
```

### 3. Add to Your Website

#### HTML

```html
<!DOCTYPE html>
<html>
<head>
    <title>PlayPalace Server Status</title>
    <style>
        .status-widget {
            background: #f0f0f0;
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            max-width: 400px;
        }
        .status-online {
            color: #27ae60;
            font-weight: bold;
        }
        .status-offline {
            color: #e74c3c;
            font-weight: bold;
        }
        .player-count {
            font-size: 24px;
            color: #2980b9;
            font-weight: bold;
        }
        .players-list {
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            max-height: 200px;
            overflow-y: auto;
            margin-top: 10px;
        }
        .player-item {
            padding: 5px;
            border-bottom: 1px solid #eee;
        }
        .player-item:last-child {
            border-bottom: none;
        }
    </style>
</head>
<body>
    <div class="status-widget">
        <h2>PlayPalace Server Status</h2>
        <p>
            Status: <span id="server-status" class="status-offline">Loading...</span>
        </p>
        <p>
            Players Online: <span class="player-count" id="player-count">0</span>
        </p>
        <p>
            Active Games: <span id="active-games">0</span>
        </p>
        <div>
            <h4>Online Players:</h4>
            <div class="players-list" id="players-list">
                <div class="player-item">None online</div>
            </div>
        </div>
        <p style="font-size: 12px; color: #999;">
            Last updated: <span id="last-updated">Never</span>
        </p>
    </div>

    <script src="playpalace-status.js"></script>
</body>
</html>
```

#### JavaScript (playpalace-status.js)

```javascript
/**
 * PlayPalace Server Status Widget
 * Automatically updates server status display from status.json
 */

const PlayPalaceStatus = {
    statusFile: '/api/status',
    updateInterval: 5000, // 5 seconds
    retryInterval: 10000, // 10 seconds on failure
    
    init() {
        this.update();
        setInterval(() => this.update(), this.updateInterval);
    },
    
    async update() {
        try {
            const response = await fetch(this.statusFile, {
                cache: 'no-store',
                headers: {
                    'Pragma': 'no-cache',
                    'Cache-Control': 'no-cache'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const status = await response.json();
            this.render(status);
        } catch (error) {
            console.error('Failed to fetch status:', error);
            this.renderOffline();
        }
    },
    
    render(status) {
        // Update server status
        const statusEl = document.getElementById('server-status');
        statusEl.textContent = status.online ? 'Online' : 'Offline';
        statusEl.className = status.online ? 'status-online' : 'status-offline';
        
        // Update player count
        document.getElementById('player-count').textContent = status.players.count;
        
        // Update active games
        document.getElementById('active-games').textContent = status.tables.active;
        
        // Update player list
        this.renderPlayerList(status.players.list);
        
        // Update last updated time
        const date = new Date(status.timestamp * 1000);
        document.getElementById('last-updated').textContent = 
            date.toLocaleTimeString();
    },
    
    renderPlayerList(players) {
        const listEl = document.getElementById('players-list');
        
        if (!players || players.length === 0) {
            listEl.innerHTML = '<div class="player-item">None online</div>';
            return;
        }
        
        listEl.innerHTML = players.map(player => 
            `<div class="player-item">${this.escapeHtml(player)}</div>`
        ).join('');
    },
    
    renderOffline() {
        document.getElementById('server-status').textContent = 'Offline';
        document.getElementById('server-status').className = 'status-offline';
        document.getElementById('player-count').textContent = '0';
        document.getElementById('active-games').textContent = '0';
        document.getElementById('players-list').innerHTML = 
            '<div class="player-item">Unable to connect</div>';
    },
    
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    PlayPalaceStatus.init();
});
```

## Response Format

The `status.json` file contains:

```json
{
  "version": "11.2.2",
  "online": true,
  "timestamp": 1705969000,
  "players": {
    "count": 3,
    "list": ["Alice", "Bob", "Charlie"]
  },
  "tables": {
    "count": 2,
    "active": 1
  }
}
```

## Advanced Usage

### React Component

```jsx
import React, { useState, useEffect } from 'react';

function PlayPalaceStatusWidget() {
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const response = await fetch('/api/status', {
                    cache: 'no-store'
                });
                if (!response.ok) throw new Error('Failed to fetch');
                const data = await response.json();
                setStatus(data);
                setError(null);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchStatus();
        const interval = setInterval(fetchStatus, 5000);
        return () => clearInterval(interval);
    }, []);

    if (error) {
        return <div className="status-offline">Server Offline</div>;
    }

    if (!status) {
        return <div>Loading...</div>;
    }

    return (
        <div className="status-widget">
            <h2>PlayPalace Status</h2>
            <p>
                Players Online: <strong>{status.players.count}</strong>
            </p>
            <p>
                Active Games: <strong>{status.tables.active}</strong>
            </p>
            <div>
                <h4>Online Players:</h4>
                <ul>
                    {status.players.list.map(player => (
                        <li key={player}>{player}</li>
                    ))}
                </ul>
            </div>
        </div>
    );
}

export default PlayPalaceStatusWidget;
```

### Vue Component

```vue
<template>
    <div class="status-widget" v-if="status">
        <h2>PlayPalace Status</h2>
        <p>
            Status: 
            <span :class="status.online ? 'status-online' : 'status-offline'">
                {{ status.online ? 'Online' : 'Offline' }}
            </span>
        </p>
        <p>Players Online: <strong>{{ status.players.count }}</strong></p>
        <p>Active Games: <strong>{{ status.tables.active }}</strong></p>
        <div>
            <h4>Online Players:</h4>
            <ul>
                <li v-for="player in status.players.list" :key="player">
                    {{ player }}
                </li>
            </ul>
        </div>
    </div>
</template>

<script>
export default {
    data() {
        return {
            status: null
        };
    },
    mounted() {
        this.fetchStatus();
        setInterval(() => this.fetchStatus(), 5000);
    },
    methods: {
        async fetchStatus() {
            try {
                const response = await fetch('/api/status', {
                    cache: 'no-store'
                });
                this.status = await response.json();
            } catch (error) {
                console.error('Failed to fetch status:', error);
            }
        }
    }
};
</script>
```

## CORS Considerations

If your website is on a different domain from your PlayPalace server, configure CORS headers on your web server to allow status.json to be accessed from your website domain.

**Nginx CORS Example:**
```nginx
add_header Access-Control-Allow-Origin "https://your-website.com";
add_header Access-Control-Allow-Methods "GET, OPTIONS";
add_header Access-Control-Max-Age "3600";
```

## Troubleshooting

### Status file not updating
- Check that server is running with `--status-file` flag
- Verify file path is writable
- Check server logs for "Failed to write status file" messages

### Always shows "Offline"
- Verify status.json is being served with correct Content-Type: application/json
- Check browser console for CORS errors
- Ensure fetch URL is correct

### Players list empty
- Status file may not have users logged in yet
- Wait for users to connect to server
- Check that server is actually running

## Performance

- Status file updates every ~1 second
- Recommended to fetch status every 5-10 seconds on website
- Use cache-busting headers to prevent stale data
- Consider caching status on website backend if high traffic

## See Also

- [STATUS_JSON_FORMAT.md](STATUS_JSON_FORMAT.md) - Detailed format documentation
- [Server Architecture](server/plans/server_architecture.md)
