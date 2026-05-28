# Orchestration Notes — Dust Wave

## Orchestration Flow

```
[Planning]  Goal 'rolling dust wave from pressure shockwave' matched 1 workflow via keyword: dust_wave.
            Expanded to 5 ordered stages.
[Execution] Beginning 'dust_wave' execution. 5 stages queued:
            ground_interaction_setup, dust_source, wave_propagation,
            thin_layer_advection, dissipation_control.
[Execution] Stage [ground_interaction_setup]: Configuring terrain collision for dust emission.
[Execution] Stage [dust_source]: Setting dust density 0.2 — semi-transparent thin veil.
[Execution] Stage [wave_propagation]: Pressure front velocity 25 m/s — driving dust rollout.
[Execution] Stage [thin_layer_advection]: Advecting dust along ground surface — not floating.
[Execution] Stage [dissipation_control]: Gradual falloff over 60 frames.
[Review]    Workflow 'dust_wave' — 5/5 stages passed. Production-ready.
```

## Key Technical Notes

- Ground interaction geometry must exist before `dust_source` can emit correctly.
- `thin_layer_advection` requires `wave_propagation` to define the velocity field.
- Dissipation should extend at least 60 frames past the wave front — abrupt cutoff
  breaks the physical believability.

## Good vs Bad Patterns

### GOOD: Ordered execution
```
ground_interaction_setup → dust_source → wave_propagation → thin_layer_advection → dissipation_control
```

### BAD: Out-of-order (no ground interaction setup)
```
dust_source → wave_propagation → thin_layer_advection → dissipation_control
```
Result: Dust floats without terrain interaction — looks like smoke, not dust.

### BAD: Missing dissipation stage
```
ground_interaction_setup → dust_source → wave_propagation → thin_layer_advection
```
Result: Dust pops off at the end of the sim range — abrupt, unnatural cutoff.
