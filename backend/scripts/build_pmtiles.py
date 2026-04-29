from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from cartography_common import ensure_processed_countries


BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
TILES_DIR = DATA_DIR / "tiles"
PMTILES_PATH = TILES_DIR / "pax1933_map.pmtiles"
LAYER_INPUTS = [
    ("countries", PROCESSED_DIR / "countries_1933.geojson"),
    ("regions", PROCESSED_DIR / "regions_1933.geojson"),
    ("microstates", PROCESSED_DIR / "microstates_1933.geojson"),
    ("rivers", PROCESSED_DIR / "rivers_1933.geojson"),
    ("country_label_lines", PROCESSED_DIR / "country_label_lines_1933.geojson"),
    ("country_label_points", PROCESSED_DIR / "country_label_points_1933.geojson"),
    ("region_label_points", PROCESSED_DIR / "region_label_points_1933.geojson"),
    ("microstate_label_points", PROCESSED_DIR / "microstate_label_points_1933.geojson"),
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ensure_processed_countries()
    missing = [path for _, path in LAYER_INPUTS if not path.exists()]
    if missing:
        print("Cannot build PMTiles because processed layers are missing:")
        for path in missing:
            print(f"  - {path}")
        print("Run the preparation scripts listed in README before build_pmtiles.py.")
        raise RuntimeError("missing processed GeoJSON")

    tippecanoe = shutil.which("tippecanoe")
    if not tippecanoe:
        print("Tippecanoe is not installed. Install it or run Docker fallback.")
        print("Install Tippecanoe, then run: python scripts/build_pmtiles.py")
        print("On Windows without a native Tippecanoe install, use:")
        print("  powershell -ExecutionPolicy Bypass -File scripts/build_pmtiles_docker.ps1")
        raise RuntimeError("missing tippecanoe")

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        tippecanoe,
        "--force",
        "-o",
        str(PMTILES_PATH),
        "-Z",
        "0",
        "-z",
        "8",
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--detect-shared-borders",
        "--no-tile-size-limit",
    ]
    for layer_name, path in LAYER_INPUTS:
        command.extend(["-L", f"{layer_name}:{path}"])

    print("Running Tippecanoe:")
    print(" ".join(str(part) for part in command))
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"failed command: tippecanoe exited with code {exc.returncode}") from exc

    if not PMTILES_PATH.exists():
        raise RuntimeError(f"wrong output path or failed build: {PMTILES_PATH} was not created")
    size_bytes = PMTILES_PATH.stat().st_size
    if size_bytes <= 0:
        raise RuntimeError(f"wrong output path or failed build: {PMTILES_PATH} is empty")

    print(f"saved: {PMTILES_PATH}")
    print(f"sizeBytes: {size_bytes}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2) from exc
