#!/usr/bin/env python3
"""Собирает GEDCOM 5.5.1 из реестров дела.

Читает person-register.csv и relationship-register.csv, пишет tree.ged.
Скрипт не оценивает доказательства: статусы связей переносятся в NOTE.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent.parent
PERSONS = CASE_DIR / "person-register.csv"
RELATIONS = CASE_DIR / "relationship-register.csv"
OUT = CASE_DIR / "tree.ged"

MONTHS = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
}
FEMALE_NAMES = {
    "лидия", "наталья", "светлана", "валентина", "ольга", "ирина", "людмила",
    "татьяна", "александра", "маланья", "меланья", "елена", "зинаида",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def clean_label(label: str) -> str:
    text = re.sub(r"\([^)]*\)", "", label)
    text = text.replace(",", " ")
    return re.sub(r"\s+", " ", text).strip()


def split_name(label: str) -> tuple[str, str]:
    parts = clean_label(label).split()
    if len(parts) < 2:
        return clean_label(label), ""
    return " ".join(parts[1:]), parts[0]


def sex_of(label: str) -> str:
    text = clean_label(label).lower()
    if re.search(r"(овна|евна|ична|инична)$", text):
        return "F"
    if re.search(r"(ович|евич|ьич)$", text):
        return "M"
    first = text.split()[0] if text.split() else ""
    return "F" if first in FEMALE_NAMES else "M"


def gedcom_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match:
        year, month, day = match.groups()
        return f"{int(day)} {MONTHS[int(month)]} {year}"
    if re.fullmatch(r"\d{4}", value):
        return value
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value):
        day, month, year = value.split(".")
        return f"{int(day)} {MONTHS[int(month)]} {year}"
    if re.fullmatch(r"\d{2}\.\d{2}", value):
        day, month = value.split(".")
        return f"ABT {int(day)} {MONTHS[int(month)]}"
    return "ABT " + value


def build_families(relations: list[dict[str, str]]) -> list[dict[str, object]]:
    families: list[dict[str, object]] = []
    spouse_keys: dict[tuple[str, str], str] = {}

    for row in relations:
        if row["relationship_type"] != "spouse":
            continue
        key = tuple(sorted((row["person_a_id"], row["person_b_id"])))
        if key in spouse_keys:
            continue
        fid = f"@F{len(families) + 1}@"
        spouse_keys[key] = fid
        families.append({"id": fid, "parents": list(key), "children": []})

    parents_of: dict[str, list[str]] = {}
    for row in relations:
        if row["relationship_type"] == "parent-child":
            parents_of.setdefault(row["person_b_id"], []).append(row["person_a_id"])

    single_families: dict[str, str] = {}
    for child_id, parent_ids in parents_of.items():
        target = next(
            (
                family
                for family in families
                if set(parent_ids) == set(family["parents"])
            ),
            None,
        )
        if target is not None:
            target["children"].append(child_id)  # type: ignore[union-attr]
            continue
        # Нет подтверждённого брака: ребёнка привязываем к отдельной семье
        # каждого известного родителя, чтобы не назначать второго родителя.
        for parent_id in parent_ids:
            if parent_id not in single_families:
                fid = f"@F{len(families) + 1}@"
                single_families[parent_id] = fid
                families.append({"id": fid, "parents": [parent_id], "children": []})
            family = next(f for f in families if f["id"] == single_families[parent_id])
            family["children"].append(child_id)  # type: ignore[union-attr]

    return families


def main() -> int:
    persons = read_rows(PERSONS)
    relations = read_rows(RELATIONS)
    person_by_id = {row["person_id"]: row for row in persons}
    families = build_families(relations)

    xref = {row["person_id"]: f"@I{index}@" for index, row in enumerate(persons, start=1)}
    child_to_family: dict[str, list[str]] = {}
    spouse_families: dict[str, list[str]] = {}
    for family in families:
        for child_id in family["children"]:  # type: ignore[union-attr]
            child_to_family.setdefault(child_id, []).append(str(family["id"]))
        for parent_id in family["parents"]:  # type: ignore[union-attr]
            spouse_families.setdefault(parent_id, []).append(str(family["id"]))

    lines: list[str] = [
        "0 HEAD",
        "1 SOUR DREVO",
        "2 VERS 1.0",
        "2 NAME Древо — семейное исследование",
        "1 GEDC",
        "2 VERS 5.5.1",
        "2 FORM LINEAGE-LINKED",
        "1 CHAR UTF-8",
        "1 LANG Russian",
        "1 SUBM @U1@",
        "0 @U1@ SUBM",
        "1 NAME Артём Прудников",
        "",
        "0 @S1@ SOUR",
        "1 TITL Семейные сведения, собранные у родителей, 06.11.2026",
        "1 AUTH Прудников Артём Сергеевич",
        "1 NOTE Все связи и даты опираются на семейную память и требуют архивного подтверждения.",
        "",
        "0 @S2@ SOUR",
        "1 TITL Память народа: Чертков Никифор Семёнович, 1909, медаль «За отвагу»",
        "1 PUBL https://pamyat-naroda.ru/heroes/podvig-chelovek_nagrazhdenie80115881/",
        "1 NOTE Приказ Президиума ВС СССР № 204 от 06.08.1946.",
        "",
        "0 @S3@ SOUR",
        "1 TITL ЦАМО, ф. 33, оп. 744807, д. 658, л. 467-468: наградной лист Черткова Н. С.",
        "1 NOTE Сканы: photos/chertkov-award-list-p467.jpg, photos/chertkov-award-list-p468.jpg.",
        "",
        "0 @S4@ SOUR",
        "1 TITL Память народа: Тарасенко Семён Васильевич, 1915, запись 27834355",
        "1 PUBL https://pamyat-naroda.ru/heroes/podvig-chelovek_nagrazhdenie27834355/",
        "1 NOTE Приказ 677/н от 18.06.1945.",
        "",
        "0 @S5@ SOUR",
        "1 TITL ЦАМО, ф. 33, оп. 686196, д. 6113: наградное дело Тарасенко С. В.",
        "1 NOTE Сканы: photos/tarasenko-award-list-p1.jpg, photos/tarasenko-award-list-p2.jpg.",
        "",
        "0 @S6@ SOUR",
        "1 TITL Дополнение к семейным сведениям, 06.11.2026",
        "1 NOTE Уточнение отчества Лидии, дата Валентины, рассказ о Калининграде 1954 года.",
        "",
    ]

    person_sources = {
        "P-0023": ["@S2@", "@S3@"],
        "P-0032": ["@S4@", "@S5@"],
        "P-0007": ["@S6@"],
        "P-0011": ["@S6@"],
    }
    person_media = {
        "P-0023": "photos/chertkov-award-list-p467.jpg",
        "P-0032": "photos/tarasenko-award-list-p1.jpg",
    }

    for row in persons:
        given, surname = split_name(row["preferred_label"])
        lines.append(f"0 {xref[row['person_id']]} INDI")
        lines.append(f"1 NAME {given} /{surname}/" if surname else f"1 NAME {given}")
        if surname:
            lines.append(f"2 SURN {surname}")
        if given:
            lines.append(f"2 GIVN {given}")
        lines.append(f"1 SEX {sex_of(row['preferred_label'])}")
        birth = gedcom_date(row["birth_estimate"])
        if birth:
            lines.append("1 BIRT")
            lines.append(f"2 DATE {birth}")
            if row["places"]:
                lines.append(f"2 PLAC {row['places'].split(';')[0].strip()}")
        death = gedcom_date(row["death_estimate"])
        if death:
            lines.append("1 DEAT")
            lines.append(f"2 DATE {death}")
        if row["occupation_or_status"]:
            lines.append(f"1 OCCU {row['occupation_or_status']}")
        if row["person_id"] in child_to_family:
            for family_id in child_to_family[row["person_id"]]:
                lines.append(f"1 FAMC {family_id}")
        for family_id in spouse_families.get(row["person_id"], []):
            lines.append(f"1 FAMS {family_id}")
        lines.append("1 SOUR @S1@")
        for source_id in person_sources.get(row["person_id"], []):
            lines.append(f"1 SOUR {source_id}")
        if row["person_id"] in person_media:
            lines.append("1 OBJE")
            lines.append(f"2 FILE {person_media[row['person_id']]}")
            lines.append("2 FORM jpg")
            lines.append("2 TITL Скан архивного документа")
        note = f"Статус: {row['candidate_status']}. {row['notes']}".strip()
        lines.append(f"1 NOTE {note}")
        lines.append("")

    for family in families:
        lines.append(f"0 {family['id']} FAM")
        for parent_id in family["parents"]:  # type: ignore[union-attr]
            role = "HUSB" if sex_of(person_by_id[parent_id]["preferred_label"]) == "M" else "WIFE"
            lines.append(f"1 {role} {xref[parent_id]}")
        for child_id in family["children"]:  # type: ignore[union-attr]
            lines.append(f"1 CHIL {xref[child_id]}")
        lines.append("1 SOUR @S1@")
        lines.append("")

    lines.append("0 TRLR")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Записано: {OUT}")
    print(f"Персон: {len(persons)}, семей: {len(families)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
