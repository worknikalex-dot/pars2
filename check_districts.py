
import json
from collections import Counter

with open("apteki.json", "r", encoding="utf-8") as f:
    pharmacies = json.load(f)

district_counts = Counter(
    (pharmacy.get("district") or "").strip()
    for pharmacy in pharmacies
)

print("РАЙОНЫ В apteki.json:")
for district, count in sorted(district_counts.items()):
    print(f"{district or '[пусто]'}: {count} аптек")

print("\nПРОВЕРКА ТЕСТОВЫХ АПТЕК:")
for pharmacy in pharmacies:
    if pharmacy.get("id") in {1091, 439, 539}:
        print(
            f"{pharmacy['id']} | "
            f"{pharmacy.get('name')} | "
            f"{pharmacy.get('district')}"
        )
