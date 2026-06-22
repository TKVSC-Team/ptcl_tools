import os
from core.byml import extract_ptcl_data
from core.parser import iter_all_emitters, describe_emitter

def run(effect_file, target, decompressors):
    print(f"[*] Processing: {os.path.basename(effect_file)}")
    
    ptcl_raw_bytes = extract_ptcl_data(effect_file, decompressors)
    if not ptcl_raw_bytes:
        print("  [!] Could not extract particle data from this file.")
        return
        
    print(f"  -> Found {len(ptcl_raw_bytes)} bytes of particle data. Analyzing...\n")

    found = False
    for ename, eset, emname, em, db in iter_all_emitters(ptcl_raw_bytes):
        if emname == target:
            print(f"# Full dump of '{ename}' / '{emname}'")
            info = describe_emitter(ptcl_raw_bytes, db)
            
            if info.get('volume'):
                import json
                print("  Shape:")
                formatted_vol = json.dumps(info['volume'], default=str, indent=4)
                for line in formatted_vol.split('\n'):
                    print(f"    {line}")
            else:
                print("  Shape: None")
                
            print(f"  Const colors: {info.get('const_colors')}")
            for chan, result in info['anim_channels'].items():
                if result['count'] > 0:
                    print(f"  Anim[{chan}] count={result['count']}")
                    print(f"    front_slice={result['front_slice']}")
                    print(f"    back_slice ={result['back_slice']}")
            found = True
            break
            
    if not found:
        print(f"  [!] Emitter '{target}' not found in this file.")
