import os
import json
from core.ui import select_effect_file, clear_screen
from core.byml import extract_ptcl_data
from core.parser import iter_all_emitters, read_emitter_volume

def run(config, decompressors):
    game_dump_path = config.get("game_dump_path")
    if not game_dump_path:
        print("[!] 'game_dump_path' not found in config.json")
        input("Press Enter to continue...")
        return

    while True:
        clear_screen()
        effect_choice, full_path = select_effect_file(game_dump_path)
        if not effect_choice:
            break
            
        clear_screen()
        print(f"[*] Parsing {effect_choice}...")
        
        ptcl_data = extract_ptcl_data(full_path, decompressors)
        if not ptcl_data:
            print("[!] Could not extract particle data from this file.\n")
            input("Press Enter to continue...")
            continue
            
        out = []
        for eset_name, eset, emtr_name, emtr, db in iter_all_emitters(ptcl_data):
            vol = read_emitter_volume(ptcl_data, db)
            if vol:
                if hasattr(vol['particle_type'], 'name'):
                    vol['particle_type'] = vol['particle_type'].name
                else:
                    vol['particle_type'] = str(vol['particle_type'])
                out.append({'eset': eset_name, 'emtr': emtr_name, **vol})

        if not out:
            print("[!] No shapes found in this file.\n")
            continue
            
        dir_name = effect_choice.replace('.esetb.byml.zs', '')
        out_dir = os.path.join("out", dir_name)
        os.makedirs(out_dir, exist_ok=True)
        filepath = os.path.join(out_dir, "all_shapes.json")
        
        with open(filepath, 'w') as f:
            json.dump(out, f, indent=2)
        print(f"[*] Successfully dumped to {filepath}\n")
        
        input("Press Enter to continue...")
