import os
import zstandard as zstd
import oead

def load_decompressors(zsdic_pack_path):
    """
    Decompresses ZsDic.pack.zs, reads the SARC archive, 
    and initializes the dictionary fallbacks.
    """
    if not os.path.exists(zsdic_pack_path):
        raise FileNotFoundError(f"Could not find dictionary pack at {zsdic_pack_path}")

    with open(zsdic_pack_path, 'rb') as f:
        compressed_pack = f.read()
    
    dctx = zstd.ZstdDecompressor()
    sarc_bytes = dctx.decompress(compressed_pack)

    sarc = oead.Sarc(sarc_bytes)

    zs_dict_file = sarc.get_file("zs.zsdic")
    pack_dict_file = sarc.get_file("pack.zsdic")
    bcett_dict_file = sarc.get_file("bcett.byml.zsdic")

    if not all([zs_dict_file, pack_dict_file, bcett_dict_file]):
        raise ValueError("ZsDic.pack.zs damaged! One or more dictionary files unreadable.")

    zs_dict = zstd.ZstdCompressionDict(
        bytes(zs_dict_file.data), dict_type=zstd.DICT_TYPE_AUTO
    )
    pack_dict = zstd.ZstdCompressionDict(
        bytes(pack_dict_file.data), dict_type=zstd.DICT_TYPE_AUTO
    )
    bcett_dict = zstd.ZstdCompressionDict(
        bytes(bcett_dict_file.data), dict_type=zstd.DICT_TYPE_AUTO
    )

    return [
        ("pack", zstd.ZstdDecompressor(dict_data=pack_dict)),
        ("bcett", zstd.ZstdDecompressor(dict_data=bcett_dict)),
        ("zs", zstd.ZstdDecompressor(dict_data=zs_dict)),
        ("none", zstd.ZstdDecompressor()),
    ]

def decompress_totk_file(filepath, decompressors):
    """Attempts to decompress a file using the fallback list."""
    with open(filepath, 'rb') as f:
        compressed_data = f.read()

    for name, dctx in decompressors:
        try:
            return dctx.decompress(compressed_data)
        except zstd.ZstdError:
            continue
            
    raise Exception(f"Decompression failed for {filepath}: Dictionary mismatch on all attempts.")
