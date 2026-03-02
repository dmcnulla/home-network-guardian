from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage
from urllib import request

from home_network_guardian.config import Settings


class Notifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, subject: str, body: str) -> None:
        if self.settings.notify_email_enabled:
            self._send_email(subject, body)
        if self.settings.notify_telegram_enabled:
            self._send_telegram(f"*{subject}*\n{body}")

    def _send_email(self, subject: str, body: str) -> None:
        if not self.settings.notify_email_to or not self.settings.smtp_host:
            return
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.settings.smtp_username or "hng@localhost"
        msg["To"] = self.settings.notify_email_to
        msg.set_content(body)

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as client:
            client.starttls()
            if self.settings.smtp_username and self.settings.smtp_password:
                client.login(self.settings.smtp_username, self.settings.smtp_password)
            client.send_message(msg)

    def _send_telegram(self, text: str) -> None:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = json.dumps(
            {
                "chat_id": self.settings.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        request.urlopen(req, timeout=10).read()
