"""Run: python3 tools/test_tactical.py (includes official-engine comparison)."""
import sys
import importlib.util
import json
import time
import subprocess
import tempfile
import zipfile
from itertools import product
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "Model"), str(ROOT / "BaseLines/yk-development-tools")]
from main import Geo
from tactical import combat, capture, rollout
from engine.config import load_config
from engine.state import GameState, Building, blank_terrain
from engine.pipeline import step_combat, step_capture


def replay_check(folder):
    """Exact disabled-command parity and single-process decision timing."""
    import main as current
    from protocol import parse_init, parse_turn
    from runner.protocol import serialize_init, serialize_turn
    from mapgen import generate, to_state
    from engine.pipeline import run_turn
    from runner.protocol import parse_commands

    spec = importlib.util.spec_from_file_location("frozen_v10", ROOT / "Model/history/v10/main.py")
    frozen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen)
    times = []
    compared = 0
    for path in sorted(Path(folder).glob("candidate-*.json")):
        replay = json.loads(path.read_text())
        for team in ("Y", "K"):
            cfg = replay["config"]
            state = to_state(generate(replay["seed"], cfg))
            init = parse_init(serialize_init(state, team).splitlines())
            current.GEO = current.MEM = frozen.GEO = frozen.MEM = None
            # Each mode needs its own persistent memory on the same observations.
            spec2 = importlib.util.spec_from_file_location("enabled", ROOT / "Model/main.py")
            enabled = importlib.util.module_from_spec(spec2)
            spec2.loader.exec_module(enabled)
            enabled.P["tactical_rollout"] = True
            for entry in replay["turns"]:
                view = parse_turn(serialize_turn(state, team, entry["turn"]).splitlines(), init)
                assert current.decide(view, init) == frozen.decide(view, init), (path, team, entry["turn"])
                start = time.perf_counter()
                enabled.decide(view, init)
                elapsed = 1000 * (time.perf_counter() - start)
                if entry["turn"] > 1:
                    times.append(elapsed)
                compared += 1
                state, _ = run_turn(state, parse_commands(entry["commands"]["Y"]),
                                    parse_commands(entry["commands"]["K"]))
    assert compared, "No candidate replays found"
    times.sort()
    result = dict(commands_compared=compared, max_ms=max(times), p99_ms=times[int(len(times) * .99)])
    print(json.dumps(result, indent=2))
    return result


def main():
    cfg = load_config()
    checked = 0
    for yw, kw, yf, kf, owner, resource in product(range(4), range(4), range(2), range(2), (-1, 0, 1), (0, 1, 2, 4)):
        teams = ("Y", "K")
        b = Building(0, 2, 2, "HALL", 2, "N" if owner == -1 else teams[owner], 0 if owner == -1 else 2)
        state = GameState(cfg, blank_terrain(cfg), {0: b}, {"Y": (0, 0), "K": (14, 14)},
                          resources={"Y": resource, "K": resource})
        for team, nw, nf in (("Y", yw, yf), ("K", kw, kf)):
            state.add_unit(2, 2, team, "W", nw)
            state.add_unit(2, 2, team, "F", nf)
        w, f = [{16: yw}, {16: kw}], [{16: yf}, {16: kf}]
        local_owner, _ = combat(w, f, owner, 16)
        res = [resource, resource]
        local_owner = capture(local_owner, [f[0].get(16, 0), f[1].get(16, 0)], res, [2, 2])
        step_combat(state)
        step_capture(state, {"Y": [], "K": []})
        assert local_owner == ({"N": -1, "Y": 0, "K": 1}[b.owner])
        assert res == [state.resources[t] for t in teams]
        for side, team in enumerate(teams):
            assert w[side].get(16, 0) == state.get_unit(2, 2, team, "W")
            assert f[side].get(16, 0) == state.get_unit(2, 2, team, "F")
        checked += 1
    geo = Geo(SimpleNamespace(width=7, height=7, team="Y", passable=lambda x, y: 0 <= x < 7 and 0 <= y < 7))

    def run(**kw):
        args = dict(geo=geo, target=24, actor=23, first=24, groups=[], my_f={23: 1},
                    en_w={}, en_f={}, resource=(20, 20), income=(0, 0), costs=(3, 3),
                    cap_costs=(2, 2), spawns=([], []), owner=1, btype="WATCH",
                    worth=3, horizon=3, policy="hold")
        args.update(kw)
        return rollout(**args)

    assert run()["capture_turn"] == 2  # empty enemy building requires two stages
    assert run(wait="hold")["capture_turn"] is None
    assert run(wait=True)["capture_turn"] == 3
    assert run(groups=[(24, 24, 2)], en_w={24: 1}, en_f={24: 1})["capture_turn"] == 1
    contested = run(groups=[(24, 24, 1)], en_w={24: 1}, en_f={24: 1})
    assert contested["capture_turn"] is None and contested["actor_alive"]
    assert contested["losses"] == [[1, 0], [1, 0]]  # casualties never return next turn
    assert run(en_w={24: 1})["actor_alive"] is False
    # Crossing edges is not combat; only the common destination matters.
    crossed = run(actor=23, first=24, en_w={24: 1}, policy="hunt", horizon=1)
    assert crossed["actor_alive"] and crossed["losses"] == [[0, 0], [0, 0]]
    # Gaining a hospital makes it usable for production on later turns only.
    hospital = run(owner=-1, btype="HOSPITAL", income=(10, 10), horizon=3)
    assert hospital["capture_turn"] == 1 and hospital["held"] == 3
    counterattack = dict(owner=-1, income=(10, 0), en_w={28: 3},
                         horizon=5, policy="reinforce")
    assert run(btype="HOSPITAL", **counterattack)["actor_alive"]
    assert not run(btype="WATCH", **counterattack)["actor_alive"]
    print(f"PASS: {checked} official combat/capture comparisons + tactical continuation checks")
    from make_zip import FILES, inspect_zip
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "bot.zip"
        with zipfile.ZipFile(archive, "w") as z:
            for name in FILES:
                z.writestr(name, (ROOT / "Model" / name).read_bytes())
        assert inspect_zip(archive)["ok"]
        subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import main",
                        str(archive)], cwd=temp, check=True)
    print("PASS: submission archive validation and isolated import")


if __name__ == "__main__":
    main()
    if len(sys.argv) > 1:
        replay_check(sys.argv[1])
