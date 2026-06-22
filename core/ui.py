import os
import questionary
from prompt_toolkit.styles import Style

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("╔" + "═" * 58 + "╗")
    print("║" + "PTCL Tools".center(58) + "║")
    print("╚" + "═" * 58 + "╝\n")

def select_effect_file(game_dump_path):
    effect_dir = os.path.join(game_dump_path, "Effect")
    if not os.path.exists(effect_dir):
        print(f"[!] Effect directory not found: {effect_dir}")
        return None, None
        
    files = [f for f in os.listdir(effect_dir) if f.endswith('.esetb.byml.zs')]
    if not files:
        print(f"[!] No .esetb.byml.zs files found in {effect_dir}")
        return None, None
        
    effect_choice = questionary.autocomplete(
        'Select an effect file (type to search, Tab to autocomplete, or leave empty to exit):',
        choices=sorted(files),
        style=Style([('answer', 'fg:#ff9d00 bold')])
    ).ask()
    
    if not effect_choice or effect_choice not in files:
        return None, None
        
    full_path = os.path.join(effect_dir, effect_choice)
    return effect_choice, full_path
