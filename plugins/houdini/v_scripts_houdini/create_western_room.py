"""
Western Old Room Scene Builder
================================
Builds a complete western saloon-style room in Houdini.

What gets created:
  Shell (box SOPs - real architectural geometry):
    wr_floor          — wood-plank floor slab
    wr_wall_n/s/e/w   — four perimeter walls
    wr_ceiling        — ceiling slab
    wr_beam_1..4      — wooden ceiling beams spanning wall-to-wall

  Furniture slots (null nodes - coordinate markers for real FBX assets):
    slot_*            — positions computed by the Vibrante semantic layout engine
                        (or canonical western_room fallback layout if the engine
                        is unavailable)

To replace a slot with a real Megascans asset:
  1. Export the FBX from Fab / Unreal Engine Fab panel
  2. In Houdini: inside the slot null, add a geo node → file SOP → point to .fbx
     (or use the Vibrante node graph: hou_mcp_build_shell → hou_mcp_apply_layout)
  3. Set the geo scale to 0.01 (Megascans FBX are in centimeter space)

Run from: Vibrante-Node → Scripts → Create Western Old Room
"""
from src.utils.hou_bridge import get_bridge, is_available

if not is_available():
    print("[Western Room] Houdini command server not reachable.")
    print("  Make sure Vibrante-Node was launched from inside Houdini.")
