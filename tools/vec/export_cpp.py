"""정책망 체크포인트 → C++ 제출물(main.cpp + weights.hpp + submission.json) 과 ZIP.

가중치는 float16 비트를 정수 배열로 weights.hpp 에 직접 넣는다(대회 공지: 소스에 포함한 상수·배열 허용, 별도 데이터 파일 불가).
ZIP 은 일반 파일 권한(0644)으로 기록하고 공식 inspect_zip 검사를 통과해야 한다. 이름은 submission-Junghoon-<버전>.zip.

사용 (WSL, 프로젝트 루트):
  python3 tools/vec/export_cpp.py --ckpt out/rl/vs1/it00500.pt --version nn1
  → out/sub/nn1/{main.cpp, weights.hpp, submission.json}, submissions/submission-Junghoon-nn1.zip
"""
import argparse
import json
import stat
import sys
import zipfile
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Model/sparring/rlbot"))
sys.path.insert(0, str(ROOT / "BaseLines/yk-development-tools/bots/dist/starter"))

from model import load_net  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ckpt", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--author", default="Junghoon")
    args = p.parse_args()
    net, _ = load_net(ROOT / args.ckpt)
    sd = {k: v.detach().float().numpy() for k, v in net.state_dict().items()}
    ch, blocks = net.arch["ch"], net.arch["blocks"]
    parts, offs = [], {}
    pos = 0

    def add(name, key):
        nonlocal pos
        a = sd[key].reshape(-1)
        offs[name] = pos
        parts.append(a)
        pos += a.size

    add("NN_STEM_W", "stem.weight"); add("NN_STEM_B", "stem.bias")
    for b in range(blocks):
        add(f"B{b}W1", f"body.{b}.c1.weight"); add(f"B{b}B1", f"body.{b}.c1.bias")
        add(f"B{b}W2", f"body.{b}.c2.weight"); add(f"B{b}B2", f"body.{b}.c2.bias")
    add("NN_MOVE_W", "move.weight"); add("NN_MOVE_B", "move.bias")
    add("NN_GLOB_W", "glob.0.weight"); add("NN_GLOB_B", "glob.0.bias")
    add("NN_F_W", "spawn_f.weight"); add("NN_F_B", "spawn_f.bias")
    add("NN_WF_W", "spawn_w.weight"); add("NN_WF_B", "spawn_w.bias")
    allw = np.concatenate(parts).astype(np.float16).view(np.uint16)

    out = ROOT / "out/sub" / args.version
    out.mkdir(parents=True, exist_ok=True)
    lines = [f"// 자동 생성: tools/vec/export_cpp.py --ckpt {args.ckpt}", "#pragma once", "#include <cstddef>",
             "#include <cstdint>", f"constexpr int NN_CH = {ch};", f"constexpr int NN_BLOCKS = {blocks};"]
    for k in ("NN_STEM_W", "NN_STEM_B", "NN_MOVE_W", "NN_MOVE_B", "NN_GLOB_W", "NN_GLOB_B", "NN_F_W", "NN_F_B", "NN_WF_W", "NN_WF_B"):
        lines.append(f"constexpr size_t {k} = {offs[k]};")
    for tag, key in (("W1", "W1"), ("B1", "B1"), ("W2", "W2"), ("B2", "B2")):
        vals = ", ".join(str(offs[f"B{b}{key}"]) for b in range(blocks))
        lines.append(f"constexpr size_t NN_BLK_{tag}[NN_BLOCKS] = {{{vals}}};")
    lines.append(f"static const uint16_t NN_W16[{allw.size}] = {{")
    for i in range(0, allw.size, 24):
        lines.append(",".join(f"0x{v:04x}" for v in allw[i:i + 24]) + ",")
    lines.append("};")
    (out / "weights.hpp").write_text("\n".join(lines) + "\n")
    (out / "main.cpp").write_text((ROOT / "tools/vec/cpp/nn_main.cpp").read_text())
    (out / "submission.json").write_text(json.dumps({"schemaVersion": 1, "language": "cpp"}, indent=2) + "\n")

    zpath = ROOT / "submissions" / f"submission-{args.author}-{args.version}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("submission.json", "main.cpp", "weights.hpp"):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 28, 0, 0, 0))
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (out / name).read_bytes())
    from submission import inspect_zip
    rep = inspect_zip(zpath)
    print(f"가중치 {allw.size}개, weights.hpp {(out / 'weights.hpp').stat().st_size / 1e6:.1f}MB, "
          f"ZIP {zpath.stat().st_size / 1e6:.2f}MB → {zpath}")
    print(f"inspect_zip: {rep}")


if __name__ == "__main__":
    main()
