# Other instructions (chef hard constraints)

## Goal

Add an optional **Other instructions** free-text field under Likes/Dislikes so users can give the chef open-ended planning rules (e.g. “oven/microwave only, no real cooking”, “3 curry dinners”). The chef must treat non-empty instructions as hard requirements, overridden only by allergies/safety.

## Decision

**Approach A — prompt-only hard constraint.** Persist the field end-to-end and inject strong “must follow” language into the meal-plan LLM prompt. Ask the chef to briefly acknowledge applied instructions in `chef_notes`. No second compliance pass; no structured parsing.

## Platforms

- **Web:** textarea under Likes/Dislikes in Preferences (`DiscoveryStep`), matching existing form styling.
- **Mobile:** same field, and also add Likes/Dislikes (currently missing) so Preferences parity with web.

## Data model

| Layer | Field | Type | Notes |
|-------|-------|------|-------|
| `DiscoveryAnswers` (TS + API) | `other_instructions` | `string` | Default `""` |
| `UserProfile` | `other_instructions` | `str` | Default `""`; keep as prose, do **not** comma-split |
| Saved profiles JSON | `other_instructions` | string | Backward compatible when missing |

Flow: Preferences UI → `POST /api/profile` → `create_profile_from_answers` → session `UserProfile` → `MealPlanner._build_prompt` → LLM.

Changing the field invalidates a cached meal plan via existing preferences fingerprint.

## Prompt behavior

When building constraints in `_build_prompt`:

- Include `other_instructions` (string; may be empty).
- Include an `other_instructions_rules` note: if non-empty, **hard requirement** — follow for the meal plan; only allergies / food-safety may override; briefly note in `chef_notes` what was applied.
- Likes/dislikes remain soft preference lists; cooking-method / plan-shape constraints belong in Other instructions.

## UI

- Label: **Other instructions**
- Control: multiline textarea (web) / multiline `TextInput` (mobile)
- Placeholder example: oven & microwave ready meals, no stovetop cooking; or “3 dinners curry-based”
- Placement: directly under the Likes/Dislikes row in Diet & safety / Diet & budget

## Out of scope

- Post-generation compliance check / auto-regenerate
- Parsing free text into structured constraint objects
- Changing how likes/dislikes are enforced in code
