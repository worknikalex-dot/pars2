import json
import shutil
from pathlib import Path

FILE = Path("apteki.json")
BACKUP = Path("apteki_before_manual_coordinates.json")

VERIFIED = {
    583: {
        "lat": 56.115030,
        "lon": 92.918805,
        "source": "Справочник координат здания, адрес 24А",
    },
    650: {
        "lat": 55.997761,
        "lon": 92.795641,
        "source": "Urbanplaces, адрес Академика Киренского, 17А",
    },
    1101: {
        "lat": 55.993627,
        "lon": 92.773456,
        "source": "Urbanplaces, адрес Академика Киренского, 2И",
    },
    1091: {
        "lat": 56.023524,
        "lon": 92.820215,
        "source": "Предварительно: адрес Красномосковская, 21/1; соответствие 21Ж не подтверждено",
    },
}


def main():
    if not FILE.exists():
        print("Не найден apteki.json")
        return

    with FILE.open("r", encoding="utf-8") as f:
        pharmacies = json.load(f)

    if not BACKUP.exists():
        shutil.copy2(FILE, BACKUP)

    updated = 0

    for pharmacy in pharmacies:
        try:
            pharmacy_id = int(pharmacy.get("id"))
        except (TypeError, ValueError):
            continue

        if pharmacy_id not in VERIFIED:
            continue

        coords = VERIFIED[pharmacy_id]
        pharmacy["lat"] = coords["lat"]
        pharmacy["lon"] = coords["lon"]
        pharmacy["geocode_source"] = coords["source"]
        pharmacy.pop("geocode_error", None)

        updated += 1
        print(
            f"ID {pharmacy_id}: {pharmacy.get('name')} — "
            f"{coords['lat']}, {coords['lon']}"
        )

    if updated:
        temp = FILE.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(pharmacies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp.replace(FILE)

    print(f"Обновлено аптек: {updated}")


if __name__ == "__main__":
    main()
