import json
from pathlib import Path

SOURCE = Path("apteki.json")
OUTPUT = Path("apteki_incomplete.txt")

# Поля, которые хотим проверить
REQUIRED_FIELDS = [
    "id",
    "name",
    "address",
    "lat",
    "lon",
    "district",
]

with SOURCE.open("r", encoding="utf-8") as f:
    data = json.load(f)

# Поддерживаем JSON в виде списка или словаря
if isinstance(data, list):
    pharmacies = data
elif isinstance(data, dict):
    pharmacies = [
        value for value in data.values()
        if isinstance(value, dict)
    ]
else:
    raise ValueError("Неизвестная структура apteki.json")

incomplete = []

for pharmacy in pharmacies:
    if not isinstance(pharmacy, dict):
        continue

    missing = []

    for field in REQUIRED_FIELDS:
        value = pharmacy.get(field)

        if value is None or str(value).strip() == "":
            missing.append(field)

    if missing:
        incomplete.append({
            "id": pharmacy.get("id"),
            "name": pharmacy.get("name"),
            "address": pharmacy.get("address"),
            "missing": missing,
            "record": pharmacy,
        })

with OUTPUT.open("w", encoding="utf-8") as f:
    for item in incomplete:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"Всего аптек: {len(pharmacies)}")
print(f"Неполных записей: {len(incomplete)}")
print(f"Результат сохранён в: {OUTPUT}")