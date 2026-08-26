"""Loss-aware Path of Exile 2 clipboard parser.

The parser extracts only information present in clipboard text. It does not
look up tiers, infer affix capacity, enrich modifiers, or model mechanics.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from .api import ApiError, ApiErrorCode, ParseItemResponse
from .domain import (
    AffixState,
    AffixType,
    ClipboardFormat,
    Confidence,
    ConfidenceLevel,
    GameContext,
    ItemModifier,
    ItemSpecialState,
    ModifierOrigin,
    ParsedItem,
    Rarity,
    RollValue,
)


SECTION_SEPARATOR = "--------"
HEADER_RE = re.compile(
    r"^\{\s*(?P<meta>.+?)(?:\s+Modifier)?(?:\s+\"(?P<name>[^\"]+)\")?"
    r"(?:\s+\(Tier:\s*(?P<tier>[^)]+)\))?"
    r"(?:\s+[\u2014-]\s*(?P<tags>.+?))?\s*\}$"
)
VALUE_WITH_RANGE_RE = re.compile(
    r"(?P<observed>[+-]?\d+(?:\.\d+)?)(?:\((?P<low>[+-]?\d+(?:\.\d+)?)"
    r"(?:-(?P<high>[+-]?\d+(?:\.\d+)?))?\))?"
)


@dataclass(frozen=True)
class ParseResult:
    item: ParsedItem | None
    error: ApiError | None = None
    detected_format: ClipboardFormat = ClipboardFormat.UNKNOWN
    warnings: tuple[str, ...] = ()
    unparsed_sections: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModifierHeader:
    affix_type: AffixType
    origin: ModifierOrigin
    display_name: str | None
    tier: str | None
    tags: tuple[str, ...]
    raw_header: str


def parse_clipboard_item(
    raw_clipboard_text: str,
    game_context: GameContext | None = None,
) -> ParseResult:
    normalized = normalize_clipboard(raw_clipboard_text)
    if not normalized:
        error = ApiError(
            code=ApiErrorCode.VALIDATION_ERROR,
            message="Clipboard text is empty.",
            reliable_no_result=True,
        )
        return ParseResult(item=None, error=error)

    lines = normalized.splitlines()
    if not any(line.startswith("Item Class:") for line in lines) or not any(
        line.startswith("Rarity:") for line in lines
    ):
        error = ApiError(
            code=ApiErrorCode.PARSE_FAILURE,
            message="Clipboard text does not look like a supported PoE item.",
            reliable_no_result=True,
        )
        return ParseResult(item=None, error=error)

    sections = split_sections(lines)
    clipboard_format = detect_clipboard_format(lines)
    warnings: list[str] = []
    item_class, rarity, item_name, base_type = parse_header(sections[0])
    required_level = parse_required_level(sections)
    item_level = parse_item_level(sections)
    modifiers, implicit_modifiers, explicit_modifiers, special_modifiers = parse_modifiers(
        sections, warnings
    )
    prefixes = tuple(
        modifier for modifier in explicit_modifiers if modifier.affix_type == AffixType.PREFIX
    )
    suffixes = tuple(
        modifier for modifier in explicit_modifiers if modifier.affix_type == AffixType.SUFFIX
    )
    special_states = parse_special_states(lines)
    granted_skills = tuple(
        line.removeprefix("Grants Skill:").strip()
        for line in lines
        if line.startswith("Grants Skill:")
    )
    trade_note = next(
        (line.removeprefix("Note:").strip() for line in lines if line.startswith("Note:")),
        None,
    )
    equipment_restrictions = tuple(
        line for line in lines if line.startswith("Can only be equipped")
    )
    unparsed_lines = find_unparsed_lines(sections)
    unparsed_sections = find_unparsed_sections(sections)
    if unparsed_lines:
        warnings.append("Some lines were preserved as unparsed text.")
    if unparsed_sections:
        warnings.append("Some sections were preserved as wholly unparsed text.")
    if clipboard_format == ClipboardFormat.NORMAL:
        warnings.append("Normal copy lacks explicit modifier metadata; tiers and affix types may be unknown.")

    confidence = parser_confidence(clipboard_format, warnings)
    item = ParsedItem(
        analysis_id=generate_analysis_id(),
        raw_clipboard_text=normalized,
        game_context=game_context or GameContext(game="Path of Exile 2"),
        clipboard_format=clipboard_format,
        rarity=rarity,
        item_name=item_name,
        item_class=item_class,
        base_type=base_type,
        required_level=required_level,
        item_level=item_level,
        properties={},
        modifiers=modifiers,
        implicit_modifiers=implicit_modifiers,
        explicit_modifiers=explicit_modifiers,
        special_modifiers=special_modifiers,
        affix_state=AffixState(
            known_prefixes=prefixes,
            known_suffixes=suffixes,
            observed_prefix_count=len(prefixes),
            observed_suffix_count=len(suffixes),
            uncertainty=confidence,
        ),
        special_states=special_states,
        granted_skills=granted_skills,
        trade_note=trade_note,
        equipment_restrictions=equipment_restrictions,
        raw_sections=tuple("\n".join(section) for section in sections),
        unparsed_lines=unparsed_lines,
        warnings=tuple(warnings),
        parser_confidence=confidence,
    )
    return ParseResult(
        item=item,
        detected_format=clipboard_format,
        warnings=tuple(warnings),
        unparsed_sections=unparsed_sections,
    )


def parse_item_request(raw_clipboard_text: str, game_context: GameContext | None = None) -> ParseItemResponse:
    result = parse_clipboard_item(raw_clipboard_text, game_context)
    return ParseItemResponse(
        item=result.item,
        detected_format=result.detected_format,
        warnings=result.warnings,
        unparsed_sections=result.unparsed_sections,
        error=result.error,
    )


def normalize_clipboard(raw_text: str) -> str:
    return "\n".join(line.rstrip() for line in raw_text.replace("\r\n", "\n").split("\n")).strip()


def split_sections(lines: list[str]) -> list[list[str]]:
    sections: list[list[str]] = [[]]
    for line in lines:
        if line.strip() == SECTION_SEPARATOR:
            sections.append([])
        else:
            sections[-1].append(line)
    return [section for section in sections if section]


def generate_analysis_id() -> str:
    if not hasattr(uuid, "uuid7"):
        raise RuntimeError("DonnieCraftShell requires Python with stdlib uuid.uuid7 support.")
    return f"analysis-{uuid.uuid7()}"


def detect_clipboard_format(lines: list[str]) -> ClipboardFormat:
    if any(HEADER_RE.match(line) for line in lines):
        return ClipboardFormat.ADVANCED
    if any(line.startswith("Item Class:") for line in lines):
        return ClipboardFormat.NORMAL
    return ClipboardFormat.UNKNOWN


def parse_header(section: list[str]) -> tuple[str | None, Rarity, str | None, str | None]:
    item_class = None
    rarity = Rarity.UNKNOWN
    remainder: list[str] = []
    for line in section:
        if line.startswith("Item Class:"):
            item_class = line.removeprefix("Item Class:").strip()
        elif line.startswith("Rarity:"):
            rarity_text = line.removeprefix("Rarity:").strip().upper()
            rarity = Rarity.__members__.get(rarity_text, Rarity.UNKNOWN)
        else:
            remainder.append(line)

    if rarity in {Rarity.RARE, Rarity.UNIQUE} and len(remainder) >= 2:
        return item_class, rarity, remainder[0], remainder[1]
    if rarity == Rarity.MAGIC and remainder:
        full_name = remainder[0]
        base_type = infer_base_type_from_item_name(item_class, full_name)
        return item_class, rarity, full_name, base_type
    if rarity == Rarity.NORMAL and remainder:
        return item_class, rarity, None, remainder[0]
    return item_class, rarity, remainder[0] if remainder else None, remainder[-1] if remainder else None


def parse_required_level(sections: list[list[str]]) -> int | None:
    for section in sections:
        for line in section:
            match = re.search(r"Requires:\s*Level\s+(\d+)", line)
            if match:
                return int(match.group(1))
    return None


def parse_item_level(sections: list[list[str]]) -> int | None:
    for section in sections:
        for line in section:
            match = re.search(r"Item Level:\s*(\d+)", line)
            if match:
                return int(match.group(1))
    return None


def parse_modifiers(
    sections: list[list[str]], warnings: list[str]
) -> tuple[tuple[ItemModifier, ...], tuple[ItemModifier, ...], tuple[ItemModifier, ...], tuple[ItemModifier, ...]]:
    all_modifiers: list[ItemModifier] = []
    implicit: list[ItemModifier] = []
    explicit: list[ItemModifier] = []
    special: list[ItemModifier] = []

    for section in sections[1:]:
        index = 0
        while index < len(section):
            line = section[index]
            header = parse_modifier_header(line)
            if header is None:
                if looks_like_normal_modifier_line(line):
                    modifier = build_normal_modifier(line)
                    all_modifiers.append(modifier)
                    if "(implicit)" in line.lower():
                        implicit.append(modifier)
                    else:
                        explicit.append(modifier)
                index += 1
                continue

            value_lines: list[str] = []
            index += 1
            while index < len(section) and parse_modifier_header(section[index]) is None:
                if not is_non_modifier_metadata_line(section[index]) and not is_flavor_line(section[index]):
                    value_lines.append(section[index])
                index += 1
            raw_text = "\n".join([header.raw_header, *value_lines])
            normalized_text = " ".join(value_lines).strip() or None
            observed_rolls = parse_roll_values(normalized_text or "")
            modifier = ItemModifier(
                raw_text=raw_text,
                normalized_text=normalized_text,
                affix_type=header.affix_type,
                origin=header.origin,
                display_name=header.display_name,
                tier=header.tier,
                observed_rolls=observed_rolls,
                allowed_range=allowed_ranges_from_rolls(observed_rolls),
                tags=header.tags,
                confidence=Confidence(
                    score=Decimal("0.90"),
                    level=ConfidenceLevel.HIGH,
                    reasons=("Advanced copy modifier header parsed.",),
                ),
            )
            all_modifiers.append(modifier)
            if modifier.affix_type == AffixType.IMPLICIT:
                implicit.append(modifier)
            elif modifier.affix_type == AffixType.CORRUPTION_ENHANCEMENT:
                special.append(modifier)
            elif modifier.origin in {ModifierOrigin.UNIQUE, ModifierOrigin.CORRUPTION_ENHANCEMENT}:
                special.append(modifier)
            else:
                explicit.append(modifier)

    if not all_modifiers:
        warnings.append("No modifiers were detected.")
    return tuple(all_modifiers), tuple(implicit), tuple(explicit), tuple(special)


def parse_modifier_header(line: str) -> ModifierHeader | None:
    match = HEADER_RE.match(line)
    if not match:
        return None
    meta = match.group("meta").strip()
    tags = tuple(
        tag.strip() for tag in (match.group("tags") or "").split(",") if tag.strip()
    )
    words = meta.split()
    affix_type = AffixType.UNKNOWN
    origin = ModifierOrigin.NATURAL

    if "Implicit" in words:
        affix_type = AffixType.IMPLICIT
        origin = ModifierOrigin.IMPLICIT
    elif "Prefix" in words:
        affix_type = AffixType.PREFIX
    elif "Suffix" in words:
        affix_type = AffixType.SUFFIX

    if "Crafted" in words:
        origin = ModifierOrigin.CRAFTED
    elif "Desecrated" in words:
        origin = ModifierOrigin.DESECRATED
    elif "Fractured" in words:
        origin = ModifierOrigin.FRACTURED
    elif "Unique" in words:
        origin = ModifierOrigin.UNIQUE
    elif "Corruption" in words and "Enhancement" in words:
        affix_type = AffixType.CORRUPTION_ENHANCEMENT
        origin = ModifierOrigin.CORRUPTION_ENHANCEMENT

    return ModifierHeader(
        affix_type=affix_type,
        origin=origin,
        display_name=match.group("name"),
        tier=match.group("tier"),
        tags=tags,
        raw_header=line,
    )


def parse_roll_values(text: str) -> tuple[RollValue, ...]:
    rolls: list[RollValue] = []
    for match in VALUE_WITH_RANGE_RE.finditer(text):
        observed = _to_decimal(match.group("observed"))
        low = _to_decimal(match.group("low"))
        high = _to_decimal(match.group("high"))
        if low is None and high is None:
            rolls.append(RollValue(value=observed))
        else:
            rolls.append(RollValue(value=observed, min_value=low, max_value=high or low))
    return tuple(rolls)


def allowed_ranges_from_rolls(rolls: tuple[RollValue, ...]) -> tuple[RollValue, ...]:
    return tuple(
        RollValue(label=roll.label, min_value=roll.min_value, max_value=roll.max_value)
        for roll in rolls
        if roll.min_value is not None or roll.max_value is not None
    )


def parse_special_states(lines: list[str]) -> tuple[ItemSpecialState, ...]:
    states: list[ItemSpecialState] = []
    for line in lines:
        normalized = line.strip().lower()
        if normalized == "twice corrupted":
            states.append(ItemSpecialState.TWICE_CORRUPTED)
        elif normalized == "corrupted":
            states.append(ItemSpecialState.CORRUPTED)
        elif normalized == "fractured item":
            states.append(ItemSpecialState.FRACTURED)
    return tuple(states)


def find_unparsed_lines(sections: list[list[str]]) -> tuple[str, ...]:
    unparsed: list[str] = []
    for section_index, section in enumerate(sections):
        if section_index == 0:
            continue
        for line in section:
            if (
                not line
                or line == SECTION_SEPARATOR
                or line.startswith(("Item Class:", "Rarity:", "Requires:", "Item Level:", "Note:", "Grants Skill:"))
                or line.startswith("Can only be equipped")
                or line in {"Corrupted", "Twice Corrupted", "Fractured Item"}
                or HEADER_RE.match(line)
                or looks_like_normal_modifier_line(line)
                or is_flavor_line(line)
            ):
                continue
            unparsed.append(line)
    return tuple(unparsed)


def find_unparsed_sections(sections: list[list[str]]) -> tuple[str, ...]:
    unparsed: list[str] = []
    for section_index, section in enumerate(sections):
        if section_index == 0:
            continue
        meaningful_lines = [line for line in section if line.strip()]
        if meaningful_lines and all(is_unrecognized_line(line) for line in meaningful_lines):
            unparsed.append("\n".join(section))
    return tuple(unparsed)


def is_unrecognized_line(line: str) -> bool:
    return not (
        line.startswith(("Item Class:", "Rarity:", "Requires:", "Item Level:", "Note:", "Grants Skill:"))
        or line.startswith("Can only be equipped")
        or line in {"Corrupted", "Twice Corrupted", "Fractured Item"}
        or HEADER_RE.match(line)
        or looks_like_normal_modifier_line(line)
        or is_flavor_line(line)
    )


def build_normal_modifier(line: str) -> ItemModifier:
    is_implicit = "(implicit)" in line.lower()
    normalized = re.sub(r"\s+\(implicit\)$", "", line, flags=re.IGNORECASE)
    observed_rolls = parse_roll_values(normalized)
    return ItemModifier(
        raw_text=line,
        normalized_text=normalized,
        affix_type=AffixType.IMPLICIT if is_implicit else AffixType.UNKNOWN,
        origin=ModifierOrigin.IMPLICIT if is_implicit else ModifierOrigin.UNKNOWN,
        observed_rolls=observed_rolls,
        allowed_range=allowed_ranges_from_rolls(observed_rolls),
        confidence=Confidence(
            score=Decimal("0.55"),
            level=ConfidenceLevel.MEDIUM,
            reasons=("Normal copy modifier text parsed without metadata.",),
        ),
    )


def looks_like_normal_modifier_line(line: str) -> bool:
    if is_non_modifier_metadata_line(line) or is_flavor_line(line):
        return False
    return bool(re.search(r"\d|Blind Targets|chance|Gain|Adds|\+|increased", line))


def is_non_modifier_metadata_line(line: str) -> bool:
    return (
        line.startswith(("Item Class:", "Rarity:", "Requires:", "Item Level:", "Note:", "Grants Skill:"))
        or line.startswith("Can only be equipped")
        or line in {"Corrupted", "Twice Corrupted", "Fractured Item"}
    )


def is_flavor_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith('"') or stripped.startswith("- ")


def parser_confidence(format_type: ClipboardFormat, warnings: list[str]) -> Confidence:
    if format_type == ClipboardFormat.ADVANCED:
        score = Decimal("0.90")
        level = ConfidenceLevel.HIGH
        reason = "Advanced copy detected."
    elif format_type == ClipboardFormat.NORMAL:
        score = Decimal("0.60")
        level = ConfidenceLevel.MEDIUM
        reason = "Normal copy detected; structured modifier metadata may be missing."
    else:
        score = Decimal("0.30")
        level = ConfidenceLevel.LOW
        reason = "Clipboard format is unknown."
    if warnings:
        score = max(Decimal("0"), score - Decimal("0.10"))
    return Confidence(score=score, level=level, reasons=(reason, *warnings))


def infer_base_type_from_item_name(item_class: str | None, full_name: str) -> str:
    if item_class != "Quivers":
        return full_name
    words = full_name.split()
    for index, word in enumerate(words):
        if word == "Quiver" and index > 0:
            return f"{words[index - 1]} Quiver"
    return full_name


def _to_decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None
