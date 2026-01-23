"""MOTD (Message of the Day) dialog for Play Palace client."""

import re
import webbrowser
import wx
import wx.adv


class MOTDDialog(wx.Dialog):
    """Dialog to display server MOTD with optional 'Don't show again' option."""


    def __init__(self, parent, motd_id, title, message, dismissable=True):
        """
        Initialize the MOTD dialog.

        Args:
            parent: Parent window
            motd_id: Unique ID for this MOTD message
            title: Title of the dialog
            message: Message content (plain text or with simple HTML tags: p/br/ul/li/b/i/a)
            dismissable: Whether to show 'Don't show again' checkbox
        """
        super().__init__(parent, title=title, size=(520, 420))

        self.motd_id = motd_id
        self.dont_show_again = False
        self.links = {}  # Store extracted links

        self._create_ui(message, dismissable)
        self.CenterOnScreen()

    def _create_ui(self, message, dismissable):
        """Create the UI components with accessible controls."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Message content in scrolled text control (accessible)
        text_ctrl = wx.TextCtrl(
            panel,
            value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
        )
        self._populate_text_and_links(text_ctrl, message)
        sizer.Add(text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        # Add any extracted links as clickable buttons (hide raw URLs)
        link_sizer = wx.BoxSizer(wx.VERTICAL)
        for link_text, link_url in self.links.items():
            label = "Open feedback form" if "feedback" in link_url.lower() else (link_text or "Open link")
            btn = wx.Button(panel, label=label)
            btn.Bind(wx.EVT_BUTTON, lambda e, url=link_url: webbrowser.open(url))
            link_sizer.Add(btn, 0, wx.EXPAND | wx.ALL, 5)
        
        if link_sizer.GetChildren():
            sizer.Add(link_sizer, 0, wx.EXPAND | wx.ALL, 5)

        if dismissable:
            self.dont_show_checkbox = wx.CheckBox(
                panel, label="&Don't show this message again"
            )
            sizer.Add(self.dont_show_checkbox, 0, wx.ALL, 10)
        else:
            self.dont_show_checkbox = None

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ok_btn = wx.Button(panel, wx.ID_OK, "&OK")
        ok_btn.SetDefault()
        button_sizer.Add(ok_btn, 0, wx.CENTER)
        sizer.Add(button_sizer, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)
        ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)

    def _populate_text_and_links(self, text_ctrl: wx.TextCtrl, html_content: str):
        """Extract text from HTML and buttons for links."""
        if not html_content:
            return

        # Remove HTML tags and convert to plain text
        text = html_content

        # Extract links: <a href="...">text</a> -> store and convert to plain text
        link_pattern = r'<a\s+href=["\'](.*?)["\']\s*>(.*?)</a>'
        for match in re.finditer(link_pattern, text, re.IGNORECASE):
            url = match.group(1)
            link_text = match.group(2)
            # Store link for later button creation
            if link_text.strip():
                self.links[link_text.strip()] = url
            # Replace link tag with just the text
            text = text.replace(match.group(0), link_text)

        # Remove other HTML tags
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</?p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</?ul>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</?ol>', '', text, flags=re.IGNORECASE)
        # Convert <li> to bullet with content - preserve text for screen readers
        text = re.sub(r'<li[^>]*>\s*(.*?)\s*</li>', lambda m: '• ' + m.group(1).strip() + '\n', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'</?strong>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</?b>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</?em>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'</?i>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)  # Remove any remaining tags

        # Clean up multiple newlines
        text = re.sub(r'\n\n+', '\n\n', text)
        text = text.strip()

        text_ctrl.SetValue(text)

    def on_ok(self, event):
        """Handle OK button click."""
        if self.dont_show_checkbox:
            self.dont_show_again = self.dont_show_checkbox.GetValue()
        self.EndModal(wx.ID_OK)

    def get_dont_show_again(self):
        """Return whether user checked 'Don't show again'."""
        return self.dont_show_again
