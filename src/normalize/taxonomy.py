"""Crime category normalization for women's safety aggregates."""

from __future__ import annotations

import re

# Platform-level categories shown to end users
PLATFORM_CATEGORIES = [
    "Harassment",
    "Stalking",
    "Assault",
    "Domestic Violence",
    "Kidnapping",
    "Trafficking",
    "Sexual Assault",
    "Eve Teasing",
    "Cyber Crime",
    "Dowry Related",
    "Missing Women",
    "Workplace Harassment",
    "Public Space Harassment",
    "Other",
    "Total Crimes Against Women",
]

# Categories safe to publish in the canonical end-user table
PUBLISHABLE_CATEGORIES = [
    "Total Crimes Against Women",
    "Sexual Assault",
    "Assault",
    "Domestic Violence",
    "Dowry Related",
    "Kidnapping",
    "Trafficking",
    "Eve Teasing",
    "Stalking",
    "Harassment",
    "Workplace Harassment",
    "Public Space Harassment",
    "Cyber Crime",
]

# Ordered rules: first match wins. Patterns match uppercased/normalized labels.
RULES: list[tuple[str, str, float]] = [
    (r"TOTAL\s*CRIMES?\s*AGAINST\s*WOMEN|CRIME\s*AGAINST\s*WOMEN\s*TOTAL|^TOTAL$|TOTAL\s*\(ITEM|TOTAL\s*IPC\s*CRIMES\s*AGAINST\s*WOMEN|TOTAL\s*SLL\s*CRIMES\s*AGAINST\s*WOMEN|TOTAL\s*CRIME\s*AGAINST\s*WOMEN", "Total Crimes Against Women", 0.99),
    (r"DOWRY\s*DEATH|DOWRY\s*PROHIBITION|\bDOWRY\b", "Dowry Related", 0.95),
    (r"CRUELTY\s*BY\s*HUSBAND|DOMESTIC\s*VIOLENCE|498\s*A|PWDVA|PROTECTION\s*OF\s*WOMEN\s*FROM\s*DOMESTIC", "Domestic Violence", 0.95),
    (r"RAPE|GANG\s*RAPE|SEXUAL\s*ASSAULT|POCSO|UNNATURAL|CHILD\s*RAPE", "Sexual Assault", 0.95),
    (r"DISROBE|VOYEUR", "Assault", 0.88),
    (r"ASSAULT\s*ON\s*WOMEN|ASSAULT.*MODESTY|OUTRAG(E|ING)\s*MODESTY|MOLEST|SECTION\s*354\b", "Assault", 0.9),
    (r"INSULT\s*TO\s*(THE\s*)?MODESTY|INSULTING\s*MODESTY|EVE\s*TEAS", "Eve Teasing", 0.9),
    (r"SH\s*AT\s*WORK|HARASSMENT\s*AT\s*WORK|WORKPLACE|SH\s*AT\s*WORK/PREMISES", "Workplace Harassment", 0.9),
    (r"SH\s*IN\s*PUBLIC\s*TRANSPORT|PUBLIC\s*TRANSPORT", "Public Space Harassment", 0.9),
    (r"SH\s*IN\s*OTHER\s*PLACES|SH\s*IN\s*SHELTER|SEXUAL\s*HARRASSMENT\s*TOTAL|SEXUAL\s*HARASSMENT\s*TOTAL", "Harassment", 0.85),
    (r"SEXUAL\s*HARASS|SEXUAL\s*HARRASS|CHILD\s*SEXUAL\s*HARASS", "Harassment", 0.85),
    (r"STALK", "Stalking", 0.9),
    (r"KIDNAP|ABDUCT", "Kidnapping", 0.9),
    (r"TRAFFICK|PROCURATION|IMPORTATION\s*OF\s*GIRL|SELLING\s*OF\s*MINOR|BUYING\s*OF\s*MINOR|ITP\s*ACT|PROSTITUTION|IMMORAL\s*TRAFFIC|DETAINING\s*A\s*(PERSON|PRSN)", "Trafficking", 0.85),
    (r"CYBER|SEXUALLY\s*EXPLICIT|PORNOGRAPH|PUBLSHNG|PUBLISHING\s*OR\s*TRANSMITTING", "Cyber Crime", 0.85),
    (r"MISSING", "Missing Women", 0.8),
    (r"ACID\s*ATTACK", "Assault", 0.85),
    (r"ABETMENT\s*(TO|OF)\s*SUICIDE", "Other", 0.75),
    (r"INDECENT\s*REPRESENTATION", "Other", 0.75),
    (r"MISCARRIAGE", "Other", 0.7),
    (r"HARASS", "Harassment", 0.75),
]

