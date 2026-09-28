"""Reproducible fixed-opponent rollout experiment; saves errors and replays.

python3 tools/eval_tactical.py --seeds 0-39 --output out/tactical/screen
"""
import argparse
import json
import os
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from arena import ROOT, SubprocessBot, load_config, run_match, parse_seeds


class MeasuredBot(SubprocessBot):
    def __init__(self, cmd):
        super().__init__(cmd, name=cmd, capture_stderr=True)
        self.errors = []
        self.turn_times = []
        self.reader = threading.Thread(target=lambda: self.errors.extend(self.proc.stderr), daemon=True)
        self.reader.start()

    def collect_turn(self):
        self.max_turn_ms = 0
        result = super().collect_turn()
        self.turn_times.append(self.max_turn_ms)
        return result


def play(job):
    label, opp, seed, side, a, b, output = job
    bots = [MeasuredBot(cmd) for cmd in ((a, b) if side == "Y" else (b, a))]
    try:
        cfg = load_config()
        cfg["first_turn_timeout_ms"] = 3000
        replay, result = run_match(seed, cfg, *bots, turn_timeout_ms=300)
    finally:
        for bot in bots:
            bot.close()
            bot.reader.join(timeout=2)
    own = bots[0 if side == "Y" else 1]
    row = dict(label=label, opp=opp, seed=seed, side=side, result=result,
               point=0.5 if result["winner"] == "DRAW" else float(result["winner"] == side),
               max_ms=max(own.turn_times[1:], default=0), first_ms=own.turn_times[0],
               stderr=["".join(bot.errors) for bot in bots])
    if seed < 3:
        path = Path(output) / f"{label}-{opp}-{seed}-{side}.json"
        path.write_text(json.dumps(replay, ensure_ascii=False), encoding="utf-8")
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", default="0-39")
    p.add_argument("--opps", default="v10,v9,v8,v6")
    p.add_argument("--output", default="out/tactical/screen")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--checks", action="store_true")
    p.add_argument("--candidate-only", action="store_true", help="Reuse an already measured identical baseline")
    args = p.parse_args()
    os.chdir(ROOT)
    os.environ.pop("BOT_PARAMS", None)
    os.environ.pop("BOT_STATS", None)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    candidate = out / "candidate.sh"
    candidate.write_text('#!/bin/sh\nexport BOT_PARAMS=\'{"tactical_rollout":true}\'\nexec python3 Model/main.py\n')
    a, base = f"sh {candidate}", "python3 Model/history/v10/main.py"
    jobs = []
    if args.checks:
        for label, left, right in (("disabled", "python3 Model/main.py", base), ("mirror", a, a)):
            for seed in range(10):
                jobs.append((label, "self", seed, "Y", left, right, str(out)))
    else:
        for label, cmd in (("baseline", base), ("candidate", a)):
            if args.candidate_only and label == "baseline":
                continue
            for opp in args.opps.split(","):
                b = f"python3 Model/history/{opp}/main.py"
                for seed in parse_seeds(args.seeds):
                    for side in "YK":
                        jobs.append((label, opp, seed, side, cmd, b, str(out)))
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex, (out / "results.jsonl").open("w") as log:
        futures = [ex.submit(play, job) for job in jobs]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            log.write(json.dumps(row) + "\n")
            log.flush()
            if len(rows) % 20 == 0:
                print(f"{len(rows)}/{len(jobs)} complete", flush=True)
    report = {}
    for label in sorted({r["label"] for r in rows}):
        selected = [r for r in rows if r["label"] == label]
        report[label] = dict(games=len(selected), rate=sum(r["point"] for r in selected) / len(selected),
                            draws=sum(r["point"] == .5 for r in selected),
                            max_ms=max(r["max_ms"] for r in selected),
                            errors=sum(any(r["stderr"]) for r in selected),
                            forfeits=sum(bool(r["result"].get("forfeit")) for r in selected),
                            opponents={opp: sum(r["point"] for r in selected if r["opp"] == opp) /
                                       sum(r["opp"] == opp for r in selected)
                                       for opp in sorted({r["opp"] for r in selected})})
    (out / "summary.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