else:
    bridge = get_bridge()
    PARENT = "/obj"
    ENV    = "western_room"

    # ── Room Dimensions (from EnvironmentShellBlueprintFactory: western_room) ──
    W  = 10.0   # width  X
    H  =  4.0   # height Y
    D  = 12.0   # depth  Z
    WT =  0.3   # wall thickness
    FT =  0.1   # floor thickness
    CT =  0.15  # ceiling thickness
    BW =  0.2   # beam cross-section width  (Z)
    BH =  0.25  # beam cross-section height (Y)

    # ─────────────────────────────────────────────────────────────────────────
    def _mk_box(label, sx, sy, sz, tx=0.0, ty=0.0, tz=0.0):
        """Create /obj/label with a single box SOP inside."""
        gr = bridge.create_node(PARENT, "geo", label)
        gp = gr["path"]
        for ch in bridge.children(gp):
            bridge.delete_node(ch["path"])
        sp = bridge.create_node(gp, "box", "shape")["path"]
        bridge.set_parms(sp, {
            "sizex": round(sx, 4),
            "sizey": round(sy, 4),
            "sizez": round(sz, 4),
        })
        bridge.set_display_flag(sp, True)
        bridge.set_render_flag(sp, True)
        bridge.set_parms(gp, {
            "tx": round(tx, 4),
            "ty": round(ty, 4),
            "tz": round(tz, 4),
        })
        bridge.cook_node(sp)
        return gp

    def _mk_null(label, tx=0.0, ty=0.0, tz=0.0, ry=0.0):
        """Create an /obj-level null node at (tx, ty, tz) facing ry degrees."""
        gr = bridge.create_node(PARENT, "null", label)
        gp = gr["path"]
        bridge.set_parms(gp, {
            "tx": round(tx, 4),
            "ty": round(ty, 4),
            "tz": round(tz, 4),
            "ry": round(ry, 4),
        })
        return gp

    # ─────────────────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  Western Old Room - Building...")
    print("=" * 60)

    # ── Phase 1: Room Shell ───────────────────────────────────────────────────
    print("[Phase 1] Room shell...")

    _mk_box("wr_floor",   W,  FT, D,  0.0, -FT / 2,       0.0)
    _mk_box("wr_wall_n",  W,  H,  WT, 0.0,  H / 2,        -D / 2)
    _mk_box("wr_wall_s",  W,  H,  WT, 0.0,  H / 2,         D / 2)
    _mk_box("wr_wall_e",  WT, H,  D,  W / 2,  H / 2,       0.0)
    _mk_box("wr_wall_w",  WT, H,  D, -W / 2,  H / 2,       0.0)
    _mk_box("wr_ceiling", W,  CT, D,  0.0,  H + CT / 2,    0.0)
    print("  floor, 4 walls, ceiling - done")

    # ── Phase 2: Ceiling Beams ────────────────────────────────────────────────
    print("[Phase 2] Ceiling beams...")
    _beam_span = W - WT * 2   # beam spans between the two side walls
    for _i, _bz in enumerate([-4.0, -1.5, 1.5, 4.0]):
        _mk_box(f"wr_beam_{_i + 1}", _beam_span, BH, BW,
                0.0, H - BH / 2, _bz)
    print("  4 wooden ceiling beams - done")

    # ── Phase 3: Furniture Layout ─────────────────────────────────────────────
    print("[Phase 3] Computing furniture layout...")

    _furniture_assets = [
        # Dining cluster
        {"asset_id": "table_main", "name": "Saloon Table",  "placement_type": "table",      "category": "furniture", "width_m": 1.8,  "height_m": 0.75, "depth_m": 1.0},
        {"asset_id": "chair_n",    "name": "Chair North",   "placement_type": "chair",      "category": "furniture", "width_m": 0.50, "height_m": 0.84, "depth_m": 0.45},
        {"asset_id": "chair_s",    "name": "Chair South",   "placement_type": "chair",      "category": "furniture", "width_m": 0.50, "height_m": 0.84, "depth_m": 0.45},
        {"asset_id": "chair_e",    "name": "Chair East",    "placement_type": "chair",      "category": "furniture", "width_m": 0.50, "height_m": 0.84, "depth_m": 0.45},
        {"asset_id": "chair_w",    "name": "Chair West",    "placement_type": "chair",      "category": "furniture", "width_m": 0.50, "height_m": 0.84, "depth_m": 0.45},
        # Table surface items
        {"asset_id": "lantern",    "name": "Oil Lantern",   "placement_type": "lantern",    "category": "prop",      "width_m": 0.15, "height_m": 0.25, "depth_m": 0.15},
        {"asset_id": "bottle",     "name": "Whiskey Bottle","placement_type": "bottle",     "category": "prop",      "width_m": 0.08, "height_m": 0.30, "depth_m": 0.08},
        # Bar counter + stools
        {"asset_id": "bar",        "name": "Bar Counter",   "placement_type": "bar_counter","category": "furniture", "width_m": 3.5,  "height_m": 1.05, "depth_m": 0.6},
        {"asset_id": "stool_1",    "name": "Bar Stool 1",   "placement_type": "stool",      "category": "furniture", "width_m": 0.35, "height_m": 0.65, "depth_m": 0.35},
        {"asset_id": "stool_2",    "name": "Bar Stool 2",   "placement_type": "stool",      "category": "furniture", "width_m": 0.35, "height_m": 0.65, "depth_m": 0.35},
        {"asset_id": "stool_3",    "name": "Bar Stool 3",   "placement_type": "stool",      "category": "furniture", "width_m": 0.35, "height_m": 0.65, "depth_m": 0.35},
        # Corner props
        {"asset_id": "barrel_sw",  "name": "Barrel SW",     "placement_type": "barrel",     "category": "prop",      "width_m": 0.5,  "height_m": 0.7,  "depth_m": 0.5},
        {"asset_id": "barrel_nw",  "name": "Barrel NW",     "placement_type": "barrel",     "category": "prop",      "width_m": 0.5,  "height_m": 0.7,  "depth_m": 0.5},
        # Wall decor
        {"asset_id": "poster",     "name": "Wanted Poster", "placement_type": "poster",     "category": "prop",      "width_m": 0.30, "height_m": 0.40, "depth_m": 0.02},
    ]

    _slot_transforms = []
    _engine_ok = False
    try:
        from src.runtime.layout.semantic_layout_engine import get_semantic_layout_engine
        from src.runtime.layout_realization.layout_realization_engine import (
            get_layout_realization_engine)
        _layout   = get_semantic_layout_engine().build_layout(_furniture_assets, ENV)
        _realized  = get_layout_realization_engine().realize(
            _layout.to_dict(), room_half_width=W / 2)
        _slot_transforms = list(_realized.transforms or [])
        _engine_ok = bool(_slot_transforms)
        if _engine_ok:
            print(f"  Semantic layout engine: {len(_slot_transforms)} placements")
    except Exception as _exc:
        print(f"  Layout engine unavailable ({_exc}), using canonical layout")

    # ── Phase 4: Furniture Slot Null Nodes ────────────────────────────────────
    print("[Phase 4] Placing furniture slots...")
    _slots_created = 0

    if _engine_ok and _slot_transforms:
        for _xf in _slot_transforms:
            _safe = "".join(
                c if c.isalnum() or c == "_" else "_"
                for c in _xf.asset_id
            )[:24]
            _mk_null(f"slot_{_safe}", _xf.tx, _xf.ty, _xf.tz, _xf.ry)
            print(f"  slot_{_safe:24s}  ({_xf.tx:+5.2f}, {_xf.ty:+5.2f}, {_xf.tz:+5.2f})  ry={_xf.ry:.0f} deg")
            _slots_created += 1
    else:
        # Canonical western_room layout — hardcoded real-world positions.
        # Origin is room centre at floor level.  North = -Z, South = +Z.
        #
        #  (NW corner)              North wall (-Z)             (NE corner)
        #   barrel_nw ·                                             ·
        #                         bar counter
        #                  stool1  stool2  stool3
        #
        #                       (table + 4 chairs)
        #                           table_main
        #              chair_w  ·  lantern/bottle  ·  chair_e
        #                           chair_s
        #
        #   barrel_sw ·                             poster on W wall
        #  (SW corner)              South wall (+Z)             (SE corner)

        _canonical = [
            # Label            tx      ty      tz      ry
            # ── Dining cluster ──────────────────────────
            ("table_main",   0.00,   0.00,  -1.00,    0),
            ("chair_n",      0.00,   0.00,  -1.95,    0),   # faces south
            ("chair_s",      0.00,   0.00,  -0.05,  180),   # faces north
            ("chair_e",      0.95,   0.00,  -1.00,  270),   # faces west
            ("chair_w",     -0.95,   0.00,  -1.00,   90),   # faces east
            # ── Table surface items (ty = table top height) ──────────────────
            ("lantern",      0.30,   0.75,  -1.00,    0),
            ("bottle",      -0.30,   0.75,  -1.00,    0),
            # ── Bar cluster — back (north) wall ─────────────────────────────
            ("bar",          0.00,   0.00,  -4.50,    0),
            ("stool_1",     -1.10,   0.00,  -3.65,    0),
            ("stool_2",      0.00,   0.00,  -3.65,    0),
            ("stool_3",      1.10,   0.00,  -3.65,    0),
            # ── Corner props ─────────────────────────────────────────────────
            ("barrel_sw",   -4.00,   0.00,   4.50,    0),
            ("barrel_nw",   -4.00,   0.00,  -4.50,   45),
            # ── Wall decor — west wall at eye level ──────────────────────────
            ("poster",      -4.72,   1.60,   0.00,   90),
        ]
        for _name, _tx, _ty, _tz, _ry in _canonical:
            _mk_null(f"slot_{_name}", _tx, _ty, _tz, _ry)
            print(f"  slot_{_name:16s}  ({_tx:+5.2f}, {_ty:+5.2f}, {_tz:+5.2f})  ry={_ry} deg")
            _slots_created += 1

    # ── Finalize ──────────────────────────────────────────────────────────────
    try:
        bridge.layout_children(PARENT)
    except Exception:
        pass

    print()
    print("=" * 60)
    print("  Western Old Room - COMPLETE")
    print("=" * 60)
    print(f"  Shell:  floor + 4 walls + ceiling + 4 beams  (10 x 4 x 12 m)")
    print(f"  Slots:  {_slots_created} furniture null nodes")
    print()
    print("  To populate with real Megascans assets:")
    print("  Option A - Fab socket push (instant):")
    print("    Open UE5 -> Fab panel -> My Library -> Export -> Houdini")
    print("    Vibrante receives on port 31337 automatically.")
    print()
    print("  Option B - Manual:")
    print("    fab.com -> My Library -> download FBX ->")
    print("    copy folder to E:/MEGASCAN_LIBRARY/Downloaded/")
    print()
    print("  Then run: Vibrante-Node node graph with hou_mcp_build_shell +")
    print("  hou_mcp_layout_cluster + hou_mcp_apply_layout")
    print("=" * 60)
