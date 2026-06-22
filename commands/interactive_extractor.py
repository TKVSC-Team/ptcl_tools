import questionary
from core.ui import clear_screen
from .extractor import run as extractor_run

def run():
    clear_screen()
    print("--- Extract PtclBin from YAML ---")
    input_file = questionary.text('Enter the path to the input YAML file (or leave empty to cancel):').ask()
    if not input_file:
        return
        
    output_file = questionary.text('Enter the desired path for the output binary file (e.g. output.bin):').ask()
    if not output_file:
        return
        
    extractor_run(input_file, output_file)
    input("\nPress Enter to continue...")
