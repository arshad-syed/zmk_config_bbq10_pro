#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$repo_dir/.build" "$repo_dir/firmware"

# Use the same build image as ZMK's build-user-config.yml workflow.
docker run --rm -i \
  --mount "type=bind,source=$repo_dir,target=/repo,readonly" \
  --mount "type=bind,source=$repo_dir/.build,target=/workspace" \
  --mount "type=bind,source=$repo_dir/firmware,target=/out" \
  --workdir /workspace \
  --entrypoint /bin/bash \
  zmkfirmware/zmk-build-arm:stable -se <<'BUILD'
set -euo pipefail

mkdir -p config
cp /repo/config/west.yml config/west.yml
if [ ! -d .west ]; then
  west init -l config
fi
west update --fetch-opt=--filter=tree:0
west zephyr-export
west manifest --freeze --active-only > west-manifest.lock.yml

python3 - <<'PY'
from pathlib import Path
import shlex
import shutil
import subprocess
import yaml

matrix = yaml.safe_load(Path("/repo/build.yaml").read_text())
for target in matrix["include"]:
    board = target["board"]
    shield = target.get("shield", "")
    name = target.get("artifact-name") or f"{shield + '-' if shield else ''}{board}-zmk"
    build_dir = Path("/workspace/build") / name
    command = [
        "west", "build", "-s", "/workspace/zmk/app", "-d", str(build_dir),
        "-b", board, "-p", "always",
    ]
    if target.get("snippet"):
        command += ["-S", target["snippet"]]
    command += ["--", "-DZMK_CONFIG=/repo/config"]
    if shield:
        command += [f"-DSHIELD={shield}"]
    command += shlex.split(target.get("cmake-args", ""))
    print(f"Building {name}: {shlex.join(command)}", flush=True)
    subprocess.run(command, check=True)
    output = Path("/out") / f"{name}.uf2"
    shutil.copy2(build_dir / "zephyr/zmk.uf2", output)
    print(f"Firmware created: {output}", flush=True)
PY
BUILD

printf '\nFirmware files: %s/firmware/\n' "$repo_dir"
