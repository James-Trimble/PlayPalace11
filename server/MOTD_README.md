# MOTD (Message of the Day) System

## Overview

The PlayPalace server includes a server-side MOTD system that displays messages to users when they connect. Messages can be dismissed permanently by users if marked as dismissable.

## Configuration

The MOTD system uses a JSON file located at `server/motd.json`.

### MOTD File Structure

```json
{
  "messages": [
    {
      "id": "welcome_2026_01",
      "title": "Welcome to PlayPalace!",
      "message": "Your message content here.\n\nSupports multiple paragraphs.",
      "dismissable": true,
      "active": true
    }
  ]
}
```

### Field Descriptions

- **id** (string, required): Unique identifier for this message. Change this to make a previously dismissed message show again.
- **title** (string, optional): Title displayed in the dialog window. Defaults to "Message of the Day".
- **message** (string, required): The message content. Use `\n` for line breaks and `\n\n` for paragraph breaks.
- **dismissable** (boolean, optional): Whether users can check "Don't show again". Defaults to `true`.
- **active** (boolean, required): Whether this message is currently active. Only the first active message is shown.

## How to Update the MOTD

1. Open `server/motd.json` in a text editor
2. Edit the existing message or add a new one to the `messages` array
3. Make sure only one message has `"active": true`
4. Save the file
5. Restart the server (or wait for hot-reload if implemented)

## Example: Adding a New Message

To add a maintenance announcement:

```json
{
  "messages": [
    {
      "id": "maintenance_2026_02",
      "title": "Scheduled Maintenance",
      "message": "The server will undergo scheduled maintenance on February 15th from 2:00 AM to 4:00 AM EST.\n\nPlease save your games before this time. Thank you for your patience!",
      "dismissable": true,
      "active": true
    },
    {
      "id": "welcome_2026_01",
      "title": "Welcome to PlayPalace!",
      "message": "Welcome to PlayPalace! This server and project are in rapid development...",
      "dismissable": true,
      "active": false
    }
  ]
}
```

## Tips

- Keep messages concise and clear
- Use `\n\n` to separate paragraphs for better readability
- Change the `id` when you want everyone to see an updated message (even those who dismissed the old one)
- Set `dismissable` to `false` for critical announcements that everyone must see
- Only one message should be active at a time
- The server loads the MOTD file on startup, so restart the server after changes

## Client Behavior

- Users see the MOTD immediately after successful login
- If a user checks "Don't show again", the message ID is saved locally
- Dismissed messages won't show again unless you change the message ID
- Each server can have different dismissed messages tracked separately
