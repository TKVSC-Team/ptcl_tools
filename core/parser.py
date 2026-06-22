"""
ptcl_tools.py — TOTK .ptcl / VFXB particle binary parser

Decodes the VFXB particle effect binary format used by Tears of the Kingdom
(and shared with BotW/Splatoon/Mario engines via the nn::vfx2 lineage).

This module is the consolidated result of reverse-engineering the format via:
  - The BotW-era ZeldaMods wiki (baseline node-tree structure)
  - dt-12345/ptcl (community TOTK color-editing tool, confirms color/alpha/scale)
  - Ghidra decompilation of TOTK's nn::vfx2 namespace (Splatoon2/SMO debug
    symbols applied to the TOTK binary), tracing: ResolveBinaryData,
    UpdateParams, CalculateRotationMatrix, CalculateEmitSphere/Box/Circle/
    Cylinder, EmitterCalculator::Emit, Emitter::InitializeParticle
  - ptcl.hexpat (ImHex pattern file) — provided the authoritative ResEmitter
    struct layout and ParticleType enum, confirming nearly every offset
    found independently via decompilation, byte-for-byte.

============================================================================
VERIFIED STRUCTURE OVERVIEW
============================================================================

File layout (VFXB binary):
    VFXB header (0x40 bytes)
      -> ESTA (root, siblings = ESET list)
           -> ESET (one effect set, e.g. "Chm_Fire")
                -> EMTR (one emitter within that set, e.g. "Fire_Spark")

Node tree mechanics (BinaryData in hexpat terms):
    Every node has a 32-byte header:
        signature[4], size(u32), subsection_off(i32), next_section_off(i32),
        next_subsection_off(i32), section_off(i32), reserve[8]
    All four offset fields are relative to the node's OWN start address.
    next_section_off / subsection_off of -1 (0xFFFFFFFF) means "none" —
    this is a real sentinel seen in production data, not just a wiki note.
    section_off points to the node's own data block (e.g. ESET name, EMTR
    fields all live at node_start + section_off, then + further offsets).

EMTR data block (= ResEmitter struct, hexpat-confirmed):
    0x10            emitter_name (cstring, up to 0x60 bytes)
    0x80-0xa8       8 animation key counts (color0,alpha0,color1,alpha1,
                    scale,unk_anim0..5) - see ANIM_CHANNELS below
    0x680-0xc00     8 ResParticleAnim blocks (0x80 bytes each), in the same
                    order as the counts above. Each is base: ResAnim8KeyParam
                    (index 0) + key_frames[7] (indices 1-7), each entry
                    (x,y,z,key_frame as f32 - 16 bytes). WARNING: which end
                    of the 7-slot key_frames array holds the `count` real
                    entries is NOT consistent across channels (confirmed
                    front-anchored for alpha0, back-anchored for unk1 -
                    see read_anim_channel docstring). Check both slices.
    0xc10-0xca0     Rotation oscillator parameters (see ROTATION_BLOCK).
                    Confirmed universal (every emitter has these bytes,
                    populated with consistent defaults even when rotation
                    is unused). NOT sourced from an EAxx attribute node -
                    those are a separate, rarely-used system.
    0xd90           ResEmitterVolume struct (see EMITTER_VOLUME) - the
                    emission shape parameters. particle_type byte at this
                    offset indexes nn::vfx2::detail::EmitterCalculator::
                    g_EmitFunctions, a function-pointer jump table.

Emission shape dispatch (confirmed via InitializeParticle's
g_EmitFunctions[*(byte*)(EMTR+0xd90)] call):
    ParticleType enum (hexpat-confirmed) selects which CalculateEmit*
    function runs: Point, Circle*, Sphere*, Cylinder*, Box*, Line*,
    Rectangle, Primitive. size_x/y/z are reused across shapes with
    different meaning per shape (sphere radius scale / box half-width /
    circle XZ-plane radius, with Y as cylinder height).

============================================================================
KNOWN LIMITATIONS / UNVERIFIED AREAS
============================================================================
  - The 0xc10-0xca0 rotation block's exact field semantics are inferred
    from CalculateRotationMatrix's per-axis read pattern + corpus-wide
    constant analysis, NOT from a named source (no hexpat/wiki entry).
    Treat ROTATION_BLOCK field names as best-effort, not ground truth.
  - The EAxx/Fxx/CADP attribute-node system (decoded names available in
    ATTRIBUTE_TAGS below) is confirmed to barely appear in static.ptcl.bin
    (0 of 1991 emitters use EAER/EAES/EAET; the format supports it but
    the shared pool doesn't exercise it). Per-actor .ptcl files may use
    it more - unverified.
  - Texture/shader parameter blocks (texture_shader_flags, texture_params,
    ResTextureSamplerInfo) are present in the hexpat but not cross-checked
    against decompiled accessor code in this investigation.
"""

