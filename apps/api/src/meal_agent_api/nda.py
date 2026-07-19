"""NDA acceptance store + Resend notification for hosted beta testers."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[4]
NDA_FILE = PROJECT_ROOT / "data" / "nda_acceptances.json"

DEFAULT_NOTIFY_EMAIL = "marcus@pyxstudio.nz"
CURRENT_NDA_VERSION = "1"

# Keep in sync with apps/mobile/constants/nda.ts (NDA_VERSION / full prose).
NDA_FULL_TEXT = """Unilateral Non-Disclosure Agreement

Marcus Taylor

Confidential Beta Testing Agreement

This Confidential Beta Testing Agreement ("Agreement") is entered into electronically on the date the Recipient accepts the Agreement.

Between:

Owner: Marcus Taylor ("Owner")

and

Recipient: The person accepting this Agreement ("Recipient")

A. Purpose

A. Whereas, Owner is developing software applications, artificial intelligence systems, digital products, web applications, mobile applications, and related technology services (the "Business");

B. Whereas, Recipient wishes to access Confidential Information for the purpose of product evaluation, beta testing, user testing, research, product development, feedback, consulting, or other authorised testing purposes;

C. Whereas, Recipient agrees not to disclose, share, distribute, or communicate any Confidential Information without the express written permission of Marcus Taylor.

In consideration of being provided access to the beta product and related information, Recipient agrees to the following terms:

1. Confidential Information

"Confidential Information" means all non-public information related to the Business, including without limitation:

software; source code; artificial intelligence systems; AI prompts and workflows; algorithms; databases; designs; user interfaces; product concepts; features and functionality; business plans; marketing information; financial information; customer information; documentation; reports; testing materials; research; strategies; methods; processes; and any other information that is not publicly available.

Confidential Information includes information provided verbally, visually, electronically, through access to the beta application, or through any other method.

Recipient acknowledges that all Confidential Information remains the property of Owner.

Recipient receives no ownership rights, licence, or other rights to use Confidential Information except for the limited purpose of participating in authorised testing.

2. Confidentiality Obligations

Recipient agrees that they will not:

disclose Confidential Information to any person or organisation; share screenshots, recordings, videos, documents, reports, or access credentials; publish information about the beta product publicly; discuss unreleased features publicly; copy, reproduce, modify, reverse engineer, or distribute any part of the product; use Confidential Information for personal, commercial, or competitive purposes.

Recipient may only use Confidential Information for the authorised purpose of testing and providing feedback.

These confidentiality obligations do not apply to information that:

1. becomes publicly available through no breach of this Agreement;
2. was already lawfully known by Recipient before disclosure;
3. must be disclosed by law, provided Recipient gives notice to Owner where legally permitted.

3. Beta Testing Terms

Recipient understands and agrees that:

The product is a pre-release beta version. The product may contain bugs, errors, incomplete features, or changes. Access may be removed at any time. Features may change or be removed before public release. Feedback provided during testing may be used by Owner to improve the product. Participation does not create any employment, partnership, agency, or ownership relationship.

Recipient agrees to provide honest and constructive feedback where possible.

4. Intellectual Property

All intellectual property associated with the product remains the sole property of Marcus Taylor.

This includes, but is not limited to:

software; source code; designs; branding; trademarks; AI systems; prompts; report structures; databases; processes; workflows; concepts; documentation; and any improvements or developments.

Recipient obtains no ownership rights or licence except the limited right to test the product during the beta period.

5. Feedback Licence

Recipient grants Owner permission to use, modify, analyse, reproduce, and incorporate any feedback, suggestions, ideas, bug reports, or recommendations provided during testing for the purpose of improving and developing the product.

Recipient agrees that feedback may be used without compensation unless otherwise agreed in writing.

6. Privacy

Any personal information collected during beta testing will be handled in accordance with applicable New Zealand privacy laws, including the Privacy Act 2020.

Owner will take reasonable steps to protect personal information collected during testing.

Recipient agrees that information provided during testing may be used for:

account management; product improvement; analytics; communication regarding the beta program.

7. Disclaimer and Limitation of Liability

The beta product is provided on an "as available" basis.

Owner makes no guarantee that:

the product will operate without errors; results generated by the product will be accurate; the product will meet Recipient's expectations.

To the maximum extent permitted by New Zealand law, Owner will not be liable for indirect, incidental, or consequential losses arising from participation in the beta program.

Nothing in this Agreement excludes any rights or obligations that cannot legally be excluded under New Zealand law.

8. Breach and Remedies

Recipient acknowledges that unauthorised disclosure of Confidential Information may cause serious harm to Owner.

Owner may seek any available remedies under New Zealand law, including urgent court orders to prevent or stop unauthorised disclosure.

9. Governing Law

This Agreement is governed by the laws of New Zealand.

If any provision of this Agreement is found to be invalid or unenforceable, the remaining provisions will continue to apply.

Electronic Acceptance

By entering their full legal name and selecting "I Agree", the Recipient confirms that they have read and understood this Confidential Beta Testing Agreement; agree to be legally bound by its terms; and understand that typing their name and selecting "I Agree" constitutes their electronic signature and acceptance of this Agreement.
"""


@dataclass
class NdaAcceptance:
    id: str
    full_name: str
    nda_version: str
    accepted_at: str
    user_agent: str | None = None
    client_ip: str | None = None


class NdaStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or NDA_FILE
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict]:
        raw = self._path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return data

    def _save(self, rows: list[dict]) -> None:
        self._path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def append(
        self,
        *,
        full_name: str,
        nda_version: str,
        user_agent: str | None = None,
        client_ip: str | None = None,
    ) -> NdaAcceptance:
        record = NdaAcceptance(
            id=str(uuid.uuid4()),
            full_name=full_name.strip(),
            nda_version=nda_version.strip(),
            accepted_at=datetime.now(timezone.utc).isoformat(),
            user_agent=user_agent,
            client_ip=client_ip,
        )
        with self._lock:
            rows = self._load()
            rows.append(asdict(record))
            self._save(rows)
        return record


nda_store = NdaStore()


def notify_email() -> str:
    return os.environ.get("NDA_NOTIFY_EMAIL", DEFAULT_NOTIFY_EMAIL).strip() or DEFAULT_NOTIFY_EMAIL


def from_email() -> str | None:
    value = os.environ.get("NDA_FROM_EMAIL", "").strip()
    return value or None


def resend_api_key() -> str | None:
    value = os.environ.get("RESEND_API_KEY", "").strip()
    return value or None


def send_nda_notification(record: NdaAcceptance) -> None:
    """Send acceptance notice via Resend. Raises RuntimeError on failure."""
    api_key = resend_api_key()
    sender = from_email()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")
    if not sender:
        raise RuntimeError("NDA_FROM_EMAIL is not configured")

    to_addr = notify_email()
    subject = f"Beta NDA accepted — {record.full_name}"
    body = (
        f"A tester accepted the Confidential Beta Testing Agreement.\n\n"
        f"Full legal name: {record.full_name}\n"
        f"NDA version: {record.nda_version}\n"
        f"Accepted at (UTC): {record.accepted_at}\n"
        f"Record id: {record.id}\n"
        f"User-Agent: {record.user_agent or '(none)'}\n"
        f"Client IP: {record.client_ip or '(none)'}\n\n"
        f"--- Agreement text (version {record.nda_version}) ---\n\n"
        f"{NDA_FULL_TEXT}\n"
    )

    response = httpx.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": sender,
            "to": [to_addr],
            "subject": subject,
            "text": body,
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Resend email failed ({response.status_code}): {response.text[:500]}"
        )
