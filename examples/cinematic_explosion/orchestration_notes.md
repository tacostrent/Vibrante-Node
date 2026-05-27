# Orchestration Notes — Cinematic Explosion Scene

## Orchestration Flow

```
[Planning]  Goal 'cinematic explosion scene' matched composite workflow → 6 workflows, 34 stages.
[Execution] Beginning 'cinematic_explosion' execution. 9 ordered stages queued:
            terrain_prep, pyro_source, fireball_core, smoke_evolution, pressure_wave,
            secondary_debris, lighting_setup, camera_framing, render_setup.
[Execution] Stage [terrain_prep]: Setting up ground plane geometry for pressure interaction.
[Execution] Stage [pyro_source]: Configuring pyro emission source — burst velocity + density.
[Execution] Stage [fireball_core]: Building temperature/heat field with high-contrast gradient.
[Execution] Stage [smoke_evolution]: Adding turbulence layers for breakup variation.
[Execution] Stage [pressure_wave]: Pressure wave timing — near-sonic front within 12 frames.
[Execution] Stage [secondary_debris]: Voronoi fracture + RBD with multi-scale debris.
[Execution] Stage [lighting_setup]: Arnold cinematic rig — fire emission as key light.
[Execution] Stage [camera_framing]: Cinematic push-in with 24-frame anticipation hold.
[Execution] Stage [render_setup]: Arnold ROP, 8 AA samples, adaptive sampling on.
[Review]    Workflow 'cinematic_explosion' — 9/9 stages passed. Production-ready.
```

## Key Artistic Constraints Enforced

### Pyro

| Constraint | Value | Enforcement |
|---|---|---|
| Minimum fireball resolution | 128³ | Required — blocked if lower |
| Temperature gradient | High contrast | Advisory |
| Turbulence on smoke | Must not be uniform | Required |
| Pressure wave timing | < 12 frames from trigger | Advisory |

### Lighting

| Constraint | Value | Enforcement |
|---|---|---|
| Fire as dominant light source | Required | Required |
| HDRI intensity when pyro present | Max 0.5 | Advisory |
| Volumetric shadows from smoke | Required | Required |

### Camera

| Constraint | Value | Enforcement |
|---|---|---|
| Anticipation hold | Minimum 12 frames | Required |
| Push velocity | Must accelerate (ease-in) | Advisory |
| Motion blur during slow-mo | Required | Required |

### Render

| Constraint | Value | Enforcement |
|---|---|---|
| Output format | EXR only | Required |
| AA samples (final) | Minimum 8 | Required |
| Emission AOV | Required for pyro | Required |
| Depth pass | World units | Required |
| Cryptomatte | Required | Required |

## Common Mistakes This Orchestration Prevents

1. **Executing render_setup before lighting_setup** — the stage dependency graph enforces order.
2. **Missing emission AOV** — artistic_constraints.json marks this as `required` for pyro scenes.
3. **No anticipation hold** — constraint requires minimum 12 frames before the event trigger.
4. **Uniform smoke column** — review engine flags "smoke breakup lacks variation" specifically.
5. **Non-world-unit depth pass** — review engine catches "Depth pass is not in world units".

## What a Non-Orchestrated Attempt Produces

Without the semantic layer, a single-shot "create cinematic explosion" request results in:
- Random node order — render ROP created before pyro source exists
- No camera setup — default perspective view used for render
- Missing AOVs — only beauty pass output
- No debris interaction — explosion floats above the ground
- Lighting flat — single distant light, no fire contribution

The semantic layer converts the chaos into the ordered 34-stage sequence above.
