"""MOTD (Message of the Day) dialog for Play Palace client."""

import webbrowser
import re
import html as html_lib

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

        # Convert HTML to accessible plain text and extract links
        text_content, links = self._html_to_accessible_text_and_links(message)

        # Accessible message text (multiline, read-only)
        message_text = wx.TextCtrl(
            panel,
            value=text_content,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            size=(480, 300),
        )
        message_text.SetName("Message of the Day")
        sizer.Add(message_text, 1, wx.EXPAND | wx.ALL, 10)

        # Links section (accessible, focusable controls)
        if links:
            for text, href in links:
                # Accessible button to open the link with fixed access key
                btn_label = "Open &Link"
                open_btn = wx.Button(panel, label=btn_label)
                open_btn.Bind(wx.EVT_BUTTON, lambda evt, url=href: webbrowser.open(url))
                sizer.Add(open_btn, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

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

    def _html_to_accessible_text_and_links(self, html: str) -> tuple[str, list[tuple[str, str]]]:
        """Convert limited HTML to accessible plain text and extract links.

        Returns (text_content, links) where links is a list of (text, href).
        """
        if not html:
            return "", []

        # Extract links first
        links: list[tuple[str, str]] = []
        def anchor_replacer(match: re.Match) -> str:
            text = html_lib.unescape(match.group(2) or "")
            href = match.group(1)
            if href:
                links.append((text or href, href))
            # Replace anchor with just its text in accessible content (no URL shown)
            return text or ""

        anchor_pattern = re.compile(r"<a\s+[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
        content = anchor_pattern.sub(anchor_replacer, html)

        # Replace headings with simple emphasized text
        content = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", lambda m: f"\n\n{html_lib.unescape(m.group(1)).strip()}\n\n", content, flags=re.IGNORECASE | re.DOTALL)

        # Replace paragraphs and breaks with newlines
        content = re.sub(r"<p[^>]*>", "\n\n", content, flags=re.IGNORECASE)
        content = re.sub(r"</p>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"<br\s*/?>", "\n", content, flags=re.IGNORECASE)

        # Strip remaining tags
        content = re.sub(r"<[^>]+>", "", content)

        # Unescape HTML entities
        content = html_lib.unescape(content)

        # Normalize whitespace
        content = re.sub(r"\s+\n", "\n", content)
        content = content.strip()

        return content, links

    def on_ok(self, event):
        """Handle OK button click."""
        if self.dont_show_checkbox:
            self.dont_show_again = self.dont_show_checkbox.GetValue()
        self.EndModal(wx.ID_OK)

    def get_dont_show_again(self):
        """Return whether user checked 'Don't show again'."""
        return self.dont_show_again
