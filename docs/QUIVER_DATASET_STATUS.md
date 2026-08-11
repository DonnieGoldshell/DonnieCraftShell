# Quiver Dataset Status

This report describes the offline Task 5C Quiver modifier dataset. It is source-backed research data, not a complete or official Path of Exile 2 catalogue.

## Dataset

- Dataset version: `poe2db-unknown-version-2026-08-11-task5c-quiver`
- Source capture date: `2026-08-11`
- Raw modifier records: 17
- Normalized modifier families: 12
- Normalized tier definitions: 17
- Verification status: `NEEDS_VERIFICATION`
- Source policy: PoE2DB is community data; licensing and bulk normalized storage remain `NEEDS REVIEW / NEEDS VERIFICATION`.

## Captured Records

Captured source-backed records:

`Shocking`, `Annealed`, `Frozen`, `of the Falcon`, `of Valour`, `of Infusion`, `Glaciated`, `Polished`, `Rapid`, `of the Archer`, `of Mastery`, `of the Panther`, `Entombing`, `Nimble`, `Lacerating`, `of Destruction`, `of Calamity`.

External PoE2DB hover/cache keys are stored as `source_record_key`; they are not DonnieCraftShell canonical IDs.

## Coverage

| Fixture | Total | Resolved | Ambiguous | Unresolved | Coverage | Explicit Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `quiver_1_rare_standard_advanced.txt` | 7 | 6 | 0 | 1 | 85.7% | 100.0% |
| `quiver_2_rare_trade_note_advanced.txt` | 7 | 6 | 0 | 1 | 85.7% | 100.0% |
| `quiver_3_normal_advanced.txt` | 1 | 0 | 0 | 1 | 0.0% | 0.0% |
| `quiver_4_magic_advanced.txt` | 3 | 2 | 0 | 1 | 66.7% | 100.0% |
| `quiver_5_rare_corrupted_advanced.txt` | 7 | 1 | 0 | 6 | 14.3% | 16.7% |
| `quiver_6_crafted_desecrated_advanced.txt` | 7 | 6 | 0 | 1 | 85.7% | 100.0% |
| `quiver_7_twice_corrupted_advanced.txt` | 9 | 1 | 0 | 8 | 11.1% | 16.7% |
| `quiver_8_unique_advanced.txt` | 6 | 0 | 0 | 6 | 0.0% | 0.0% |

Rare Advanced explicit affix coverage for Quivers 1, 2, 5, 6, and 7 is `20/30` = `66.7%`.

## Unresolved Fixture Modifiers

- Quiver 1: implicit poison chance.
- Quiver 2: implicit Broadhead physical damage.
- Quiver 3: implicit stun buildup.
- Quiver 4: implicit pierce chance.
- Quiver 5: implicit critical chance, `Consistent`, `Humming`, `of the Fox`, `of Victory`, `of Disaster`.
- Quiver 6: implicit attack speed.
- Quiver 7: corruption enhancements, implicit critical chance, `Sparking`, `Impaling`, `Honed`, `of Disaster`, `of Splintering`.
- Quiver 8: unique and implicit modifiers.

These remain unresolved because no source-backed raw records have been captured for this dataset. Do not add placeholder records to improve coverage.

## Special Origins

Crafted and Desecrated are clipboard origin states. In Task 5C, `Crafted Prefix "Lacerating"` and `Desecrated Suffix "of the Archer"` can resolve to canonical modifier tier definitions because their displayed name, affix type, tier, range, and Quiver applicability match source-backed records. The resolver does not erase or reinterpret the original `origin`.

## Adding Records Safely

1. Capture only factual structured fields from a source page or hover/cache record.
2. Preserve `source_uri`, `source_record_key`, `retrieved_at`, display name, family, generation type, tier, stat min/max, spawn tags, and craft tags where exposed.
3. Confirm tier semantics match Advanced Clipboard tier labels.
4. Add the record to `data/raw/.../raw_modifiers.json`.
5. Regenerate normalized data with:

```bash
python -m packages.shared.donniecraftshell_contracts.normalize_game_data data/raw/poe2db/quiver-modifiers-research-2026-08-11/raw_modifiers.json --out-root data/normalized
```

6. Run the full test suite and coverage helper.