import struct
from enum import IntEnum
from collections import Counter


# ============================================================================
# Low-level binary readers
# ============================================================================

def u32(data, off):
    return struct.unpack_from('<I', data, off)[0]

def i32(data, off):
    return struct.unpack_from('<i', data, off)[0]

def f32(data, off):
    return struct.unpack_from('<f', data, off)[0]

def read_cstr(data, off, maxlen=128):
    end = data.find(b'\x00', off, off + maxlen)
    if end == -1:
        end = off + maxlen
    return data[off:end].decode('utf-8', errors='replace')


# ============================================================================
# Node tree (ESTA / ESET / EMTR traversal)
# ============================================================================

def read_node_header(data, node_off):
    """32-byte node header. All four offset fields are relative to node_off."""
    return {
        'sig': data[node_off:node_off + 4],
        'size': u32(data, node_off + 4),
        'subsection_off': i32(data, node_off + 8),
        'next_section_off': i32(data, node_off + 0xC),
        'next_subsection_off': i32(data, node_off + 0x10),
        'section_off': i32(data, node_off + 0x14),
        'node_off': node_off,
    }

def walk_tree(data, root_off, max_depth=100000):
    """Walk a sibling chain starting at root_off.

    IMPORTANT: next_section_off == -1 (0xFFFFFFFF) is a real "no more
    siblings" sentinel seen in production data (e.g. many ESETs have
    exactly one EMTR child). Earlier parser versions only checked for 0
    and silently wandered into unrelated bytes after the last real sibling
    - always check both 0 and -1.
    """
    nodes = []
    off = root_off
    depth = 0
    while off is not None and 0 <= off < len(data) and depth < max_depth:
        hdr = read_node_header(data, off)
        nodes.append(hdr)
        if hdr['next_section_off'] in (0, -1):
            break
        off = hdr['node_off'] + hdr['next_section_off']
        depth += 1
    return nodes

def get_data_block(hdr):
    return hdr['node_off'] + hdr['section_off']

def find_esta_root(data):
    return data.find(b'ESTA')

def get_esets(data):
    """Return all ESET node headers under the file's root ESTA."""
    esta_off = find_esta_root(data)
    esta_hdr = read_node_header(data, esta_off)
    eset_root = esta_hdr['node_off'] + esta_hdr['subsection_off']
    return walk_tree(data, eset_root)

def get_eset_name(data, eset_hdr):
    db = get_data_block(eset_hdr)
    return read_cstr(data, db + 0x10)

def get_emitters(data, eset_hdr):
    """Return all EMTR node headers under one ESET."""
    if eset_hdr['subsection_off'] in (0, -1):
        return []
    emtr_root = eset_hdr['node_off'] + eset_hdr['subsection_off']
    return walk_tree(data, emtr_root)

def get_emtr_name(data, emtr_hdr):
    db = get_data_block(emtr_hdr)
    return read_cstr(data, db + 0x10)

def iter_all_emitters(data):
    """Yield (eset_name, eset_hdr, emtr_name, emtr_hdr, data_block) for every
    emitter in the file."""
    for eset in get_esets(data):
        ename = get_eset_name(data, eset)
        for em in get_emitters(data, eset):
            emname = get_emtr_name(data, em)
            yield ename, eset, emname, em, get_data_block(em)


# ============================================================================
# Animation channels (color0, alpha0, color1, alpha1, scale, unk0-5)
# ============================================================================
# 8 identical-format keyframe channels. Verified against dt-12345/ptcl for
# color0/alpha0/color1/alpha1/scale; unk_anim0-5 are confirmed-real (corpus-
# wide independent count fields + real keyframe data found, e.g.
# Trail_Shiranami_R's unk_anim1 is a 6-keyframe fade-out curve) but their
# semantic meaning (rotation? emission rate? gravity?) is NOT identified.

ANIM_CHANNELS = [
    ('color0', 0x80, 0x680),
    ('alpha0', 0x84, 0x700),
    ('color1', 0x88, 0x780),
    ('alpha1', 0x8c, 0x800),
    ('scale',  0x90, 0x880),
    ('unk0',   0x94, 0x900),
    ('unk1',   0x98, 0x980),
    ('unk2',   0x9c, 0xa00),
    ('unk3',   0xa0, 0xa80),
    ('unk4',   0xa4, 0xb00),
    ('unk5',   0xa8, 0xb80),
]
ANIM_BLOCK_SIZE = 0x80   # bytes per channel (8 keyframes x 16 bytes)
KEYFRAME_SIZE = 16        # x, y, z, key_frame (4 x f32)
KEYFRAMES_PER_CHANNEL = 8

