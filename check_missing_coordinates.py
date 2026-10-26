
import csv
import json
import re
from pathlib import Path
from urllib.parse import quote

INPUT_FILE = Path("apteki.json")
OUTPUT_FILE = Path("missing_coordinates.csv")

WEBSITE_RE = re.compile(
    r"(www\.|https?://|\.ru\b|\.рф\b|\.com\b|\.net\b)",
    re.IGNORECASE,
)


def has_coordinates(pharmacy):
    try:
        lat = float(pharmacy.get("lat"))
        lon = float(pharmacy.get("lon"))
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


def main():
    if not INPUT_FILE.exists():
        print(f"Не найден файл: {INPUT_FILE.resolve()}")
        return

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        pharmacies = json.load(file)

    missing = [
        pharmacy
        for pharmacy in pharmacies
        if not has_coordinates(pharmacy)
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "id",
                "name",
                "address",
                "type",
                "pharmacy_url",
                "osm_search",
                "map_search",
                "geocode_error",
            ],
        )
        writer.writeheader()

        for pharmacy in missing:
            address = str(pharmacy.get("address") or "").strip()
            name = str(pharmacy.get("name") or "").strip()
            is_website = bool(WEBSITE_RE.search(address))

            # Для поиска используем название и адрес, если адрес похож на настоящий.
            if is_website or not address:
                search_text = f"{name}, Красноярск"
                entry_type = "Проверить адрес аптеки"
            else:
                search_text = f"{name}, {address}, Красноярск"
                entry_type = "Проверить адрес здания"

            writer.writerow({
                "id": pharmacy.get("id", ""),
                "name": name,
                "address": address,
                "type": entry_type,
                "pharmacy_url": pharmacy.get("url", ""),
                "osm_search": (
                    "https://www.openstreetmap.org/search?query="
                    + quote(search_text)
                ),
                "map_search": (
                    "https://www.google.com/maps/search/?api=1&query="
                    + quote(search_text)
                ),
                "geocode_error": pharmacy.get("geocode_error", ""),
            })

    print(f"Всего аптек в базе: {len(pharmacies)}")
    print(f"Без координат: {len(missing)}")
    print(f"Список для проверки: {OUTPUT_FILE.resolve()}")
    print("\nАптеки без координат:")

    for pharmacy in missing:
        print(
            f"ID {pharmacy.get('id')} | "
            f"{pharmacy.get('name', '')} | "
            f"{pharmacy.get('address', '')}"
        )


if __name__ == "__main__":
    main()
