import logging
from abc import ABC, abstractmethod

import httpx

from backend.app.core.config import settings

logger = logging.getLogger("student-dropout-system.integrations.sms")


class SMSMessage:
    def __init__(self, to_phone_e164: str, message: str):
        self.to_phone_e164 = to_phone_e164
        self.message = message


class SMSSender(ABC):
    """Abstract interface for SMS delivery with timeout and retry."""

    @abstractmethod
    async def send_sms(self, to_phone_e164: str, message: str) -> bool:
        pass


class FakeSMSSender(SMSSender):
    """In-memory test fake recording sent SMS messages for deterministic testing."""

    def __init__(self) -> None:
        self.sent_messages: list[SMSMessage] = []
        self.fail_next: bool = False

    async def send_sms(self, to_phone_e164: str, message: str) -> bool:
        if self.fail_next:
            self.fail_next = False
            logger.warning("FakeSMSSender simulated SMS failure for %s", to_phone_e164)
            return False

        msg = SMSMessage(to_phone_e164, message)
        self.sent_messages.append(msg)
        logger.info("FakeSMSSender recorded SMS to %s: '%s'", to_phone_e164, message)
        return True

    def clear(self) -> None:
        self.sent_messages.clear()
        self.fail_next = False


class TwilioSMSSender(SMSSender):
    """Twilio SMS sender using HTTP REST API with timeout."""

    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self.timeout = timeout_seconds

    async def send_sms(self, to_phone_e164: str, message: str) -> bool:
        if (
            not settings.TWILIO_ACCOUNT_SID
            or not settings.TWILIO_AUTH_TOKEN
            or not settings.TWILIO_PHONE_NUMBER
        ):
            logger.warning("Twilio credentials not configured; skipping real SMS delivery.")
            return False

        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        data = {
            "From": settings.TWILIO_PHONE_NUMBER,
            "To": to_phone_e164,
            "Body": message,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    data=data,
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                )
                if response.status_code in (200, 201):
                    return True
                logger.error(
                    "Twilio SMS send failed with status %d: %s", response.status_code, response.text
                )
                return False
        except Exception as e:
            logger.error("Twilio SMS request exception: %s", str(e))
            return False