def read_anim_channel(data, db, count_off, array_off):
    """Read one animation channel: base + key_frames[7], per the hexpat's
    ResParticleAnim struct (base: ResAnim8KeyParam, key_frames[7]).

    UNRESOLVED: which `count` keyframes (out of the 7-slot key_frames
    array) hold real data is NOT consistent across channels:
      - alpha0 (Fire_Spark, count=4): real curve at key_frames[0:4]
        (the FRONT of the array)
      - unk1 (Trail_Shiranami_R, count=6): real curve at key_frames[1:7]
        i.e. [7-6:7] (the BACK of the array)
    Both anchoring rules are provided below (front_slice, back_slice) so
    no data is hidden, but neither is confirmed universal - inspect both
    when working with a channel you haven't verified by hand, and prefer
    whichever slice doesn't contain large stretches of exact zeros next
    to non-zero values (the real heuristic used throughout this whole
    investigation: a coherent curve has monotonic-ish key_frame values,
    garbage/unused slots are all-zero).
    """
    count = i32(data, db + count_off)
    slots = []
    for i in range(KEYFRAMES_PER_CHANNEL):
        off = db + array_off + i * KEYFRAME_SIZE
        slots.append((f32(data, off), f32(data, off + 4),
                      f32(data, off + 8), f32(data, off + 12)))
    base = slots[0]
    key_frames = slots[1:]
    n = len(key_frames)
    c = min(count, n) if count >= 0 else 0
    return {
        'count': count,
        'base': base,
        'key_frames': key_frames,            # all 7 raw slots, indices 1-7
        'front_slice': key_frames[:c],        # hypothesis A: real data at front
        'back_slice': key_frames[n - c:],     # hypothesis B: real data at back
        'raw_slots': slots,                  # all 8 raw slots, unsliced
    }

def read_all_anim_channels(data, db):
    """Return {channel_name: result_dict} for all 8 channels.
    See read_anim_channel for the structure of each result dict."""
    return {
        name: read_anim_channel(data, db, count_off, array_off)
        for name, count_off, array_off in ANIM_CHANNELS
    }

def read_const_colors(data, db):
    """const_color0 / const_color1 fallback colors (used when no animation
    curve overrides them). Confirmed via AncientBall_Big round-trip."""
    return {
        'const_color0': struct.unpack_from('<4f', data, db + 0xF48),
        'const_color1': struct.unpack_from('<4f', data, db + 0xF58),
    }


# ============================================================================
# Emission shape system (ResEmitterVolume @ EMTR + 0xd90)
# ============================================================================
# Fully confirmed via ptcl.hexpat (independent of decompilation), AND
# cross-validated against the decompiled CalculateEmitSphere/Box/Circle/
# Cylinder functions and InitializeParticle's g_EmitFunctions dispatch.

class ParticleType(IntEnum):
    Point = 0x0
    Circle = 0x1
    CircleEquallyDivided = 0x2
    CircleFile = 0x3
    Sphere = 0x4
    SphereEqually32Divided = 0x5
    SphereEqually64Divided = 0x6
    SphereFile = 0x7
    Cylinder = 0x8
    CylinderFill = 0x9
    Box = 0xA
    BoxFill = 0xB
    Line = 0xC
    LineEquallyDivided = 0xD
    Rectangle = 0xE
    Primitive = 0xF

class Sphere32DivideType(IntEnum):
    Two = 0x0
    Three = 0x1
    Four = 0x2
    Six = 0x3
    Eight = 0x4
    Twelve = 0x5

class Sphere64DivideType(IntEnum):
    Twenty = 0x0
    ThirtyTwo = 0x1

EMITTER_VOLUME_BASE = 0xd90  # relative to EMTR data block

