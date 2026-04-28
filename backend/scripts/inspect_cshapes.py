from __future__ import annotations

import json
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_PATH = BACKEND_DIR / "data" / "raw" / "CShapes-2.0.geojson"


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"CShapes file not found: {RAW_PATH}")

    with RAW_PATH.open("r", encoding="utf-8") as f:
        geojson = json.load(f)

    features = geojson.get("features", [])
    print(f"features: {len(features)}")

    if not features:
        return

    first_properties = features[0].get("properties", {})
    print("property fields:")
    for field in first_properties:
        print(f"- {field}")

    print("first 10 properties:")
    for index, feature in enumerate(features[:10], start=1):
        print(f"{index}. {json.dumps(feature.get('properties', {}), ensure_ascii=False)}")


if __name__ == "__main__":
    main()
