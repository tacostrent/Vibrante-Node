# Orchestration Notes — Arnold Cinematic Lighting

## Orchestration Flow

```
[Planning]  Goal matched 2 workflows via keyword: arnold_cinematic_lighting,
            volumetric_contrast_lighting. Expanded to 12 ordered stages.
[Execution] Beginning 'arnold_cinematic_lighting' execution. 7 stages queued:
            sky_hdri_or_skydome, key_light_placement, rim_light_placement,
            fill_light, volumetric_atmosphere, shadow_control, exposure_balance.
[Execution] Stage [sky_hdri_or_skydome]: HDRI dome placed. Intensity set to 0.4.
[Execution] Stage [key_light_placement]: Key light from explosion source direction.
            Color temperature 2900K (warm orange fire).
[Execution] Stage [rim_light_placement]: Rim light defines edge separation against smoke.
[Execution] Stage [fill_light]: Fill at 1/5 key intensity — 5:1 contrast ratio.
[Execution] Stage [volumetric_atmosphere]: Volumetric scatter active for depth.
[Execution] Stage [shadow_control]: Volumetric shadows from smoke column enabled.
[Execution] Stage [exposure_balance]: Exposure balanced — fire bright but not clipped.
[Review]    Stage [volumetric_atmosphere] ⚠ — Volumetric depth could be improved.
            Add atmospheric haze behind the smoke column for better depth separation.
[Execution] Beginning 'volumetric_contrast_lighting'. 5 stages queued.
[Execution] Stage [volume_skydome] → [directional_key] → [volumetric_shadows]
            → [godrays_setup] → [secondary_bounce].
[Review]    Workflow 'volumetric_contrast_lighting' — 5/5 stages passed.
```

## Why Lighting Must Come Before Render Setup

The `arnold_cinematic_lighting` workflow must complete before `arnold_render_ready`:
- Render sampling is tuned for the scene's lighting ratio
- Volume step size is affected by volumetric fog density
- AOV setup needs to know whether emission and volume scatter passes are active

The `GoalDecomposer` enforces this by placing lighting workflows before render
workflows in the composite execution order.

## Common Lighting Mistakes

| Mistake | Consequence | Constraint Response |
|---|---|---|
| Sky dome at full intensity | Washes out explosion | Required: reduce to ≤ 0.5 |
| Key light from wrong direction | Light contradicts explosion | Required: match explosion axis |
| No volumetric shadows | Smoke column floats with no depth | Required: enable volume shadows |
| Flat 1:1 contrast ratio | Feels like day exterior, not explosion | Advisory: 4:1 minimum ratio |
| Exposure blowing out fire | Fire loses detail in comp | Required: check highlight clamp |
