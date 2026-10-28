import logging

from email_validator import EmailNotValidError, validate_email

from backend.app.db.mongo import get_database
from backend.app.integrations.dns_checker import DNSChecker, LiveDNSChecker

logger = logging.getLogger("student-dropout-system.services.email_validation")

# Built-in base disposable email domains
BUILTIN_DISPOSABLE_DOMAINS = {
    "mailinator.com",
    "guerrillamail.com",
    "tempmail.com",
    "10minutemail.com",
    "throwawaymail.com",
    "sharklasers.com",
    "dispostable.com",
    "trashmail.com",
    "yopmail.com",
}

# Role / alias prefixes rejected for personal accounts (Layer 4)
ROLE_BASED_LOCAL_PARTS = {
    "admin",
    "administrator",
    "info",
    "noreply",
    "no-reply",
    "support",
    "contact",
    "help",
    "billing",
    "postmaster",
    "webmaster",
    "test",
}


def compute_canonical_email(email: str) -> str:
    """
    Computes canonical email identity (Scenario A6):
    - Lowercase & trimmed
    - Strips subaddressing tags ('+tag')
    - Strips dots for Gmail/Googlemail domains
    """
    email = email.strip().lower()
    if "@" not in email:
        return email

    local_part, domain = email.split("@", 1)

    # Strip subaddressing / tag (e.g. user+tag -> user)
    if "+" in local_part:
        local_part = local_part.split("+", 1)[0]

    # For Gmail, remove dots
    if domain in ("gmail.com", "googlemail.com"):
        local_part = local_part.replace(".", "")

    return f"{local_part}@{domain}"


class EmailValidationService:
    def __init__(self, dns_checker: DNSChecker | None = None) -> None:
        self.dns_checker = dns_checker or LiveDNSChecker()

    async def validate_email_address(self, email: str) -> tuple[bool, str, str]:
        """
        Runs validation layers 1-4.
        Returns (is_valid, canonical_email, error_reason).
        """
        # Layer 1: Syntax & Normalization
        if not email or len(email) > 254:
            return False, "", "Email address exceeds maximum length of 254 characters."

        try:
            val = validate_email(email, check_deliverability=False)
            normalized_email = val.normalized.lower()
            domain = val.domain.lower()
        except EmailNotValidError as e:
            return False, "", f"Invalid email format: {str(e)}"

        canonical = compute_canonical_email(normalized_email)
        local_part = normalized_email.split("@")[0]

        # Layer 3: Disposable Domain Check
        if domain in BUILTIN_DISPOSABLE_DOMAINS:
            return False, canonical, "Disposable or temporary email addresses are not permitted."

        try:
            db = get_database()
            disposable = await db.disposable_domains.find_one({"domain": domain})
            if disposable:
                return (
                    False,
                    canonical,
                    "Disposable or temporary email addresses are not permitted.",
                )
        except Exception as e:
            logger.warning("Could not query disposable_domains collection: %s", e)

        # Layer 4: Role / Alias Rejection
        clean_local = local_part.split("+")[0]
        if clean_local in ROLE_BASED_LOCAL_PARTS:
            return (
                False,
                canonical,
                "Role-based email addresses (e.g., admin, info, support) cannot be used.",
            )

        # Layer 2: Domain DNS (MX / A) Lookup
        has_mx_or_a = await self.dns_checker.check_domain_has_mx_or_a(domain)
        if not has_mx_or_a:
            return False, canonical, f"Domain '{domain}' does not have active MX or A DNS records."

        return True, canonical, ""


# Default singleton instance
default_email_validator = EmailValidationService()