def read_emitter_volume(data, db):
    """Decode the ResEmitterVolume (emission shape) struct.

    Field meanings by shape (from CalculateEmitSphere/Box/Circle/Cylinder):
      size_x/y/z   - Sphere: per-axis radius scale.
                     Box: per-axis half-width (surface-sampled, not filled
                          unless *Fill variant).
                     Circle: size_x=X radius, size_z=Z radius (XZ plane;
                          size_y unused by Circle itself).
                     Cylinder: calls Circle for XZ disc, then separately
                          reads size_y as half-height along Y.
      cone_half_angle (Sphere only) - emission restricted to a cone;
                     pi = full sphere, pi/2 = hemisphere, etc. Commonly
                     exact fractions of pi in real data.
      base_angle / angle_jitter (Circle/Cylinder) - starting angle around
                     the circle, plus random jitter added to it.
      angle_override_flag (Circle/Cylinder) - when set, ignores base_angle
                     and doubles the input phase parameter instead.
      orientation_preset (Sphere only) - selects a baked quaternion preset
                     for rotating the whole emission cone; observed value
                     '2' in ~98% of real emitters (likely "no rotation").
      sphere_32_divide_type / sphere_64_divide_type (Sphere only) - point-
                     table density tier (how many precomputed directions).
      emission_type - order mode for shape variants with discrete point
                     tables (e.g. SphereEqually32Divided): 0 = sequential
                     wrap, 1 = random (uses the emitter's own LCG PRNG),
                     2 = round-robin divided across multiple emit calls.
      length - used by Line/LineEquallyDivided for line length; not used
                     by Sphere/Box/Circle/Cylinder.
    """
    base = db + EMITTER_VOLUME_BASE
    if base + 0x48 > len(data):
        return None

    def safe_enum(enum_cls, raw):
        try:
            return enum_cls(raw)
        except ValueError:
            return f"Unknown(0x{raw:02x})"

    return {
        'particle_type': safe_enum(ParticleType, data[base + 0x00]),
        'angle_override_flag': data[base + 0x01],
        'sphere_32_divide_type': safe_enum(Sphere32DivideType, data[base + 0x03]),
        'sphere_64_divide_type': safe_enum(Sphere64DivideType, data[base + 0x04]),
        'orientation_preset': data[base + 0x05],
        'angle_jitter': f32(data, base + 0x08),
        'cone_half_angle': f32(data, base + 0x0c),
        'base_angle': f32(data, base + 0x10),
        'length': f32(data, base + 0x20),
        'size_x': f32(data, base + 0x24),
        'size_y': f32(data, base + 0x28),
        'size_z': f32(data, base + 0x2c),
        'emission_type': i32(data, base + 0x3c),
    }


# ============================================================================
# Rotation oscillator block (EMTR + 0xc10..0xca0)
# ============================================================================
# UNVERIFIED against a named source - see module docstring "KNOWN
# LIMITATIONS". Field names below are best-effort inference from:
#   1. CalculateRotationMatrix's per-axis read pattern (X/Y/Z params spaced
#      4 bytes apart; flags spaced 1 byte apart in a separate runtime
#      struct we could not map back to file offsets)
#   2. Corpus-wide scan of all 1991 emitters in static.ptcl.bin: most
#      offsets vary meaningfully per-emitter, a few are universal
#      constants (1.0, 1/6, 60.0) present in every single emitter
#      regardless of whether rotation is visually used - consistent with
#      baked default parameters for a per-axis oscillator system that's
#      usually left at defaults.
# This memory is reused as unk_anim5's raw keyframe array when rotation is
# NOT active for a given emitter (the two interpretations occupy the same
# bytes - confirmed by checking that real unk_anim5 keyframe data and the
# "rotation defaults" pattern never both appear with non-default values in
# the same sample emitters checked).

ROTATION_BLOCK_BASE = 0xc10

def read_rotation_block(data, db):
    """Best-effort decode of the per-axis rotation/spin oscillator block.
    Field names are inferred, not confirmed - see module docstring."""
    base = db + ROTATION_BLOCK_BASE
    if base + 0x90 > len(data):
        return None

    def axis_triplet(rel_off):
        return tuple(f32(data, base + rel_off + i * 4) for i in range(3))

    return {
        'phase_xyz': axis_triplet(0x00),        # 0xc10/c14/c18 - matches confirmed pi/2 find
        'amplitude_xyz': axis_triplet(0x10),    # 0xc20/c24/c28
        'frequency_xyz': axis_triplet(0x20),    # 0xc30/c34/c38
        'damping': f32(data, base + 0x2c),      # 0xc3c - nonzero in 100% of emitters
        'jitter_xyz': axis_triplet(0x30),       # 0xc40/c44/c48
        'param_a': f32(data, base + 0x40),      # 0xc50 - present in ~74% of emitters
        'param_b': f32(data, base + 0x44),      # 0xc54 - present in ~69% of emitters
        'divisor_xyz': axis_triplet(0x50),      # 0xc60/c64/c68 - usually 1/6, sometimes 1/36
        'rate_xyz': axis_triplet(0x60),         # 0xc70/c74/c78 - usually 60.0, sometimes 120/25
        'flag_a': f32(data, base + 0x84),       # 0xc94 - boolean-like, rare (3/1991)
        'flag_b': f32(data, base + 0x88),       # 0xc98 - boolean-like, rare (19/1991)
    }


