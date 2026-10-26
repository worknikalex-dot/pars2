
import json
from pathlib import Path
from collections import Counter

FILE = Path("apteki.json")

with FILE.open("r", encoding="utf-8") as f:
    data = json.load(f)

print("ТИП КОРНЕВОЙ СТРУКТУРЫ:", type(data).__name__)

if isinstance(data, dict):
    print("КЛЮЧИ КОРНЯ:", list(data.keys()))
    pharmacies = None

    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            pharmacies = value
            print("СПИСОК АПТЕК В ПОЛЕ:", key)
            break

    if pharmacies is None:
        pharmacies = [data]

elif isinstance(data, list):
    pharmacies = data
else:
    pharmacies = []

print("КОЛИЧЕСТВО ЗАПИСЕЙ:", len(pharmacies))

if pharmacies and isinstance(pharmacies[0], dict):
    all_keys = Counter()
    for item in pharmacies:
        all_keys.update(item.keys())

    print("\nПОЛЯ И ЧИСЛО ЗАПИСЕЙ С НИМИ:")
    for key, count in all_keys.most_common():
        print(f"{key}: {count}")

    print("\nПРИМЕРЫ ПЕРВЫХ 5 ЗАПИСЕЙ:")
    for item in pharmacies[:5]:
        print(json.dumps(item, ensure_ascii=False))

    print("\nПРИМЕРЫ ПОТЕНЦИАЛЬНЫХ ПОЛЕЙ РАЙОНА:")
    district_words = ("район", "district", "raon")
    for item in pharmacies:
        selected = {
            k: v for k, v in item.items()
            if any(word in k.lower() for word in district_words)
        }
        if selected:
            print(json.dumps(selected, ensure_ascii=False))
