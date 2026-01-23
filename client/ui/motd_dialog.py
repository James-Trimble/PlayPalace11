"""MOTD (Message of the Day) dialog for Play Palace client."""

import wx


class MOTDDialog(wx.Dialog):
    """Dialog to display server MOTD with optional 'Don't show again' option."""

    def __init__(self, parent, motd_id, title, message, dismissable=True):
        """
        Initialize the MOTD dialog.

        Args:
            parent: Parent window
            motd_id: Unique ID for this MOTD message
            title: Title of the dialog
            message: Message content
            dismissable: Whether to show 'Don't show again' checkbox
        """
        super().__init__(parent, title=title, size=(500, 400))

        self.motd_id = motd_id
        self.dont_show_again = False

        self._create_ui(message, dismissable)
        self.CenterOnScreen()

    def _create_ui(self, message, dismissable):
        """Create the UI components."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Message text (multiline, read-only)
        message_text = wx.TextCtrl(
            panel,
            value=message,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
        )
        sizer.Add(message_text, 1, wx.EXPAND | wx.ALL, 10)

        # Don't show again checkbox (if dismissable)
        if dismissable:
            self.dont_show_checkbox = wx.CheckBox(
                panel, label="&Don't show this message again"
            )
            sizer.Add(self.dont_show_checkbox, 0, wx.ALL, 10)
        else:
            self.dont_show_checkbox = None

        # OK button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ok_btn = wx.Button(panel, wx.ID_OK, "&OK")
        ok_btn.SetDefault()
        button_sizer.Add(ok_btn, 0, wx.CENTER)

        sizer.Add(button_sizer, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

        # Bind events
        ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)

        # Focus the message text so screen readers read it immediately
        message_text.SetFocus()

    def on_ok(self, event):
        """Handle OK button click."""
        if self.dont_show_checkbox:
            self.dont_show_again = self.dont_show_checkbox.GetValue()
        self.EndModal(wx.ID_OK)

    def get_dont_show_again(self):
        """Return whether user checked 'Don't show again'."""
        return self.dont_show_again