# ============================================================================
# Attribute-node tag table (decoded from ResolveBinaryData's magic dispatch)
# ============================================================================
# Confirmed to barely appear in static.ptcl.bin (0/1991 emitters use any of
# the EA-prefixed tags in this file). Provided for completeness / for
# checking per-actor .ptcl files, which may use this system more.

ATTRIBUTE_TAGS = {
    'EAA0': 'Emitter Animation Alpha0 (?)',
    'EAA1': 'Emitter Animation Alpha1 (?)',
    'EAC0': 'Emitter Animation Color0 (?)',
    'EAC1': 'Emitter Animation Color1 (?)',
    'EADV': 'Emitter Animation Divide (?)',
    'EAER': 'Emitter Animation Ease Rotation (?) - shares flag w/ EAES, EAET',
    'EAES': 'Emitter Animation Ease Scale (?) - shares flag w/ EAER, EAET',
    'EAET': 'Emitter Animation Ease Translate (?) - shares flag w/ EAER, EAES',
    'EAGV': 'Emitter Animation Gravity/Gyration Variance (?)',
    'EAOV': 'Emitter Animation Orientation Variance (?)',
    'EAPL': 'Emitter Animation Plane (?)',
    'EASL': 'Emitter Animation Scale-Sub-L (?)',
    'EASS': 'Emitter Animation Scale-Sub-S (?)',
    'EATR': 'Emitter Animation Translate/Rotate (?)',
    'EP01': 'Emitter/Particle child-type variant 1 of 4',
    'EP02': 'Emitter/Particle child-type variant 2 of 4',
    'EP03': 'Emitter/Particle child-type variant 3 of 4',
    'EP04': 'Emitter/Particle child-type variant 4 of 4',
    'CADP': 'Confirmed (wiki): emitter casts light',
    'CSDP': 'Has associated size field (shadow/sprite-divide params?)',
    'CUDP': 'Unknown purpose, confirmed real attribute class',
    'FCOL': 'Field: Color modifier (?)',
    'FCOV': 'Field: Color-Override (?)',
    'FCLN': 'Field: Collision (?)',
    'FCSF': 'Field: Curve Scale Factor (?)',
    'FGWD': 'Field: Gravity/Wind (?)',
    'FMAG': 'Field: Magnify/Magnet (?)',
    'FPAD': 'Field: Pad (?)',
    'FRND': 'Field: Random',
    'FRN1': 'Field: Random (variant 1)',
    'FSPN': 'Field: Spin',
}


# ============================================================================
# High-level convenience: full emitter dump
# ============================================================================

def describe_emitter(data, db):
    """Return a complete dict describing one EMTR's name, shape, animation
    channels, and rotation block."""
    return {
        'name': read_cstr(data, db + 0x10),
        'volume': read_emitter_volume(data, db),
        'anim_channels': read_all_anim_channels(data, db),
        'const_colors': read_const_colors(data, db),
        'rotation': read_rotation_block(data, db),
    }


# ============================================================================
# CLI / self-test
# ============================================================================

if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/static.ptcl.bin'
    with open(path, 'rb') as f:
        data = f.read()

    print(f"File: {path}")
    print(f"Size: {len(data):,} bytes\n")

    esets = get_esets(data)
    total_emitters = sum(len(get_emitters(data, e)) for e in esets)
    print(f"ESETs: {len(esets)}")
    print(f"Total emitters: {total_emitters}\n")

    type_counts = Counter()
    for ename, eset, emname, em, db in iter_all_emitters(data):
        vol = read_emitter_volume(data, db)
        if vol:
            pt = vol['particle_type']
            type_counts[pt.name if isinstance(pt, ParticleType) else str(pt)] += 1

    print("ParticleType distribution:")
    for ptype, count in type_counts.most_common():
        print(f"  {ptype:30s} {count}")

    # Example: full dump of one named emitter, if present
    target = 'Fire_Spark'
    for ename, eset, emname, em, db in iter_all_emitters(data):
        if emname == target:
            print(f"\nFull dump of '{ename}' / '{emname}':")
            info = describe_emitter(data, db)
            print("  Shape:", info['volume'])
            print("  Const colors:", info['const_colors'])
            for chan, result in info['anim_channels'].items():
                if result['count'] > 0:
                    print(f"  Anim[{chan}] count={result['count']}")
                    print(f"    front_slice={result['front_slice']}")
                    print(f"    back_slice ={result['back_slice']}")
            break
