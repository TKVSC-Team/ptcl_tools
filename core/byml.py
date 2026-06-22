import oead
from .compression import decompress_totk_file

def find_ptcl_bytes_in_byml(byml_node):
    """
    Recursively searches the BYML hash/dictionary for the 'PtclBin' key.
    oead parses binary nodes directly into Python bytes.
    """
    if isinstance(byml_node, (dict, getattr(oead.byml, 'Hash', dict), getattr(oead.byml, 'Dictionary', dict))):
        if "PtclBin" in byml_node:
            return byml_node["PtclBin"]
        
        for key, value in byml_node.items():
            result = find_ptcl_bytes_in_byml(value)
            if result: return result
            
    elif isinstance(byml_node, (list, getattr(oead.byml, 'Array', list))):
        for item in byml_node:
            result = find_ptcl_bytes_in_byml(item)
            if result: return result
            
    return None

def extract_ptcl_data(filepath, decompressors):
    """
    Decompresses the file and extracts the PtclBin data.
    Returns the raw bytes or None.
    """
    try:
        byml_bytes = decompress_totk_file(filepath, decompressors)
        byml_data = oead.byml.from_binary(byml_bytes)
        ptcl_raw_bytes = find_ptcl_bytes_in_byml(byml_data)
        
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
