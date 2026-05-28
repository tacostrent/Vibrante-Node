# Cinematic Camera — Example Prompt

## Prompt

```
Create a cinematic camera move — start held back watching the target area,
then push in toward the explosion as it detonates. The camera should shake
violently on impact and decay to a residual tremor.
```

## What This Prompt Triggers

Keyword matches:
- "push in" / "camera push" → `cinematic_push_in`
- "camera shake" / "impact shake" → `impact_handheld`

Two-workflow match (confidence 0.90):
1. `cinematic_push_in` — 5-stage push-in move
2. `impact_handheld` — 4-stage shake decay sequence

## Expected Stage Sequence

```
start_position → anticipation_hold → event_trigger_point
→ push_in_path → slow_motion_end
→ pre_event_slight_float → impact_violent_shake
→ decay_oscillation → settle_residual
```

## Artistic Intent

- Camera breathes slightly before the event (handheld breathing).
- Minimum 24-frame hold builds tension.
- Push begins at or 2 frames after the event trigger.
- Acceleration during push — not constant speed.
- At impact: violent high-frequency shake (8–20 Hz, 0.05–0.15m amplitude).
- Shake decays exponentially — not linear.
- Camera does NOT return to exact pre-impact position (permanent drift).

## Timing Reference

| Phase | Frames | Description |
|---|---|---|
| Pre-event float | 1–48 | Subtle handheld breathing |
| Anticipation hold | 24 min | Static with micro-jitter |
| Push (ease-in) | 8–12 | Velocity builds from 0 |
| Push (peak velocity) | 24–96 | Toward epicenter |
| Impact shake | 4–12 | Maximum displacement |
| Shake decay | 48–96 | Exponential frequency + amplitude drop |
| Residual tremor | 60+ | Low-freq drift, permanent offset |
