"""Upscale the Packed Light test-cut pictures (1672x941) to 1920x1080 as remotion/public/pk-ep01/images/sceneNN.png.
Reads the file names from content-prompts/packed_light/ep01_open_test.csv (rows after the REF row)."""
import csv, os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
src = ROOT / "content-prompts" / "packed_light"
out = ROOT / "remotion" / "public" / "pk-ep01" / "images"
out.mkdir(parents=True, exist_ok=True)
rows = list(csv.reader(open(src / "ep01_open_test.csv", encoding="utf-8-sig", newline="")))[2:]
for i, r in enumerate(rows, 1):
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", str(src / "images" / r[1]), "-vf", "scale=1920:1080:flags=lanczos", str(out / f"scene{i:02d}.png")])
print("images:", len(rows))
