"""Registration dialog for Play Palace v9 client."""

import wx
import json
import asyncio
import threading
import websockets
import ssl


class RegistrationDialog(wx.Dialog):
    """Registration dialog for creating new accounts."""

    def __init__(self, parent, server_url):
        """Initialize the registration dialog."""
        super().__init__(parent, title="Create Play Palace Account", size=(400, 280))

        self.server_url = server_url
        self._create_ui()
        self.CenterOnScreen()

    def _create_ui(self):
        """Create the UI components."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="Create New Account")
        title_font = title.GetFont()
        title_font.PointSize += 4
        title_font = title_font.Bold()
        title.SetFont(title_font)
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        # Username
        username_label = wx.StaticText(panel, label="&Username:")
        sizer.Add(username_label, 0, wx.LEFT | wx.TOP, 10)

        self.username_input = wx.TextCtrl(panel)
        sizer.Add(self.username_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        username_help = wx.StaticText(
            panel, label="Letters, numbers, underscores, and dashes only"
        )
        username_help.SetForegroundColour(wx.Colour(100, 100, 100))
        sizer.Add(username_help, 0, wx.LEFT | wx.RIGHT, 10)

        # Password
        password_label = wx.StaticText(panel, label="&Password:")
        sizer.Add(password_label, 0, wx.LEFT | wx.TOP, 10)

        self.password_input = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        sizer.Add(self.password_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Confirm Password
        confirm_label = wx.StaticText(panel, label="&Confirm Password:")
        sizer.Add(confirm_label, 0, wx.LEFT | wx.TOP, 10)

        self.confirm_input = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        sizer.Add(self.confirm_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.register_btn = wx.Button(panel, label="&Register")
        self.register_btn.SetDefault()
        button_sizer.Add(self.register_btn, 0, wx.RIGHT, 5)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "&Cancel")
        button_sizer.Add(cancel_btn, 0)

        sizer.Add(button_sizer, 0, wx.ALL | wx.CENTER, 10)

        # Set sizer
        panel.SetSizer(sizer)

        # Bind events
        self.register_btn.Bind(wx.EVT_BUTTON, self.on_register)
        cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)

        # Set focus
        self.username_input.SetFocus()

    def on_register(self, event):
        """Handle register button click."""
        username = self.username_input.GetValue().strip()
        password = self.password_input.GetValue()
        confirm = self.confirm_input.GetValue()

        # Validate fields
        if not username:
            wx.MessageBox("Please enter a username", "Error", wx.OK | wx.ICON_ERROR)
            self.username_input.SetFocus()
            return

        if not password:
            wx.MessageBox("Please enter a password", "Error", wx.OK | wx.ICON_ERROR)
            self.password_input.SetFocus()
            return

        if password != confirm:
            wx.MessageBox("Passwords do not match", "Error", wx.OK | wx.ICON_ERROR)
            self.confirm_input.SetFocus()
            return

        # Disable button during registration
        self.register_btn.Enable(False)

        # Send registration to server
        self._send_registration(username, password)

    def _send_registration(self, username, password):
        """Send registration packet to server."""
        # Run in a thread to avoid blocking UI
        thread = threading.Thread(
            target=self._register_thread,
            args=(username, password),
            daemon=True,
        )
        thread.start()

    def _register_thread(self, username, password):
        """Thread to handle registration."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self._send_register_packet(username, password)
            )
            loop.close()

            # Show result on main thread
            wx.CallAfter(self._show_registration_result, result)
        except Exception as e:
            wx.CallAfter(self._show_registration_result, f"Connection error: {str(e)}")

    async def _send_register_packet(self, username, password):
        """Send registration packet and wait for response."""
        try:
            # Create SSL context that allows self-signed certificates
            ssl_context = None
            if self.server_url.startswith("wss://"):
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            async with websockets.connect(self.server_url, ssl=ssl_context) as ws:
                # Send registration packet
                await ws.send(
                    json.dumps(
                        {
                            "type": "register",
                            "username": username,
                            "password": password,
                        }
                    )
                )

                # Wait for response (server will send a "speak" message)
                message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(message)

                if data.get("type") == "speak":
                    return data.get("text", "Registration successful")
                else:
                    return "Unexpected response from server"

        except asyncio.TimeoutError:
            return "Server did not respond in time"
        except Exception as e:
            return f"Error: {str(e)}"

    def _show_registration_result(self, message):
        """Show registration result to user."""
        self.register_btn.Enable(True)

        # Check if it was successful
        success = (
            "registration successful" in message.lower()
            or "you can now log in" in message.lower()
        )

        if success:
            wx.MessageBox(
                message, "Registration Successful", wx.OK | wx.ICON_INFORMATION
            )
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox(message, "Registration Failed", wx.OK | wx.ICON_ERROR)
            self.EndModal(wx.ID_CANCEL)

    def on_cancel(self, event):
        """Handle cancel button click."""
        self.EndModal(wx.ID_CANCEL)
