"""Экспорт реестров дела в JSON для интерактивного древа на сайте."""

from __future__ import annotations

import csv
import json
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
OUT = CASE.parent / "docs" / "tree-data.json"

# Портреты из семейного архива: путь относительно docs/
PHOTOS = {
    "P-0023": "photos/family/chertkov-nikifor.jpg",
    "P-0031": "photos/family/malanya-savelyevna.jpg",
    "P-0032": "photos/family/tarasenko-semyon.jpg",
    "P-0021": "photos/family/ligin-davyd-and-voronko.jpg",
    "P-0010": "photos/family/voronko-mikhail-nikolai-group.jpg",
    "P-0016": "photos/family/voronko-ekaterina-nikolai-grigory-mikhail.jpg",
    "P-0019": "photos/family/voronko-ekaterina-nikolai-grigory-mikhail.jpg",
    "P-0020": "photos/family/voronko-ekaterina-nikolai-grigory-mikhail.jpg",
    "P-0022": "photos/family/voronko-mikhail-nikolai-group.jpg",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def main() -> int:
    persons = read_rows(CASE / "person-register.csv")
    relations = read_rows(CASE / "relationship-register.csv")

    parents: dict[str, list[str]] = {}
    spouses: list[list[str]] = []
    extra: list[dict[str, str]] = []

    for rel in relations:
        kind = rel["relationship_type"]
        a, b = rel["person_a_id"], rel["person_b_id"]
        if kind == "parent-child":
            parents.setdefault(b, []).append(a)
        elif kind == "spouse":
            spouses.append([a, b])
        else:
            extra.append({"a": a, "b": b, "type": kind, "note": rel["rationale"]})

    data = {
        "persons": [
            {
                "id": p["person_id"],
                "name": p["preferred_label"],
                "birth": p["birth_estimate"],
                "death": p["death_estimate"],
                "place": p["places"],
                "status": p["candidate_status"],
                "artifacts": [x.strip() for x in p["source_artifact_ids"].split(";") if x.strip()],
                "photo": PHOTOS.get(p["person_id"], ""),
                "notes": p["notes"],
            }
            for p in persons
        ],
        "parents": parents,
        "spouses": spouses,
        "extra": extra,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Записано: {OUT}")
    print(f"Персон: {len(data['persons'])}, пар родителей: {len(parents)}, браков: {len(spouses)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
