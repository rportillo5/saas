"""HIPAA Safe Harbor de-identification module.

Redacts the 18 Safe Harbor identifiers from text before sending to external
APIs, and restores original values in the output shown to the user.
"""

import re
from typing import Tuple


class PHIRedactor:
    """Regex-based PHI redactor following HIPAA Safe Harbor method."""

    # Compiled patterns: (category, regex)
    _PATTERNS = [
        ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
        ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
        ("PHONE", re.compile(
            r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        )),
        ("URL", re.compile(r"https?://[^\s,;)>]+")),
        ("IP", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
        ("DATE", re.compile(
            r"\b(?:"
            # MM/DD/YYYY or MM-DD-YYYY
            r"(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-]\d{4}"
            r"|"
            # Month DD, YYYY or Month DD YYYY
            r"(?:January|February|March|April|May|June|July|August|"
            r"September|October|November|December|"
            r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"\.?\s+\d{1,2},?\s+\d{4}"
            r"|"
            # DD Month YYYY
            r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
            r"September|October|November|December|"
            r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"\.?\s+\d{4}"
            r")\b",
            re.IGNORECASE,
        )),
        ("MRN", re.compile(r"\bMRN[:#\s]*\d{4,}\b", re.IGNORECASE)),
        ("ACCOUNT", re.compile(r"\b(?:account|acct)[#:\s]*\d{4,}\b", re.IGNORECASE)),
        ("ZIP", re.compile(r"\b\d{5}(?:-\d{4})?\b")),
        ("AGE_OVER_89", re.compile(r"\b(?:age[ds]?\s*:?\s*)?(?:9\d|[1-9]\d{2,})\s*(?:year|yr|y/?o)\b", re.IGNORECASE)),
        ("DEVICE_ID", re.compile(r"\b(?:UDI|serial\s*#?|SN)[:\s]*[A-Z0-9-]{6,}\b", re.IGNORECASE)),
        ("LICENSE", re.compile(r"\b(?:license|DEA|NPI)[#:\s]*[A-Z0-9]{6,}\b", re.IGNORECASE)),
    ]

    # Pattern to detect doctor/provider names like "Dr. Smith" or "Dr Smith"
    _DOCTOR_PATTERN = re.compile(
        r"\bDr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
    )

    def __init__(self, patient_name: str = ""):
        self.patient_name = patient_name.strip()
        self.mapping: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    def _placeholder(self, category: str, original: str) -> str:
        """Create a unique placeholder and record the mapping."""
        if original in self.mapping.values():
            for ph, val in self.mapping.items():
                if val == original:
                    return ph
        count = self._counters.get(category, 0) + 1
        self._counters[category] = count
        tag = f"[PHI_{category}_{count}]"
        self.mapping[tag] = original
        return tag

    def redact(self, text: str) -> Tuple[str, dict[str, str]]:
        """Redact PHI from text. Returns (redacted_text, placeholder_mapping)."""
        self.mapping = {}
        self._counters = {}

        # 1. Redact full patient name first (exact match, case-insensitive)
        if self.patient_name:
            parts = self.patient_name.split()
            if len(parts) > 1:
                pattern = re.compile(re.escape(self.patient_name), re.IGNORECASE)
                for match in pattern.finditer(text):
                    ph = self._placeholder("NAME", match.group())
                    text = text.replace(match.group(), ph)

        # 2. Apply all regex patterns (emails, phones, SSNs, dates, etc.)
        #    This runs BEFORE individual name parts to prevent partial matches
        for category, pattern in self._PATTERNS:
            for match in pattern.finditer(text):
                val = match.group()
                if "[PHI_" in val:
                    continue
                ph = self._placeholder(category, val)
                text = text.replace(val, ph)

        # 3. Redact doctor/provider names
        for match in self._DOCTOR_PATTERN.finditer(text):
            val = match.group()
            if "[PHI_" in val:
                continue
            ph = self._placeholder("PROVIDER", val)
            text = text.replace(val, ph)

        # 4. Redact individual name parts (first, last) — only if 3+ chars
        if self.patient_name:
            for part in self.patient_name.split():
                if len(part) >= 3:
                    pattern = re.compile(r"\b" + re.escape(part) + r"\b", re.IGNORECASE)
                    for match in pattern.finditer(text):
                        val = match.group()
                        if "[PHI_" in val:
                            continue
                        ph = self._placeholder("NAME", val)
                        text = text.replace(val, ph)

        return text, dict(self.mapping)


def restore(text: str, mapping: dict[str, str]) -> str:
    """Replace all PHI placeholders with their original values."""
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text


def restore_streaming(chunk: str, carry: str, mapping: dict[str, str]) -> Tuple[str, str]:
    """Restore PHI in a streaming chunk, handling split placeholders.

    Args:
        chunk: Current SSE chunk text.
        carry: Leftover partial placeholder from previous chunk.
        mapping: PHI placeholder mapping.

    Returns:
        (restored_text_to_emit, new_carry)
    """
    text = carry + chunk

    # Check if text ends with an incomplete placeholder
    bracket_pos = text.rfind("[PHI_")
    if bracket_pos != -1:
        after = text[bracket_pos:]
        if "]" not in after:
            # Incomplete placeholder — hold it for next chunk
            return restore(text[:bracket_pos], mapping), after

    return restore(text, mapping), ""
