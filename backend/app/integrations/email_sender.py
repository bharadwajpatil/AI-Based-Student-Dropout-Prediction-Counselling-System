import asyncio
import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.app.core.config import settings

logger = logging.getLogger("student-dropout-system.integrations.email")


class EmailMessage:
    def __init__(self, to_email: str, subject: str, html_content: str, text_content: str):
        self.to_email = to_email
        self.subject = subject
        self.html_content = html_content
        self.text_content = text_content


class EmailSender(ABC):
    """Abstract interface for email delivery with retry and timeout."""

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        pass


class FakeEmailSender(EmailSender):
    """In-memory test fake recording sent emails for deterministic testing."""

    def __init__(self) -> None:
        self.sent_messages: list[EmailMessage] = []
        self.fail_next: bool = False

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        if self.fail_next:
            self.fail_next = False
            logger.warning("FakeEmailSender simulated delivery failure for %s", to_email)
            return False

        message = EmailMessage(to_email, subject, html_content, text_content)
        self.sent_messages.append(message)
        logger.info("FakeEmailSender recorded email to %s: '%s'", to_email, subject)
        return True

    def clear(self) -> None:
        self.sent_messages.clear()
        self.fail_next = False


class SMTPEmailSender(EmailSender):
    """Production/dev SMTP sender with timeout and retry logic."""

    def __init__(self, max_retries: int = 3, timeout_seconds: float = 10.0) -> None:
        self.max_retries = max_retries
        self.timeout = timeout_seconds

    def _send_sync(self, to_email: str, subject: str, html_content: str, text_content: str) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=self.timeout)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=self.timeout)

        try:
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
            return True
        finally:
            server.quit()

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        for attempt in range(1, self.max_retries + 1):
            try:
                loop = asyncio.get_running_loop()
                success = await loop.run_in_executor(
                    None, self._send_sync, to_email, subject, html_content, text_content
                )
                if success:
                    return True
            except Exception as e:
                logger.warning(
                    "SMTP delivery attempt %d/%d to %s failed: %s",
                    attempt,
                    self.max_retries,
                    to_email,
                    str(e),
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
        return False
