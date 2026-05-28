# Dust Wave — Example Prompt

## Prompt

```
Create a rolling dust wave from a pressure shockwave passing across a terrain.
The dust should hug the ground, be semi-transparent, and dissipate naturally
as it rolls outward.
```

## What This Prompt Triggers

The GoalDecomposer matches keywords:
- "dust wave" → `dust_wave` workflow
- "pressure" → potentially `cinematic_explosion` pressure_wave stage

Single workflow match: `dust_wave` — 5 ordered stages.

## Expected Stage Sequence

```
ground_interaction_setup → dust_source → wave_propagation
→ thin_layer_advection → dissipation_control
```

## Artistic Intent

- Dust rolls along the ground plane — not floating up.
- Semi-transparent thin veil, not opaque wall.
- Driven by pressure front — wave speed dictates dust rollout.
- Dissipates gradually; doesn't cut off abruptly.

## Artistic Constraints

| Constraint | Value |
|---|---|
| Dust opacity | Semi-transparent (density 0.1–0.4) |
| Ground interaction | Dust hugs terrain — not floating |
| Wave propagation speed | 20–50 m/s (pressure-driven) |
| Dissipation | Gradual — not abrupt cutoff |
