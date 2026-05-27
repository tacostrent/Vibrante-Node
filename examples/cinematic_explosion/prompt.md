# Cinematic Explosion Scene — Example Prompt

## Prompt

```
Create a cinematic hero explosion scene with rising smoke, debris scatter, a pressure
wave interacting with the ground, volumetric lighting, a cinematic push-in camera move,
and a full Arnold render setup with all production AOVs.
```

## What This Prompt Triggers

The GoalDecomposer matches this against the **"cinematic explosion scene"** composite goal,
which expands to 6 ordered workflows:

1. `cinematic_explosion` — 9-stage pyro FX sequence
2. `dust_wave` — ground pressure wave with dust displacement
3. `debris_field` — secondary debris scatter with RBD
4. `arnold_cinematic_lighting` — 7-stage cinematic lighting rig
5. `cinematic_push_in` — 5-stage camera move with anticipation hold
6. `arnold_render_ready` — full production render setup with AOVs

## Expected Stage Sequence (ordered)

```
terrain_prep → pyro_source → fireball_core → smoke_evolution → pressure_wave
→ secondary_debris → lighting_setup → camera_framing → render_setup
→ ground_interaction_setup → dust_source → wave_propagation → thin_layer_advection
→ dissipation_control
→ debris_source_geo → voronoi_fracture → initial_velocity_seed → rigid_body_sim
→ scatter_distribution → dust_tail
→ sky_hdri_or_skydome → key_light_placement → rim_light_placement → fill_light
→ volumetric_atmosphere → shadow_control → exposure_balance
→ start_position → anticipation_hold → event_trigger_point → push_in_path
→ slow_motion_end
→ arnold_rop_setup → sampling_configuration → aov_setup → motion_blur_config
→ volume_step_size → output_driver → farm_submission_prep
```

## Artistic Intent

- Explosion feels violent, immediate, and physically grounded.
- Ground interaction is visible — dust, pebbles, disturbance.
- Smoke column has visible breakup variation, not a uniform pillar.
- Camera reveals the blast with anticipation before pushing in.
- Lighting is dominated by fire emission; HDRI is secondary.
- All passes (emission, cryptomatte, depth, motion vectors) are output-ready.
