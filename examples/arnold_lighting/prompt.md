# Arnold Cinematic Lighting — Example Prompt

## Prompt

```
Set up cinematic explosion lighting in Arnold — HDRI sky dome, fire-driven key light
with warm orange fill, rim light for edge definition, volumetric atmosphere, and
correct exposure balance for a daytime explosion scene.
```

## What This Prompt Triggers

Keyword matches:
- "arnold lighting" / "cinematic lighting" → `arnold_cinematic_lighting`
- "volumetric" → `volumetric_contrast_lighting`

Two-workflow match (confidence 0.90):
1. `arnold_cinematic_lighting` — 7-stage cinematic rig
2. `volumetric_contrast_lighting` — 5-stage volumetric enhancement

## Expected Stage Sequence

```
sky_hdri_or_skydome → key_light_placement → rim_light_placement → fill_light
→ volumetric_atmosphere → shadow_control → exposure_balance
→ volume_skydome → directional_key → volumetric_shadows → godrays_setup
→ secondary_bounce
```

## Artistic Intent

- Sky dome establishes ambient base only — not the dominant source.
- Fire emission drives the key light — warm orange (2800–3200K).
- Rim light separates subjects from the smoke background.
- Volumetric shadows from smoke column create depth.
- God rays (if applicable) add cinematic atmosphere.
- Final exposure balance ensures fire is not blown out.

## Artistic Constraints

| Constraint | Value | Level |
|---|---|---|
| Key light direction | From explosion source | Required |
| Key:fill contrast ratio | Minimum 4:1 | Advisory |
| Sky dome intensity | Max 0.5 when fire present | Required |
| Volumetric shadows | Active | Required |
| Exposure | Fire not clipped/blown | Required |
