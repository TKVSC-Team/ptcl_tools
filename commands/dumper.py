import json
from core.parser import iter_all_emitters, read_emitter_volume

def run(ptcl_bin):
    try:
        with open(ptcl_bin, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print(f"Error: Could not read {ptcl_bin}")
        return

    out = []
    for eset_name, eset, emtr_name, emtr, db in iter_all_emitters(data):
        vol = read_emitter_volume(data, db)
        if vol:
            if hasattr(vol['particle_type'], 'name'):
                vol['particle_type'] = vol['particle_type'].name
            else:
                vol['particle_type'] = str(vol['particle_type'])
            out.append({'eset': eset_name, 'emtr': emtr_name, **vol})

    with open('all_shapes.json', 'w') as f:
        json.dump(out, f, indent=2)
    print(f"Successfully dumped to all_shapes.json")
