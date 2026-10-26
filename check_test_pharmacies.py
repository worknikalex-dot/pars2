
import json

with open("apteki.json", "r", encoding="utf-8") as f:
    pharmacies = json.load(f)

target_ids = {1091, 439, 539}

for pharmacy in pharmacies:
    if pharmacy.get("id") in target_ids:
        print(
            f"ID: {pharmacy.get('id')} | "
            f"Название: {pharmacy.get('name')} | "
            f"Адрес: {pharmacy.get('address')} | "
            f"Район: {pharmacy.get('district')!r}"
        )

found_ids = {
    pharmacy.get("id")
    for pharmacy in pharmacies
    if pharmacy.get("id") in target_ids
}

print("Не найдены ID:", sorted(target_ids - found_ids))
