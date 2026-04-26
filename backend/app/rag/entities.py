from __future__ import annotations

import re

DRUG_PATTERNS: list[tuple[str, str]] = [
    (r"\badrenaline\b|\bepinephrine\b", "adrenaline"),
    (r"\bamiodarone\b", "amiodarone"),
    (r"\baspirin\b", "aspirin"),
    (r"\batropine\b", "atropine"),
    (r"\bmorphine\b", "morphine"),
    (r"\bfentanyl\b", "fentanyl"),
    (r"\bketamine\b", "ketamine"),
    (r"\bmidazolam\b", "midazolam"),
    (r"\bdiazepam\b", "diazepam"),
    (r"\blorazepam\b", "lorazepam"),
    (r"\bsalbutamol\b|\balbuterol\b", "salbutamol"),
    (r"\bipratropium\b", "ipratropium"),
    (r"\bglucose\b|\bdextrose\b", "glucose"),
    (r"\bsodium\s+chloride\b|\bnormal\s+saline\b|\b0\.9%\s+saline\b", "sodium_chloride"),
    (r"\bnitroglycerin\b|\bglyceryl\s+trinitrate\b|\bGTN\b", "gtn"),
    (r"\bfurosemide\b|\bfrusemide\b", "furosemide"),
    (r"\bhydrocortisone\b", "hydrocortisone"),
    (r"\bdexamethasone\b", "dexamethasone"),
    (r"\bmetoclopramide\b", "metoclopramide"),
    (r"\bondansetron\b", "ondansetron"),
    (r"\btranexamic\s+acid\b|\bTXA\b", "tranexamic_acid"),
    (r"\bheparin\b", "heparin"),
    (r"\balteplase\b|\btenecteplase\b", "thrombolytics"),
    (r"\boxygen\b|\bO2\b", "oxygen"),
    (r"\bnitrous\s+oxide\b|\bentonox\b", "entonox"),
    (r"\bcalcium\s+gluconate\b|\bcalcium\s+chloride\b", "calcium"),
    (r"\bmagnesium\s+sulphate\b|\bmagnesium\s+sulfate\b", "magnesium"),
    (r"\bpotassium\s+chloride\b", "potassium_chloride"),
    (r"\bnaloxone\b|\bnarcan\b", "naloxone"),
    (r"\bflumazenil\b", "flumazenil"),
]

_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE), canonical)
    for pattern, canonical in DRUG_PATTERNS
]


def extract_entities(text: str) -> list[str]:
    """Return canonical entity IDs for drugs/substances found in text."""
    found: list[str] = []
    seen: set[str] = set()
    for pattern, canonical in _COMPILED:
        if pattern.search(text) and canonical not in seen:
            found.append(f"entity_{canonical}")
            seen.add(canonical)
    return found
