import asyncio
import logging
from abc import ABC, abstractmethod

import dns.exception
import dns.resolver

logger = logging.getLogger("student-dropout-system.integrations.dns")


class DNSChecker(ABC):
    """Abstract interface for domain MX / A record deliverability pre-filtering."""

    @abstractmethod
    async def check_domain_has_mx_or_a(self, domain: str) -> bool:
        pass


class FakeDNSChecker(DNSChecker):
    """Controllable DNS checker for unit testing scenarios A2 and A3."""

    def __init__(self) -> None:
        self.nonexistent_domains: set[str] = {"nonexistent-domain-12345.xyz"}
        self.timeout_domains: set[str] = set()

    async def check_domain_has_mx_or_a(self, domain: str) -> bool:
        normalized = domain.lower().strip()
        if normalized in self.timeout_domains:
            # Scenario A3: DNS timeout -> do not reject; log warning and return True
            logger.warning(
                "DNS resolution timed out for domain %s (falling through to ownership proof)",
                domain,
            )
            return True

        if normalized in self.nonexistent_domains:
            # Scenario A2: Nonexistent domain -> reject
            return False

        return True


class LiveDNSChecker(DNSChecker):
    """Live DNS MX / A lookup with strict 3-second timeout per RFC 5321."""

    def __init__(self, timeout: float = 3.0) -> None:
        self.timeout = timeout

    def _sync_lookup(self, domain: str) -> bool:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = self.timeout

        # 1. Try MX record lookup
        try:
            answers = resolver.resolve(domain, "MX")
            if answers:
                return True
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            pass  # Fallback to A record
        except dns.resolver.NXDOMAIN:
            return False
        except dns.exception.Timeout:
            logger.warning("DNS MX lookup timed out for domain %s (falling through)", domain)
            return True
        except Exception as e:
            logger.warning("DNS lookup transient failure for %s: %s (falling through)", domain, e)
            return True

        # 2. RFC 5321 Fallback: Try A record lookup
        try:
            answers = resolver.resolve(domain, "A")
            if answers:
                return True
        except dns.resolver.NXDOMAIN:
            return False
        except dns.exception.Timeout:
            logger.warning("DNS A lookup timed out for domain %s (falling through)", domain)
            return True
        except Exception:
            return True

        return False

    async def check_domain_has_mx_or_a(self, domain: str) -> bool:
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, self._sync_lookup, domain)
        except Exception as e:
            logger.warning("DNS check executor failure for %s: %s", domain, e)
            return True