# Source labels that are structural junk and must never enter canonical
DROP_SOURCE_PATTERNS = [
    r"^COL_\d+$",
    r"^UNNAMED",
    r"^S\.?\s*NO",
    r"^SL\.?\s*NO",
    r"^INDEX$",
    r"^ID$",
    r"^RANK",
    r"^SUB\s*TOTAL",
    r"^CAW\s*CATEGORY",
]

# India Data Portal district CAW: mutually exclusive primary columns only.
# Omits overlapping POCSO/subtype heads that would double-count rape/assault.
IDP_PRIMARY_COLUMNS: dict[str, str] = {
    "rape_women_above_18": "Sexual Assault",
    "child_rape": "Sexual Assault",
    "attempt_to_commit_rape_above_18": "Sexual Assault",
    "attempt_to_commit_rape_girls_below_18": "Sexual Assault",
    "murder_with_rape_gang_rape": "Sexual Assault",
    "assault_on_womenabove_18": "Assault",
    "assault_on_women_below_18": "Assault",
    "acid_attack": "Assault",
    "attempt_to_acid_attack": "Assault",
    "insult_to_the_modesty_of_women_above_18": "Eve Teasing",
    "insult_to_the_modesty_of_women_below_18": "Eve Teasing",
    "cruelty_by_husband_or_his_relatives": "Domestic Violence",
    "dowry_deaths": "Dowry Related",
    "dowry_prohibition": "Dowry Related",
    "kidnapping_and_abduction": "Kidnapping",
    "human_trafficking": "Trafficking",
    "detaining_a_prsn_in_premises_where_prost_is_carried": "Trafficking",
    "procuration_of_minor_girls": "Trafficking",
    "procuring_inducing_children_for_the_sake_of_prostitution": "Trafficking",
    "prostitution_in_or_in_the_vicinity_of_public_places": "Trafficking",
    "other_sections_under_itp_act": "Trafficking",
    "seducing_or_soliciting_for_purpose_of_prostitution": "Trafficking",
    "buying_of_minor_girls": "Trafficking",
    "selling_of_minor_girls": "Trafficking",
    "importation_of_girls_from_foreign": "Trafficking",
    "child_sexual_harassment": "Harassment",
    "publshng_or_transmitting_of_sexually_explicit_mtrl": "Cyber Crime",
    "other_women_centric_cyber_crimes": "Cyber Crime",
    "use_of_child_for_pornography": "Cyber Crime",
}


def normalize_category(source_label: str) -> tuple[str, float]:
    if source_label is None:
        return "Other", 0.0
    text = str(source_label).strip()
    if not text:
        return "Other", 0.0
    upper = re.sub(r"[_\-]+", " ", text).upper()
    upper = re.sub(r"\s+", " ", upper).strip()
    for pattern, category, confidence in RULES:
        if re.search(pattern, upper):
            return category, confidence
    return "Other", 0.4


def is_drop_source_label(source_label: str) -> bool:
    if source_label is None:
        return True
    upper = re.sub(r"[_\-]+", " ", str(source_label)).upper().strip()
    return any(re.search(p, upper) for p in DROP_SOURCE_PATTERNS)


def taxonomy_rows() -> list[dict]:
    return [
        {
            "pattern": pattern,
            "crime_category_normalized": category,
            "default_confidence": confidence,
        }
        for pattern, category, confidence in RULES
    ]
