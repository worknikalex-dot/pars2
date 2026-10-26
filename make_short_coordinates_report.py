
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "apteki_coordinates_candidates_v2.json"
OUTPUT_FILE = BASE_DIR / "apteki_candidates_short.txt"

MAX_CANDIDATES = 6


def main():
    if not INPUT_FILE.exists():
        print(f"Не найден файл: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])

    lines = []

    lines.append("КОРОТКИЙ ОТЧЁТ ПО КООРДИНАТАМ АПТЕК")
    lines.append("=" * 60)

    for pharmacy in results:
        lines.append("")
        lines.append("-" * 60)

        lines.append(
            f"ID: {pharmacy.get('id')} | "
            f"Аптека: {pharmacy.get('name')}"
        )

        lines.append(
            f"Адрес: {pharmacy.get('address')}"
        )

        lines.append(
            f"Район: {pharmacy.get('district')}"
        )

        candidates = pharmacy.get("candidates", [])

        lines.append(
            f"Всего кандидатов: {len(candidates)}"
        )

        if not candidates:
            lines.append("Кандидатов нет")
            continue

        # Сначала показываем результаты с номером дома,
        # затем остальные.
        candidates = sorted(
            candidates,
            key=lambda x: (
                not x.get("has_house_number", False),
                x.get("query_type") == "street_only"
            )
        )

        # Убираем дубли с одинаковыми координатами
        # и одинаковым названием объекта.
        unique = []
        seen = set()

        for candidate in candidates:
            key = (
                candidate.get("lat"),
                candidate.get("lon"),
                candidate.get("display_name")
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(candidate)

        for number, candidate in enumerate(
            unique[:MAX_CANDIDATES],
            start=1
        ):
            lines.append("")
            lines.append(f"  Кандидат {number}:")

            lines.append(
                f"    Координаты: "
                f"{candidate.get('lat')}, "
                f"{candidate.get('lon')}"
            )

            lines.append(
                f"    Название: "
                f"{candidate.get('display_name')}"
            )

            lines.append(
                f"    Тип объекта: "
                f"{candidate.get('category')} / "
                f"{candidate.get('type')}"
            )

            lines.append(
                f"    Номер дома в результате: "
                f"{candidate.get('returned_house_number')}"
            )

            lines.append(
                f"    Улица в результате: "
                f"{candidate.get('returned_road')}"
            )

            lines.append(
                f"    Тип поиска: "
                f"{candidate.get('query_type')}"
            )

            lines.append(
                f"    Уровень совпадения: "
                f"{candidate.get('match_level')}"
            )

        if len(unique) > MAX_CANDIDATES:
            lines.append(
                f"  Остальные кандидаты скрыты: "
                f"{len(unique) - MAX_CANDIDATES}"
            )

    report = "\n".join(lines)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)

    print("\n" + "=" * 60)
    print(f"Короткий отчёт сохранён: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
