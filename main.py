import argparse
import sys

from core.config import load_config
from core.compression import load_decompressors

def interactive_main_loop():
    import questionary
    config = load_config()
    if not config:
        return
        
    pack_path = config.get("zsdic_pack_path")
    if not pack_path:
        print("[!] 'zsdic_pack_path' not found in config.json")
        return
        
    print("[*] Loading TOTK compression dictionaries... (This might take a moment)")
    try:
        decompressors = load_decompressors(pack_path)
    except Exception as e:
        print(f"[!] Failed to load dictionaries: {e}")
        return

    while True:
        from core.ui import clear_screen
        clear_screen()
        
        mode = questionary.select(
            "What would you like to do?",
            choices=[
                "1. Effect Searcher (View single emitters)",
                "2. Dump all shapes from an effect to JSON",
                "3. Extract PtclBin from a YAML file",
                "Exit"
            ]
        ).ask()
        
        if mode == "1. Effect Searcher (View single emitters)":
            from commands.interactive import run
            run(config, decompressors)
        elif mode == "2. Dump all shapes from an effect to JSON":
            from commands.interactive_dumper import run
            run(config, decompressors)
        elif mode == "3. Extract PtclBin from a YAML file":
            from commands.interactive_extractor import run
            run()
        else:
            print("Goodbye!")
            break

def main():
    parser = argparse.ArgumentParser(description="PTCL Tools")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Interactive Command
    parser_interactive = subparsers.add_parser("interactive", help="Open the interactive searcher menu")

    # Analyze Command
    parser_analyze = subparsers.add_parser("analyze", help="Analyze a specific .esetb.byml.zs file")
    parser_analyze.add_argument("file", help="Path to the .esetb.byml.zs file")
    parser_analyze.add_argument("--target", required=True, help="Name of the emitter to target (e.g. Fire_Spark)")

    # Dump Command
    parser_dump = subparsers.add_parser("dump", help="Dump all shapes from a .bin file to JSON")
    parser_dump.add_argument("file", help="Path to the .bin file")

    # Extract Command
    parser_extract = subparsers.add_parser("extract", help="Extract PtclBin from a YAML file")
    parser_extract.add_argument("input", help="Path to the input YAML file")
    parser_extract.add_argument("output", help="Path to the output .bin file")

    args = parser.parse_args()

    if not args.command:
        interactive_main_loop()
        return

    elif args.command == "analyze":
        config = load_config()
        if not config:
            return
            
        pack_path = config.get("zsdic_pack_path")
        if not pack_path:
            print("[!] 'zsdic_pack_path' not found in config.json")
            return
            
        print("[*] Loading TOTK compression dictionaries...")
        try:
            decompressors = load_decompressors(pack_path)
        except Exception as e:
            print(f"[!] Failed to load dictionaries: {e}")
            return
            
        from commands.analyzer import run
        run(args.file, args.target, decompressors)

    elif args.command == "dump":
        from commands.dumper import run
        run(args.file)

    elif args.command == "extract":
        from commands.extractor import run
        run(args.input, args.output)

if __name__ == "__main__":
    main()