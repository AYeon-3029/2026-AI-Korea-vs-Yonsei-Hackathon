import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'BaseLines/yk-development-tools'))
from engine.config import load_config
from mapgen import generate
from mapgen.render import render_ascii
cfg = load_config()
for s in map(int, sys.argv[1:]):
    print(render_ascii(generate(s, cfg)))
    print()
