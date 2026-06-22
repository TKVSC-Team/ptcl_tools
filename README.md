# TOTK Particle Effect Hub

A command-line toolkit for exploring, analyzing, and dumping particle effects (`.esetb.byml.zs`) from The Legend of Zelda: Tears of the Kingdom.

## Prerequisites

Before running the tool, ensure you have the required Python packages installed. 
Since the official PyPI version of `oead` is out of date, you MUST install it from the custom release first:

```bash
pip install tkvsc-oead 
pip install questionary prompt_toolkit zstandard
```

## Configuration

You must create a `config.json` file in the root directory (next to `main.py`). It requires two paths pointing to your local TOTK game dump:

```json
{
    "game_dump_path": "E:\\Tears\\romfs",
    "zsdic_pack_path": "E:\\Tears\\romfs\\Pack\\ZsDic.pack.zs"
}
```
- `game_dump_path`: The path to your extracted `romfs` folder. The tool will look for the `Effect` directory inside this path.
- `zsdic_pack_path`: The path to the `ZsDic.pack.zs` dictionary file, required for decompressing the effect files.

## Usage

Simply run the main script to launch the interactive CLI menu:

```bash
python main.py
```

### Features

1. **Effect Searcher (View single emitters)**
   Search through the game's `Effect` folder using autocomplete. Select a file to parse all of its emitters, then choose a specific emitter to view its detailed properties (Shapes, Colors, Animations, Rotation). You can easily export this data to a text file.

2. **Dump all shapes from an effect to JSON**
   Select an effect file to automatically parse and dump every shape inside it into a cleanly formatted `all_shapes.json` file. 

3. **Extract PtclBin from a YAML file**
   Given a YAML file containing a base64-encoded `PtclBin` node, this tool extracts the data, handles the necessary padding, and saves it out as a raw `.bin` file.

## Output Structure
When you save dumps or JSON files, they are automatically organized into an `out/` directory. The tool creates a dedicated sub-folder matching the name of the effect file (with the `.esetb.byml.zs` extension stripped off), keeping your workspace neat and tidy.