import os
import questionary
from prompt_toolkit.styles import Style

from core.byml import extract_ptcl_data
from core.parser import iter_all_emitters, describe_emitter


def format_emitter_info(eset_name, emtr_name, info):
    out_lines = []
    out_lines.append(f"# Full dump of '{eset_name}' / '{emtr_name}'")
    
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
    
    if info.get('rotation'):
        out_lines.append(f"  Rotation Block:")
        for k, v in info['rotation'].items():
            out_lines.append(f"    {k}: {v}")
    
    for chan, result in info.get('anim_channels', {}).items():
        if result['count'] > 0:
            out_lines.append(f"  Anim[{chan}] count={result['count']}")
            out_lines.append(f"    front_slice={result['front_slice']}")
            out_lines.append(f"    back_slice ={result['back_slice']}")
            
    return "\n".join(out_lines)

def run(config, decompressors):
    game_dump_path = config.get("game_dump_path")
    if not game_dump_path:
        print("[!] 'game_dump_path' not found in config.json")
        return

    from core.ui import select_effect_file, clear_screen
    
    while True:
        clear_screen()
        effect_choice, full_path = select_effect_file(game_dump_path)
        if not effect_choice:
            break
            
        print(f"\n[*] Parsing {effect_choice}...")
        
        ptcl_data = extract_ptcl_data(full_path, decompressors)
        if not ptcl_data:
            print("[!] Could not extract particle data from this file.\n")
            input("Press Enter to continue...")
            continue
            
        emitters = []
        for ename, eset, emname, em, db in iter_all_emitters(ptcl_data):
            emitters.append({
                'eset': ename,
                'emtr': emname,
                'db': db
            })
            
        if not emitters:
            print("[!] No emitters found in this file.\n")
            input("Press Enter to continue...")
            continue
            
        while True:
            clear_screen()
            print(f"--- File: {effect_choice} ---")
            
            emitter_choices = [f"{e['eset']} / {e['emtr']}" for e in emitters]
            emitter_choices.insert(0, "[Back to File Selection]")
            
            em_choice = questionary.select(
                f'Select an emitter to view:',
                choices=emitter_choices,
                use_indicator=True
            ).ask()
            
            if not em_choice or em_choice == "[Back to File Selection]":
                break
                
            selected_em = next((e for e in emitters if f"{e['eset']} / {e['emtr']}" == em_choice), None)
            if not selected_em:
                continue
                
            info = describe_emitter(ptcl_data, selected_em['db'])
            out_text = format_emitter_info(selected_em['eset'], selected_em['emtr'], info)
            
            clear_screen()
            print("\n" + out_text + "\n")
            
            action = questionary.select(
                'What would you like to do next?',
                choices=['Go Back', 'Save to File']
            ).ask()
            
            if action == 'Save to File':
                default_name = f"{selected_em['emtr']}.yaml"
                filename = questionary.text('Enter filename:', default=default_name).ask()
                
                if filename:
                    try:
                        dir_name = effect_choice.replace('.esetb.byml.zs', '')
                        out_dir = os.path.join("out", dir_name)
                        os.makedirs(out_dir, exist_ok=True)
                        filepath = os.path.join(out_dir, filename)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(out_text)
                        print(f"[*] Saved emitter dump to {filepath}\n")
                    except Exception as e:
                        print(f"[!] Failed to save file: {e}\n")
                else:
                    print("")
