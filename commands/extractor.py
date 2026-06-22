import re
import base64

def run(input_file, output_file):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: The file '{input_file}' was not found.")
        return

    # Regex: Looks for 'PtclBin:', followed by anything (non-greedy), 
    # then '!!binary', then captures the continuous base64 string.
    pattern = r'PtclBin:.*?!!binary\s+([A-Za-z0-9+/=]+)'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        b64_data = match.group(1)
        
        # Base64 strings must be a multiple of 4 in length.
        padding_needed = len(b64_data) % 4
        if padding_needed:
            b64_data += '=' * (4 - padding_needed)

        try:
            binary_data = base64.b64decode(b64_data)
            with open(output_file, 'wb') as out_f:
                out_f.write(binary_data)
            print(f"Success! Extracted {len(binary_data)} bytes to '{output_file}'.")
        except Exception as e:
            print(f"Error decoding base64 data: {e}")
    else:
        print("Could not find the 'PtclBin' base64 data in the file.")
