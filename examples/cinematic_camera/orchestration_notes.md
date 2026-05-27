# Orchestration Notes — Cinematic Camera

## Orchestration Flow

```
[Planning]  Goal matched 2 workflows: cinematic_push_in, impact_handheld.
            Expanded to 9 ordered stages.
[Execution] Beginning 'cinematic_push_in'. 5 stages queued:
            start_position, anticipation_hold, event_trigger_point,
            push_in_path, slow_motion_end.
[Execution] Stage [start_position]: Camera placed 30m from FX epicenter, 2m elevation.
            Lens 40mm. Hero element in lower-center frame.
[Execution] Stage [anticipation_hold]: 24-frame hold. Micro-jitter 0.02m amplitude.
            Constraint: MINIMUM 12 frames — enforced.
[Execution] Stage [event_trigger_point]: Event frame keyframed. Push begins +2 frames.
[Execution] Stage [push_in_path]: Ease-in over 10 frames, peak push 60 frames.
            Arc path — slight Y-rotation for parallax.
[Execution] Stage [slow_motion_end]: Time scale 0.3x over final 36 frames.
[Execution] Beginning 'impact_handheld'. 4 stages queued:
            pre_event_slight_float, impact_violent_shake,
            decay_oscillation, settle_residual.
[Execution] Stage [pre_event_slight_float]: 0.01m amplitude, 1.2 Hz. Subtle breathing.
[Execution] Stage [impact_violent_shake]: Max displacement at impact frame.
            10 Hz shake, 0.1m amplitude, both translation and rotation.
[Execution] Stage [decay_oscillation]: Exponential decay — half-life 18 frames.
            Frequency drops from 10 Hz to 0.8 Hz over decay.
[Execution] Stage [settle_residual]: 0.03m permanent offset. 0.3 Hz residual tremor.
            Persists 72 frames past peak.
[Review]    Both workflows: 9/9 stages passed. Production-ready.
```

## Key Constraints Enforced

| Constraint | Value | Enforcement |
|---|---|---|
| Anticipation hold | ≥ 12 frames | REQUIRED — hard block |
| Push acceleration | Must ease-in (not constant) | Advisory |
| Push path | Arc, not straight | Advisory — straight pushes look CG |
| Motion blur during slow-mo | REQUIRED | Required |
| Impact shake frequency | 8–20 Hz | Advisory |
| Camera permanent drift | Must NOT return to pre-impact position | Required |
| Residual tremor duration | ≥ 60 frames | Required |
| Both translation AND rotation | On impact shake | Required |

## What a Non-Orchestrated Attempt Produces

Without semantic ordering:
- Constant-speed push (no ease-in) — mechanical, not cinematic
- No anticipation hold — cut directly to push
- Impact shake added as generic noise — not tied to event frame
- Linear decay — physically wrong
- Camera returns exactly to pre-impact position — feels "digital"
- Motion blur off during slow-motion — freezes instead of blurs

The semantic layer enforces the specific ordered stages that produce a
physically convincing, cinema-quality camera performance.
