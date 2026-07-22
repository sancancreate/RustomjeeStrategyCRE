"""
Maharashtra IGR Property Description Parsing Engine — Version 2
=================================================================

A modular, production-grade re-implementation of the original regex-only
parser. The engine is organised as an explicit pipeline:

    TextNormalizer -> NoiseCleaner -> PatternDetector -> AreaExtractor
    -> Validator -> ConfidenceScorer -> OutputFormatter

Each stage is a small, testable class with a single responsibility. This
keeps the engine maintainable and lets new Maharashtra IGR description
formats be added by registering a new extraction strategy instead of
bolting more regexes onto a single function.

Internally every area is normalised to SQUARE METRES. Square feet is only
computed once, right before output, using the constant SQM_TO_SQFT.

Author: Rewritten per "MASTER PROMPT FOR CODEX" (v2 rewrite).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("igr_parser")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Configuration / Constants
# ---------------------------------------------------------------------------

SQM_TO_SQFT: float = 10.7639

# Realistic bounds for a single residential/commercial unit area, in sqm.
# Anything outside this range is almost certainly a mis-captured
# registration ID, CTS number, phone number or pincode rather than an area.
MIN_REALISTIC_SQM: float = 3.0
MAX_REALISTIC_SQM: float = 2000.0  # ~21,500 sq ft ceiling

# Tolerance (in sqm) used by the Validator when checking
# total ~= carpet + attached
AREA_SUM_TOLERANCE_SQM: float = 1.0

DEVANAGARI_DIGITS: Dict[str, str] = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}

MARATHI_NUMBER_WORDS: Dict[str, int] = {
    "एक": 1, "दोन": 2, "तीन": 3, "चार": 4, "पाच": 5,
    "सहा": 6, "सात": 7, "आठ": 8, "नऊ": 9, "दहा": 10,
}

# Unit fragments (kept separate so we can tell metres from feet apart)
METER_UNIT = r"(?:चौ\s*\.?\s*म[ीि](?:टर|तर)?\s*\.?|चौरस\s*मीटर|sq\s*\.?\s*m(?:tr|eter)?s?\s*\.?|sqm|square\s*meters?)"
FEET_UNIT = r"(?:चौ\s*\.?\s*फु(?:ट)?\s*\.?|चौ\s*\.?\s*फूट|चौ\s*\.?\s*फिट|चौ\s*\.?\s*फी\.?|चौ\s*\.?\s*फू\.?|चौरस\s*फूट|sq\s*\.?\s*ft\s*\.?|sqft|sq\s*\.?\s*feet|square\s*feet)"
ANY_UNIT = rf"(?:{METER_UNIT}|{FEET_UNIT})"

NUM = r"\d+\s*(?:\.\s*\d+)?"
# 'area' word — covers both क्षेत्र and its common inflection क्षेत्रफळ
AREA_WORD = r"क्षेत्र(?:फळ)?"

# Keyword vocab used across strategies (kept centralised for maintainability)
KW_CARPET = r"(?:रेरा\s*कारपेट|कारपेट|कार्पेट|चटई)"
KW_ATTACHED = r"(?:इतर\s*लगतचे\s*क्षेत्र|संलग्न\s*क्षेत्र|लगतचे\s*क्षेत्र)"
KW_BALCONY = r"(?:बाल्कनी|बालकॉनी|गॅलरी|गॅलेरी|डेक|ओपन\s*डेक|टेरेस|balcony|gallery|deck|terrace)"
KW_UTILITY = r"(?:युटिलिटी|युटीलिटी|युटिलीटी|यूटिलीटी|यूटिलिटी|ड्राय\s*बाल्कनी|ड्राय|सर्व्हिस|utility|dry|service)"
KW_ANCILLARY = r"(?:एन्सिलरी\s*एरिया|ancillary\s*area)"
KW_TOTAL = r"(?:एकूण\s*क्षेत्रफळ|एकुण\s*क्षेत्रफळ|एकूण\s*क्षेत्र|एकुण\s*क्षेत्र|सदनिकेचे\s*एकूण\s*क्षेत्रफळ)"


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    project_name: str = "Not Mentioned"
    tower_wing: str = "Not Mentioned"
    unit_number: str = "Not Mentioned"
    carpet_sqm: float = 0.0
    attached_sqm: float = 0.0
    balcony_sqm: float = 0.0
    utility_sqm: float = 0.0
    total_sqm: float = 0.0
    parking: int = 0
    detected_pattern: str = "UNDETECTED"
    confidence: float = 0.0
    parse_status: str = "Failed"
    warnings: List[str] = field(default_factory=list)
    raw_text: str = ""

    def as_output_row(self) -> Dict[str, Any]:
        total_sqft = round(self.total_sqm * SQM_TO_SQFT, 2)
        return {
            "Project Name": self.project_name,
            "Tower/Wing": self.tower_wing,
            "Unit Number": self.unit_number,
            "Carpet Area (Sq M)": round(self.carpet_sqm, 2),
            "Attached Area (Sq M)": round(self.attached_sqm, 2),
            "Balcony Area (Sq M)": round(self.balcony_sqm, 2),
            "Utility Area (Sq M)": round(self.utility_sqm, 2),
            "Total Area (Sq M)": round(self.total_sqm, 2),
            "Total Area (Sq Ft)": total_sqft,
            "Parking": self.parking,
            "Detected Pattern": self.detected_pattern,
            "Confidence": round(self.confidence, 1),
            "Parse Status": self.parse_status,
            # Legacy-compatible columns (kept so downstream sheets / older
            # dashboards that expect the old header names keep working)
            "Carpet Area (sq ft)": round(self.carpet_sqm * SQM_TO_SQFT, 2),
            "Balcony Area (sq ft)": round(self.balcony_sqm * SQM_TO_SQFT, 2),
            "Utility Area (sq ft)": round(self.utility_sqm * SQM_TO_SQFT, 2),
            "Total Area (sq ft)": total_sqft,
            "Parking Space": str(self.parking),
        }

    def debug_row(self) -> Dict[str, Any]:
        row = self.as_output_row()
        row["Warnings"] = "; ".join(self.warnings) if self.warnings else ""
        row["Raw Description"] = self.raw_text
        return row


# ---------------------------------------------------------------------------
# Stage 1: Text Normalizer
# ---------------------------------------------------------------------------

class TextNormalizer:
    """Cleans raw cell text into a predictable, ASCII-digit string."""

    _INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
    _WHITESPACE_RE = re.compile(r"\s+")
    _THOUSAND_SEP_RE = re.compile(r"(?<=\d),(?=\d{3}\b)")

    @classmethod
    def normalize(cls, text: Any) -> str:
        if pd.isna(text):
            return ""
        text = str(text)
        # Unicode cleanup (NFKC folds full-width / compatibility chars)
        text = unicodedata.normalize("NFKC", text)
        # Remove invisible / zero-width characters
        text = cls._INVISIBLE_RE.sub("", text)
        # Common OCR / copy-paste artefacts
        text = text.replace("\xa0", " ").replace("\t", " ").replace("\n", " ").replace("\r", " ")
        # Standardise punctuation variants
        text = text.replace("–", "-").replace("—", "-").replace("‐", "-")
        text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        # Strip thousand-separator commas inside numbers (12,345 -> 12345)
        text = cls._THOUSAND_SEP_RE.sub("", text)
        # Devanagari digits -> Arabic digits
        for dev, eng in DEVANAGARI_DIGITS.items():
            text = text.replace(dev, eng)
        # Collapse whitespace
        text = cls._WHITESPACE_RE.sub(" ", text).strip()
        return text


# ---------------------------------------------------------------------------
# Stage 2: Noise Cleaner
# ---------------------------------------------------------------------------

class NoiseCleaner:
    """
    Strips or masks substrings that contain numbers which must NEVER be
    mistaken for an area: CTS numbers, survey numbers, registration /
    document IDs, phone numbers, and pincodes.
    """

    _NOISE_BLOCK_PATTERNS = [
        re.compile(r"C\.?T\.?S\.?\s*Number\s*:.*?(?=\)\)|$)", re.IGNORECASE),
        re.compile(r"सर्व्हे\s*(?:नं|क्र|नंबर)\.?\s*[:\-]?\s*[\w/,\s]+", re.IGNORECASE),
        re.compile(r"(?:दस्त|नोंदणी|डॉक्युमेंट)\s*(?:क्र|क्रमांक|नं)\.?\s*[:\-]?\s*[\w/\-]+", re.IGNORECASE),
        re.compile(r"नोटिफिकेशन\s*क्रमांक.*?(?=\(|$)", re.IGNORECASE),
    ]
    # 10-digit phone numbers / 6-digit pincodes standing alone
    _PHONE_RE = re.compile(r"\b\d{10}\b")
    _PINCODE_RE = re.compile(r"(?:मुंबई|पिन\s*कोड|pin\s*code)\s*[-:]?\s*(\d{6})\b", re.IGNORECASE)

    @classmethod
    def clean(cls, text: str) -> str:
        cleaned = text
        for pat in cls._NOISE_BLOCK_PATTERNS:
            cleaned = pat.sub(" ", cleaned)
        cleaned = cls._PHONE_RE.sub(" ", cleaned)
        cleaned = cls._PINCODE_RE.sub(" ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned


# ---------------------------------------------------------------------------
# Stage 3 + 4: Pattern Detector & Area Extractor
# ---------------------------------------------------------------------------
# Each "strategy" below owns detection (does this text match?) AND
# extraction (pull the numbers out) for one Maharashtra IGR layout family.
# PatternDetector simply tries each strategy, in priority order, and the
# first one that successfully extracts a usable area wins.

def _to_sqm(value: float, unit_hint: str) -> float:
    """Convert a raw numeric value to sqm given the unit token that followed it."""
    if re.search(METER_UNIT, unit_hint, re.IGNORECASE):
        return value
    if re.search(FEET_UNIT, unit_hint, re.IGNORECASE):
        return value / SQM_TO_SQFT
    # No unit captured: assume sqm (Maharashtra IGR overwhelmingly reports
    # RERA carpet in sqm when unlabelled in these clauses).
    return value


def _safe_float(s: str) -> Optional[float]:
    try:
        return float(re.sub(r"\s+", "", s))
    except (TypeError, ValueError):
        return None


def _find_labeled_area(text: str, label_re: str) -> Optional[Tuple[float, str]]:
    """
    Finds a NUM+UNIT associated with a label, regardless of whether the
    label appears before the number (optionally with 1-3 filler words in
    between, e.g. 'बाल्कनी स्पेस क्षेत्रफळ 36 चौ. फुट') or after it
    (e.g. 'क्षेत्रफळ 832 चौ. फुट कार्पेट').
    """
    forward = re.compile(
        rf"{label_re}(?:\s+[^\s,.]+){{0,3}}?\s*{AREA_WORD}?\s*[-:=]?\s*({NUM})\s*({ANY_UNIT})?",
        re.IGNORECASE,
    )
    backward = re.compile(
        rf"{AREA_WORD}?\s*[-:=]?\s*({NUM})\s*({ANY_UNIT})?(?:\s+[^\s,.]+){{0,2}}?\s*{label_re}",
        re.IGNORECASE,
    )
    for pat in (forward, backward):
        m = pat.search(text)
        if m:
            val = _safe_float(m.group(1))
            if val is not None:
                return val, (m.group(2) or "")
    return None


class AreaStrategy:
    """Base class for a single detectable IGR area-description layout."""

    name: str = "BASE"

    def try_extract(self, text: str) -> Optional[Dict[str, float]]:
        """Return a dict of sqm areas if this strategy matches, else None."""
        raise NotImplementedError


class LabeledCarpetAttachedStrategy(AreaStrategy):
    """
    Pattern A: 'क्षेत्रफळ 64.40 चौ. मीटर रेरा कारपेट व इतर लगतचे क्षेत्र 4.78
    चौ. मी. यांचे एकुण क्षेत्र 69.18 चौ. मी.'
    Pattern B: 'क्षेत्र-66.88 चौ. मीटर कारपेट व इतर लगतचे क्षेत्र-5.27 चौ.
    मीटर यांसी एकूण क्षेत्र-72.15 चौ. मीटर कारपेट.'
    Carpet + explicit attached area + explicit total, in the same unit.
    """

    name = "LABELED_CARPET_ATTACHED"

    _RE = re.compile(
        rf"क्षेत्रफळ?\s*[-:]?\s*({NUM})\s*({ANY_UNIT})\s*(?:रेरा\s*)?{KW_CARPET}?"
        rf".{{0,15}}?{KW_ATTACHED}\s*[-:]?\s*({NUM})\s*({ANY_UNIT})"
        rf".{{0,20}}?{KW_TOTAL}\s*[-:]?\s*({NUM})\s*({ANY_UNIT})",
        re.IGNORECASE,
    )

    def try_extract(self, text: str) -> Optional[Dict[str, float]]:
        m = self._RE.search(text)
        if not m:
            return None
        carpet = _safe_float(m.group(1))
        attached = _safe_float(m.group(3))
        total = _safe_float(m.group(5))
        if carpet is None or attached is None or total is None:
            return None
        carpet_sqm = _to_sqm(carpet, m.group(2))
        attached_sqm = _to_sqm(attached, m.group(4))
        total_sqm = _to_sqm(total, m.group(6))
        return {
            "carpet_sqm": carpet_sqm,
            "attached_sqm": attached_sqm,
            "balcony_sqm": 0.0,
            "utility_sqm": 0.0,
            "total_sqm": total_sqm,
        }


class EnglishDualUnitCarpetAncillaryStrategy(AreaStrategy):
    """
    Pattern D/E: 'कारपेट एरिया 105.290 चौ. मी. म्हणजेच 1133.342 चौ. फूट. व
    एन्सिलरी एरिया 11.970 चौ. मी. म्हणजेच 128.845 चौ. फूट'
    Carpet + ancillary/attached area, each given in both sqm and sqft
    (we only need the sqm figure, which appears first).
    """

    name = "CARPET_ANCILLARY_DUAL_UNIT"

    _RE = re.compile(
        rf"{KW_CARPET}\s*एरिया\s*({NUM})\s*({METER_UNIT})"
        rf".{{0,40}}?{KW_ANCILLARY}\s*({NUM})\s*({METER_UNIT})",
        re.IGNORECASE,
    )

    def try_extract(self, text: str) -> Optional[Dict[str, float]]:
        m = self._RE.search(text)
        if not m:
            return None
        carpet = _safe_float(m.group(1))
        attached = _safe_float(m.group(3))
        if carpet is None or attached is None:
            return None
        carpet_sqm = _to_sqm(carpet, m.group(2))
        attached_sqm = _to_sqm(attached, m.group(4))
        return {
            "carpet_sqm": carpet_sqm,
            "attached_sqm": attached_sqm,
            "balcony_sqm": 0.0,
            "utility_sqm": 0.0,
            "total_sqm": round(carpet_sqm + attached_sqm, 4),
        }


class BalconyUtilityBreakdownStrategy(AreaStrategy):
    """
    Pattern B/F: carpet, balcony and utility areas explicitly and
    separately labelled (rather than lumped into one 'attached' figure).
    """

    name = "CARPET_BALCONY_UTILITY"

    def try_extract(self, text: str) -> Optional[Dict[str, float]]:
        b = _find_labeled_area(text, KW_BALCONY)
        u = _find_labeled_area(text, KW_UTILITY)
        if not (b or u):
            return None
        c = _find_labeled_area(text, KW_CARPET)
        carpet_sqm = _to_sqm(c[0], c[1]) if c else 0.0
        balcony_sqm = _to_sqm(b[0], b[1]) if b else 0.0
        utility_sqm = _to_sqm(u[0], u[1]) if u else 0.0
        if carpet_sqm == 0.0 and balcony_sqm == 0.0 and utility_sqm == 0.0:
            return None
        return {
            "carpet_sqm": carpet_sqm,
            "attached_sqm": 0.0,
            "balcony_sqm": balcony_sqm,
            "utility_sqm": utility_sqm,
            "total_sqm": round(carpet_sqm + balcony_sqm + utility_sqm, 4),
        }


class ExplicitTotalOnlyStrategy(AreaStrategy):
    """
    Pattern C: only a single total/carpet figure is stated, e.g.
    'सदनिका क्र. 2703,क्षेत्र 1283 चौ. फुट रेरा कारपेट'
    'सदनिकेचे एकूण क्षेत्रफळ 2251.50 चौ.फूट.'
    """

    name = "TOTAL_ONLY"

    _PATTERNS = [
        re.compile(rf"{KW_TOTAL}\s*[-:]?\s*({NUM})\s*({ANY_UNIT})", re.IGNORECASE),
        re.compile(rf"{AREA_WORD}\s*[-:]?\s*({NUM})\s*({ANY_UNIT})\s*(?:रेरा\s*)?{KW_CARPET}", re.IGNORECASE),
        re.compile(rf"{KW_CARPET}\s*(?:एरिया|{AREA_WORD})?\s*[-:=]?\s*({NUM})\s*({ANY_UNIT})", re.IGNORECASE),
        re.compile(rf"Area\s*of\s*Constructed\s*Property\s*[-:=]?\s*({NUM})\s*({ANY_UNIT})", re.IGNORECASE),
    ]
    # A bare number directly followed by 'रेरा कारपेट' with NO unit token at
    # all, e.g. '100.90 रेरा कारपेट'. Maharashtra RERA carpet-area figures
    # are conventionally reported in sqm when no unit is given, so we treat
    # this as sqm. Kept separate (and tried last) since it's a weaker,
    # unit-less signal.
    _BARE_RERA_CARPET_RE = re.compile(rf"\b({NUM})\s*रेरा\s*कारपेट", re.IGNORECASE)

    def try_extract(self, text: str) -> Optional[Dict[str, float]]:
        for pat in self._PATTERNS:
            m = pat.search(text)
            if not m:
                continue
            val = _safe_float(m.group(1))
            if val is None:
                continue
            total_sqm = _to_sqm(val, m.group(2))
            return {
                "carpet_sqm": total_sqm,
                "attached_sqm": 0.0,
                "balcony_sqm": 0.0,
                "utility_sqm": 0.0,
                "total_sqm": total_sqm,
            }
        # Fallback: label-flexible search (handles filler words / label
        # appearing after the number, e.g. 'सदनिकेचे क्षेत्रफळ 832 चौ. फुट कार्पेट')
        found = _find_labeled_area(text, KW_CARPET)
        if found:
            total_sqm = _to_sqm(found[0], found[1])
            return {
                "carpet_sqm": total_sqm,
                "attached_sqm": 0.0,
                "balcony_sqm": 0.0,
                "utility_sqm": 0.0,
                "total_sqm": total_sqm,
            }
        # Last resort: bare number immediately before 'रेरा कारपेट' with no
        # unit token at all — assume sqm.
        m = self._BARE_RERA_CARPET_RE.search(text)
        if m:
            val = _safe_float(m.group(1))
            if val is not None and MIN_REALISTIC_SQM <= val <= MAX_REALISTIC_SQM:
                return {
                    "carpet_sqm": val,
                    "attached_sqm": 0.0,
                    "balcony_sqm": 0.0,
                    "utility_sqm": 0.0,
                    "total_sqm": val,
                }
        return None


class ChainedPlusEquationStrategy(AreaStrategy):
    """
    Pattern G/H: figures joined with '+' such as
    '64.40 चौ.मी. कारपेट + 4.78 चौ.मी. बाल्कनी + 2.10 चौ.मी. युटिलिटी'
    """

    name = "CHAINED_PLUS"

    _TERM_RE = re.compile(rf"({NUM})\s*({ANY_UNIT})", re.IGNORECASE)

    def try_extract(self, text: str) -> Optional[Dict[str, float]]:
        if "+" not in text:
            return None
        segments = text.split("+")
        carpet = balcony = utility = attached = 0.0
        any_found = False
        for idx, seg in enumerate(segments):
            m = self._TERM_RE.search(seg)
            if not m:
                continue
            val = _safe_float(m.group(1))
            if val is None:
                continue
            sqm_val = _to_sqm(val, m.group(2))
            if not (MIN_REALISTIC_SQM * 0.1 <= sqm_val <= MAX_REALISTIC_SQM):
                continue
            any_found = True
            seg_lower = seg.lower()
            if re.search(KW_UTILITY, seg_lower, re.IGNORECASE):
                utility += sqm_val
            elif re.search(KW_BALCONY, seg_lower, re.IGNORECASE):
                balcony += sqm_val
            elif re.search(KW_CARPET, seg_lower, re.IGNORECASE):
                carpet += sqm_val
            elif re.search(KW_ATTACHED, seg_lower, re.IGNORECASE):
                attached += sqm_val
            elif idx == 0 and carpet == 0.0:
                carpet += sqm_val
            elif balcony == 0.0:
                balcony += sqm_val
            elif utility == 0.0:
                utility += sqm_val
        if not any_found:
            return None
        return {
            "carpet_sqm": carpet,
            "attached_sqm": attached,
            "balcony_sqm": balcony,
            "utility_sqm": utility,
            "total_sqm": round(carpet + attached + balcony + utility, 4),
        }


class NarrativeConversionCarpetStrategy(AreaStrategy):
    """
    Pattern K: a narrative sentence where the carpet figure is given in one
    unit, restated in the other via 'म्हणजेच' (i.e./meaning), with the
    carpet label appearing only after both numbers, e.g.:
    '63.96 चौ.मी. म्हणजेच 688 चौ.फु. रेरा कारपेट क्षेत्रफळाच्या सदनिके
     सोबत 3.25 चौ.मी. क्षेत्रफळाची बाल्कनी तसेच 1.77 चौ.मी. ...युटीलिटी'
    Only the first (leading) figure is needed — _to_sqm converts whichever
    unit it's in, and since both figures denote the same area, picking
    either is correct.
    """

    name = "NARRATIVE_CONVERSION_CARPET"

    _RE = re.compile(
        rf"({NUM})\s*({ANY_UNIT})\.?\s*म्हणजेच\s*{NUM}\s*{ANY_UNIT}\.?\s*(?:रेरा\s*)?{KW_CARPET}",
        re.IGNORECASE,
    )

    def try_extract(self, text: str) -> Optional[Dict[str, float]]:
        m = self._RE.search(text)
        if not m:
            return None
        val = _safe_float(m.group(1))
        if val is None:
            return None
        carpet_sqm = _to_sqm(val, m.group(2))

        # Balcony / utility are often given separately later in the same
        # sentence ('सोबत X चौ.मी. क्षेत्रफळाची बाल्कनी', 'तसेच Y चौ.मी.
        # क्षेत्रफळाचे युटीलिटी एरिया'); reuse the flexible label finder.
        b = _find_labeled_area(text, KW_BALCONY)
        u = _find_labeled_area(text, KW_UTILITY)
        balcony_sqm = _to_sqm(b[0], b[1]) if b else 0.0
        utility_sqm = _to_sqm(u[0], u[1]) if u else 0.0

        return {
            "carpet_sqm": carpet_sqm,
            "attached_sqm": 0.0,
            "balcony_sqm": balcony_sqm,
            "utility_sqm": utility_sqm,
            "total_sqm": round(carpet_sqm + balcony_sqm + utility_sqm, 4),
        }


class UnqualifiedAreaStrategy(AreaStrategy):
    """
    Pattern L: the unit's area is stated but with NO carpet/RERA/total
    qualifier at all — just 'क्षेत्रफळ 97.80 चौ. मी.' or '463 चौ फिट'
    on its own, sometimes followed by 'बिल्टअप' (built-up).

    This is deliberately tried LAST among the text-based strategies
    (lowest precision) and explicitly skips any 'क्षेत्रफळ'/'क्षेत्र'
    mention that is actually describing a PARKING SPACE's area rather
    than the unit's, e.g. 'पार्किंग(क्षेत्र 11.15 चौ. मी.)' or
    'इनक्लोज पार्किंग क्षेत्रफळ 13.94 चौ. मी.' — those must never be
    mistaken for the flat's carpet area.
    """

    name = "UNQUALIFIED_AREA"

    _LABELED_RE = re.compile(
        rf"(?:सदनिकेचे\s*)?(?:{AREA_WORD}|एरिया)\s*[-:]?\s*({NUM})\s*({ANY_UNIT})\s*(?:बिल्ट\s*अप|बिल्टअप)?",
        re.IGNORECASE,
    )
    _BARE_UNIT_RE = re.compile(rf"({NUM})\s*({ANY_UNIT})\s*(?:कारपेट|कार्पेट)?", re.IGNORECASE)
    _PARKING_CONTEXT_RE = re.compile(r"पार्क", re.IGNORECASE)

    def try_extract(self, text: str) -> Optional[Dict[str, float]]:
        for pat in (self._LABELED_RE, self._BARE_UNIT_RE):
            for m in pat.finditer(text):
                val = _safe_float(m.group(1))
                if val is None:
                    continue
                # Look back a short window to make sure this isn't a
                # parking space's area, e.g. '...पार्किंग(क्षेत्र 11.15...)'
                window_start = max(0, m.start() - 30)
                preceding = text[window_start:m.start()]
                # Only treat as parking-space area if the parking mention is
                # NOT separated from this area figure by a comma / field
                # boundary — e.g. block 'पार्किंग(क्षेत्र 11.15...)' and
                # 'पार्किंग क्षेत्रफळ 13.94...', but do NOT block
                # 'पार्किंग 2,एरिया-1116...' where पार्किंग belongs to an
                # unrelated preceding field.
                park_match = self._PARKING_CONTEXT_RE.search(preceding)
                if park_match:
                    between = preceding[park_match.end():]
                    if "," not in between:
                        continue
                total_sqm = _to_sqm(val, m.group(2))
                if not (MIN_REALISTIC_SQM <= total_sqm <= MAX_REALISTIC_SQM):
                    continue
                return {
                    "carpet_sqm": total_sqm,
                    "attached_sqm": 0.0,
                    "balcony_sqm": 0.0,
                    "utility_sqm": 0.0,
                    "total_sqm": total_sqm,
                }
        return None


class PatternDetector:
    """
    Chooses the best-matching extraction strategy for a normalised,
    noise-cleaned description. Strategies are tried in priority order
    (most specific / most reliable first); the first successful
    extraction wins.
    """

    # Priority order matters: the more specific / structured a layout is,
    # the earlier it should be tried.
    STRATEGIES: List[AreaStrategy] = [
        LabeledCarpetAttachedStrategy(),
        NarrativeConversionCarpetStrategy(),
        EnglishDualUnitCarpetAncillaryStrategy(),
        BalconyUtilityBreakdownStrategy(),
        ChainedPlusEquationStrategy(),
        ExplicitTotalOnlyStrategy(),
        UnqualifiedAreaStrategy(),
    ]

    @classmethod
    def extract(cls, text: str) -> Tuple[Dict[str, float], str]:
        for strategy in cls.STRATEGIES:
            try:
                result = strategy.try_extract(text)
            except Exception as exc:  # noqa: BLE001 - defensive, log & continue
                logger.debug("Strategy %s raised %s", strategy.name, exc)
                continue
            if result:
                return result, strategy.name
        return (
            {"carpet_sqm": 0.0, "attached_sqm": 0.0, "balcony_sqm": 0.0, "utility_sqm": 0.0, "total_sqm": 0.0},
            "UNDETECTED",
        )


# ---------------------------------------------------------------------------
# Stage 5: Validator
# ---------------------------------------------------------------------------

class Validator:
    """Sanity-checks extracted area figures."""

    @staticmethod
    def validate(areas: Dict[str, float]) -> List[str]:
        warnings: List[str] = []
        total = areas.get("total_sqm", 0.0)
        carpet = areas.get("carpet_sqm", 0.0)
        parts_sum = (
            areas.get("carpet_sqm", 0.0)
            + areas.get("attached_sqm", 0.0)
            + areas.get("balcony_sqm", 0.0)
            + areas.get("utility_sqm", 0.0)
        )

        if total <= 0 and carpet <= 0:
            warnings.append("No usable area extracted")
            return warnings

        if total > MAX_REALISTIC_SQM:
            warnings.append(f"Total area {total:.2f} sqm exceeds realistic ceiling")
        if 0 < total < MIN_REALISTIC_SQM:
            warnings.append(f"Total area {total:.2f} sqm below realistic floor")

        # Only compare independently-derived total vs the sum of parts when
        # both a genuine 'total' and 'parts' figure exist separately
        # (LabeledCarpetAttachedStrategy is the main case where this applies)
        if total > 0 and parts_sum > 0 and abs(total - parts_sum) > AREA_SUM_TOLERANCE_SQM:
            # allow it if total IS parts_sum (i.e. same source, rounding-only diff)
            if abs(total - parts_sum) / max(total, 1e-6) > 0.05:
                warnings.append(
                    f"Total ({total:.2f}) does not reconcile with parts sum ({parts_sum:.2f})"
                )
        return warnings


# ---------------------------------------------------------------------------
# Stage 6: Confidence Scorer
# ---------------------------------------------------------------------------

class ConfidenceScorer:
    """Produces a 0-100 confidence score for a parsed row."""

    @staticmethod
    def score(
        pattern: str,
        areas: Dict[str, float],
        warnings: List[str],
        project_found: bool,
        unit_found: bool,
    ) -> float:
        if pattern == "UNDETECTED" or areas.get("total_sqm", 0.0) <= 0:
            return 0.0

        score = 0.0
        score += 45.0  # a usable total area was extracted
        if areas.get("carpet_sqm", 0.0) > 0:
            score += 15.0
        if pattern in ("LABELED_CARPET_ATTACHED", "CARPET_ANCILLARY_DUAL_UNIT"):
            score += 10.0  # these patterns give an explicit, unambiguous total
        if pattern == "UNQUALIFIED_AREA":
            score -= 10.0  # area stated, but without an explicit carpet/total label
        if project_found:
            score += 12.0
        if unit_found:
            score += 12.0
        score -= 8.0 * len(warnings)
        score = max(0.0, min(100.0, score))
        return score


# ---------------------------------------------------------------------------
# Field extraction helpers (project / tower / unit / parking)
# ---------------------------------------------------------------------------

class FieldExtractor:
    """Extracts non-area structured fields from the description text."""

    _PROJECT_RE = re.compile(r"इमारतीचे\s*नाव\s*[:\-]\s*([^,]+)", re.IGNORECASE)
    _PROJECT_FALLBACK_RE = re.compile(
        r"([\w\s\-]+?)\s*(?:प्रोजेक्ट|फेज|प्रकल्प|गार्डन्स|रेसिडेन्सी)", re.IGNORECASE
    )

    _WING_DASH_RE = re.compile(r"विंग\s*-\s*([A-Za-zअ-ह0-9]+)", re.IGNORECASE)
    _WING_PREFIX_RE = re.compile(r"\b([A-Za-zअ-ह])\s*विंग\b", re.IGNORECASE)
    _TOWER_NO_RE = re.compile(r"टॉवर\s*(?:नं|क्र|क्रमांक)\.?\s*([A-Za-z0-9अ-ह]+)", re.IGNORECASE)
    _TOWER_LETTER_RE = re.compile(r"टॉवर\s+(?!नं|क्र)([A-Za-zअ-ह])\b", re.IGNORECASE)
    _BUILDING_NO_RE = re.compile(
        r"(?:बिल्डिंग|बिल्डींग)\s*(?:नं|क्र|क्रमांक|नंबर)?\.?\s*([A-Za-z0-9\-]+)", re.IGNORECASE
    )

    _UNIT_SEGMENT_RE = re.compile(
        r"(?:सदनिका|फ्लॅट|शॉप|दुकान|गाळा)\s*(?:नं|क्र|क्रमांक)?\.?\s*[:.\-]?\s*(.{0,40}?)(?:,|माळा|$)",
        re.IGNORECASE,
    )
    _DIGIT_TOKEN_RE = re.compile(r"([0-9]{2,6}[A-Za-z]?)")

    _PARKING_NUM_WORD = "|".join(MARATHI_NUMBER_WORDS.keys())
    _PARKING_RE = re.compile(
        rf"({_PARKING_NUM_WORD}|[0-9]+)?\s*(?:सिंगल\s*)?(?:कव्हर्ड\s*)?कार\s*पार्क\S{{0,4}}ग",
        re.IGNORECASE,
    )

    @classmethod
    def project_name(cls, text: str, row_context: Optional[pd.Series], project_col: Optional[str]) -> str:
        if row_context is not None and project_col and project_col in row_context and pd.notna(row_context[project_col]):
            val = str(row_context[project_col]).strip()
            return val[:-2] if val.endswith(".0") else val
        m = cls._PROJECT_RE.search(text)
        if m:
            return m.group(1).strip(" -")
        m = cls._PROJECT_FALLBACK_RE.search(text)
        if m:
            return m.group(1).strip(" -")
        return "Not Mentioned"

    @classmethod
    def tower_wing(cls, text: str, row_context: Optional[pd.Series], tower_col: Optional[str]) -> str:
        if row_context is not None and tower_col and tower_col in row_context and pd.notna(row_context[tower_col]):
            val = str(row_context[tower_col]).strip()
            return val[:-2] if val.endswith(".0") else val
        for pat in (cls._WING_DASH_RE, cls._WING_PREFIX_RE, cls._TOWER_NO_RE, cls._TOWER_LETTER_RE, cls._BUILDING_NO_RE):
            m = pat.search(text)
            if m:
                return m.group(1).strip()
        return "Not Mentioned"

    @classmethod
    def unit_number(cls, text: str, row_context: Optional[pd.Series], unit_col: Optional[str]) -> str:
        if row_context is not None and unit_col and unit_col in row_context and pd.notna(row_context[unit_col]):
            val = row_context[unit_col]
            if isinstance(val, (int, float)):
                out = str(int(val)) if float(val).is_integer() else str(val).strip()
            else:
                out = str(val).strip()
            return out[:-2] if out.endswith(".0") else out

        m = cls._UNIT_SEGMENT_RE.search(text)
        if m:
            segment = m.group(1)
            tokens = cls._DIGIT_TOKEN_RE.findall(segment)
            if tokens:
                return tokens[-1]
        return "Not Mentioned"

    @classmethod
    def parking(cls, text: str) -> int:
        m = cls._PARKING_RE.search(text)
        if m:
            token = (m.group(1) or "").strip()
            if not token:
                return 1
            if token.isdigit():
                return int(token)
            return MARATHI_NUMBER_WORDS.get(token, 1)
        if "पार्किंग" in text or "पार्कींग" in text or "पार्किग" in text:
            return 1
        return 0


# ---------------------------------------------------------------------------
# Column auto-detection helper (used by app.py)
# ---------------------------------------------------------------------------

def locate_column_by_keywords(df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
    """Finds the first dataframe column whose header contains any keyword."""
    for col in df.columns:
        col_lower = str(col).lower()
        if any(k.lower() in col_lower for k in keywords):
            return col
    return None


def auto_detect_description_column(df: pd.DataFrame, sample_rows: int = 50) -> Optional[str]:
    """
    Intelligent detection of the free-text property-description column:
    first tries header keywords, then falls back to scoring each column by
    the density of Marathi IGR vocabulary found in a text sample.
    """
    header_guess = locate_column_by_keywords(
        df, ["property description", "description", "वर्णन", "मालमत्ता"]
    )
    if header_guess:
        return header_guess

    vocab = ["कारपेट", "क्षेत्र", "सदनिका", "फ्लॅट", "मजला", "विंग", "पालिकेचे"]
    best_col, best_score = None, 0
    sample = df.head(sample_rows)
    for col in df.columns:
        try:
            series = sample[col].dropna().astype(str)
        except Exception:  # noqa: BLE001
            continue
        if series.empty:
            continue
        hits = sum(1 for v in series if any(k in v for k in vocab))
        avg_len = series.str.len().mean()
        score = hits * 10 + (avg_len if avg_len and avg_len > 80 else 0) / 20
        if score > best_score:
            best_score, best_col = score, col
    return best_col


# ---------------------------------------------------------------------------
# Top-level orchestration (Output Formatter lives inside ParseResult)
# ---------------------------------------------------------------------------

def parse_property_description(
    raw_text: Any,
    row_context: Optional[pd.Series] = None,
    project_col: Optional[str] = None,
    tower_col: Optional[str] = None,
    unit_col: Optional[str] = None,
    fallback_area_sqft: Optional[float] = None,
) -> ParseResult:
    """
    Runs the full pipeline for a single description and returns a
    ParseResult. This is the main entry point used by app.py.

    fallback_area_sqft: if provided (e.g. from a structured 'Area' column
    that already exists in the source spreadsheet) and the free-text
    description does not itself state an area, this value is used as the
    total/carpet area instead of leaving the row unparsed. This commonly
    happens in IGR extracts where only *some* rows spell the area out in
    the Marathi description while a separate numeric column always has it.
    """
    normalized = TextNormalizer.normalize(raw_text)
    cleaned = NoiseCleaner.clean(normalized)

    areas, pattern = PatternDetector.extract(cleaned)

    used_fallback = False
    if areas.get("total_sqm", 0.0) <= 0 and fallback_area_sqft and fallback_area_sqft > 0:
        fallback_sqm = fallback_area_sqft / SQM_TO_SQFT
        areas = {
            "carpet_sqm": fallback_sqm,
            "attached_sqm": 0.0,
            "balcony_sqm": 0.0,
            "utility_sqm": 0.0,
            "total_sqm": fallback_sqm,
        }
        pattern = "AREA_COLUMN_FALLBACK"
        used_fallback = True

    warnings = Validator.validate(areas)
    if used_fallback:
        warnings.append("Area taken from spreadsheet Area column; not stated in description text")

    project_name = FieldExtractor.project_name(cleaned, row_context, project_col)
    tower_wing = FieldExtractor.tower_wing(cleaned, row_context, tower_col)
    unit_number = FieldExtractor.unit_number(cleaned, row_context, unit_col)
    parking = FieldExtractor.parking(cleaned)

    confidence = ConfidenceScorer.score(
        pattern=pattern,
        areas=areas,
        warnings=warnings,
        project_found=project_name != "Not Mentioned",
        unit_found=unit_number != "Not Mentioned",
    )
    if used_fallback:
        confidence = min(confidence, 60.0)  # cap confidence: figure wasn't verified against the text

    if areas.get("total_sqm", 0.0) > 0 and not warnings:
        status = "Success"
    elif areas.get("total_sqm", 0.0) > 0 or areas.get("carpet_sqm", 0.0) > 0:
        status = "Partial"
    else:
        status = "Failed"

    return ParseResult(
        project_name=project_name,
        tower_wing=tower_wing,
        unit_number=unit_number,
        carpet_sqm=areas.get("carpet_sqm", 0.0),
        attached_sqm=areas.get("attached_sqm", 0.0),
        balcony_sqm=areas.get("balcony_sqm", 0.0),
        utility_sqm=areas.get("utility_sqm", 0.0),
        total_sqm=areas.get("total_sqm", 0.0),
        parking=parking,
        detected_pattern=pattern,
        confidence=confidence,
        parse_status=status,
        warnings=warnings,
        raw_text=normalized,
    )


# ---------------------------------------------------------------------------
# Backwards-compatible wrapper
# ---------------------------------------------------------------------------
# app.py (and any external caller) expects a function called
# extract_marathi_property_details returning a flat dict, exactly like the
# original v1 engine. We keep that name/signature so the rest of the app,
# and anyone else importing this module, doesn't break.

def extract_marathi_property_details(
    raw_text: Any,
    row_context: Optional[pd.Series] = None,
    project_col: Optional[str] = None,
    tower_col: Optional[str] = None,
    unit_col: Optional[str] = None,
    fallback_area_sqft: Optional[float] = None,
) -> Dict[str, Any]:
    result = parse_property_description(
        raw_text, row_context, project_col, tower_col, unit_col, fallback_area_sqft
    )
    return result.as_output_row()
