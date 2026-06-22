import os
import json
import questionary
from prompt_toolkit.styles import Style

import ptcl_tools
import main as totk_main
import oead

def load_effect_files(effect_dir):
    files = []
    if not os.path.exists(effect_dir):
        return []
    for f in os.listdir(effect_dir):
        if f.endswith('.esetb.byml.zs'):
            files.append(f)
    return sorted(files)

def get_parsed_data(effect_file_path, decompressors):
    try:
        byml_bytes = totk_main.decompress_totk_file(effect_file_path, decompressors)
        byml_data = oead.byml.from_binary(byml_bytes)
        ptcl_raw_bytes = totk_main.find_ptcl_bytes_in_byml(byml_data)
        
        if not ptcl_raw_bytes:
            return None
            
        if hasattr(ptcl_raw_bytes, 'data'): 
            ptcl_raw_bytes = bytes(ptcl_raw_bytes.data) 
        else:
            ptcl_raw_bytes = bytes(ptcl_raw_bytes)
            
        return ptcl_raw_bytes
    except Exception as e:
        print(f"  [!] Error parsing file: {e}")
        return None

def format_emitter_info(eset_name, emtr_name, info):
    out_lines = []
    out_lines.append(f"--- Full dump of '{eset_name}' / '{emtr_name}' ---")
    
    # Format volume gracefully
    if info.get('volume'):
        import json
        formatted_vol = json.dumps(info['volume'], default=str, indent=4)
        out_lines.append("  Shape:")
        for line in formatted_vol.split('\n'):
            out_lines.append(f"    {line}")
    else:
        out_lines.append("  Shape: None")
        
    if info.get('const_colors'):
        out_lines.append("  Const colors:")
        for k, v in info['const_colors'].items():
            out_lines.append(f"    {k}: {v}")
    else:
        out_lines.append("  Const colors: None")
    
    # Rotation
    if info.get('rotation'):
        out_lines.append(f"  Rotation Block:")
        for k, v in info['rotation'].items():
            out_lines.append(f"    {k}: {v}")
    
    # Anim Channels
    for chan, result in info.get('anim_channels', {}).items():
        if result['count'] > 0:
            out_lines.append(f"  Anim[{chan}] count={result['count']}")
            out_lines.append(f"    front_slice={result['front_slice']}")
            out_lines.append(f"    back_slice ={result['back_slice']}")
            
    return "\n".join(out_lines)

def main():
    cfg = totk_main.load_config()
    if not cfg:
        return
        
    game_dump_path = cfg.get("game_dump_path")
    if not game_dump_path:
        print("[!] 'game_dump_path' not found in config.json")
        return
        
    pack_path = cfg.get("zsdic_pack_path")
    if not pack_path:
        print("[!] 'zsdic_pack_path' not found in config.json")
        return
        
    effect_dir = os.path.join(game_dump_path, "Effect")
    effect_files = load_effect_files(effect_dir)
    
    if not effect_files:
        print(f"[!] No .esetb.byml.zs files found in {effect_dir}")
        return
        
    print("[*] Loading TOTK compression dictionaries... (This might take a moment)")
    try:
        decompressors = totk_main.load_decompressors(pack_path)
    except Exception as e:
        print(f"[!] Failed to load dictionaries: {e}")
        return
        
    while True:
        effect_choice = questionary.autocomplete(
            'Select an effect file to open (type to search, Tab to autocomplete, or leave empty to exit):',
            choices=effect_files,
            style=Style([('answer', 'fg:#ff9d00 bold')])
        ).ask()
        
        if not effect_choice:
            print("Exiting...")
            break
            
        if effect_choice not in effect_files:
            print(f"[!] '{effect_choice}' is not a valid effect file. Please try again.")
            continue
            
        full_path = os.path.join(effect_dir, effect_choice)
        print(f"\n[*] Parsing {effect_choice}...")
        
        ptcl_data = get_parsed_data(full_path, decompressors)
        if not ptcl_data:
            print("[!] Could not extract particle data from this file.\n")
            continue
            
        emitters = []
        for ename, eset, emname, em, db in ptcl_tools.iter_all_emitters(ptcl_data):
            emitters.append({
                'eset': ename,
                'emtr': emname,
                'db': db
            })
            
        if not emitters:
            print("[!] No emitters found in this file.\n")
            continue
            
        while True:
            # Prepare choices for the sub-menu
            emitter_choices = [f"{e['eset']} / {e['emtr']}" for e in emitters]
            emitter_choices.insert(0, "[Back to File Selection]")
            
            em_choice = questionary.select(
                f'Select an emitter from {effect_choice} to view:',
                choices=emitter_choices,
                use_indicator=True
            ).ask()
            
            if not em_choice or em_choice == "[Back to File Selection]":
                print("") # Spacing
                break
                
            # Find the chosen emitter
            selected_em = next((e for e in emitters if f"{e['eset']} / {e['emtr']}" == em_choice), None)
            if not selected_em:
                continue
                
            # Dump the details
            info = ptcl_tools.describe_emitter(ptcl_data, selected_em['db'])
            out_text = format_emitter_info(selected_em['eset'], selected_em['emtr'], info)
            
            print("\n" + out_text + "\n")
            
            action = questionary.select(
                'What would you like to do next?',
                choices=['Go Back', 'Save to File']
            ).ask()
            
            if action == 'Save to File':
                default_name = f"{selected_em['emtr']}.yml"
                filename = questionary.text(
                    'Enter filename:', 
                    default=default_name
                ).ask()
                
                if filename:
                    try:
                        out_dir = "out"
                        os.makedirs(out_dir, exist_ok=True)
                        filepath = os.path.join(out_dir, filename)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(out_text)
                        print(f"[*] Saved emitter dump to {filepath}\n")
                    except Exception as e:
                        print(f"[!] Failed to save file: {e}\n")
                else:
                    print("") # Spacing

if __name__ == '__main__':
    main()
