
import json
import time
import re
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path


SOURCE = Path("apteki.json")
OUTPUT = Path("apteki_coordinates_candidates.json")

# Nominatim требует идентифицировать приложение.
USER_AGENT = "24lek-pharmacy-coordinate-checker/1.0"

# Интервал между запросами к публичному Nominatim.
REQUEST_DELAY = 1.1

# Районы Красноярска для уточнения поиска.
DISTRICTS = {
    "Ленинский": "Ленинский район",
    "Советский": "Советский район",
    "Центральный": "Центральный район",
    "Кировский": "Кировский район",
    "Свердловский": "Свердловский район",
    "Октябрьский": "Октябрьский район",
    "Железнодорожный": "Железнодорожный район",
}


def is_website(address):
    """Проверяет, не является ли адрес сайта интернет-аптеки."""
    address = str(address or "").strip().lower()

    return (
        address.startswith("www.")
        or address.startswith("http://")
        or address.startswith("https://")
        or re.search(r"\.(ru|рф|com|net|org)(/|$)", address) is not None
    )


def build_query(pharmacy):
    """Формирует поисковый запрос для Nominatim."""
    address = str(pharmacy.get("address", "")).strip()
    city = str(pharmacy.get("city", "Красноярск")).strip()
    district = str(pharmacy.get("district", "")).strip()

    parts = [address]

    if district in DISTRICTS:
        parts.append(DISTRICTS[district])

    parts.extend([city, "Россия"])

    return ", ".join(part for part in parts if part)


def search_nominatim(query):
    """Ищет адрес в OpenStreetMap Nominatim."""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "jsonv2",
        "limit": 5,
        "addressdetails": 1,
        "countrycodes": "ru",
    })

    url = f"https://nominatim.openstreetmap.org/search?{params}"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "ru",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))

        return data

    except urllib.error.HTTPError as error:
        return {
            "error": f"HTTP {error.code}: {error.reason}"
        }

    except Exception as error:
        return {
            "error": str(error)
        }


def main():
    if not SOURCE.exists():
        print(f"Файл не найден: {SOURCE}")
        return

    with SOURCE.open("r", encoding="utf-8") as file:
        pharmacies = json.load(file)

    if not isinstance(pharmacies, list):
        print("Ошибка: apteki.json должен содержать JSON-список.")
        return

    results = []
    skipped_websites = 0
    skipped_existing = 0

    targets = []

    for pharmacy in pharmacies:
        if not isinstance(pharmacy, dict):
            continue

        lat = pharmacy.get("lat")
        lon = pharmacy.get("lon")

        if lat is not None and lon is not None:
            skipped_existing += 1
            continue

        address = pharmacy.get("address", "")

        if not address or is_website(address):
            skipped_websites += 1
            continue

        targets.append(pharmacy)

    print(f"Всего аптек: {len(pharmacies)}")
    print(f"Нужно проверить адресов: {len(targets)}")
    print(f"Пропущено сайтов и пустых адресов: {skipped_websites}")
    print(f"Уже есть координаты: {skipped_existing}")
    print()

    for index, pharmacy in enumerate(targets, start=1):
        query = build_query(pharmacy)

        print(
            f"[{index}/{len(targets)}] "
            f"ID {pharmacy.get('id')}: "
            f"{pharmacy.get('address')}"
        )

        candidates = search_nominatim(query)

        result = {
            "id": pharmacy.get("id"),
            "name": pharmacy.get("name"),
            "address": pharmacy.get("address"),
            "district": pharmacy.get("district"),
            "city": pharmacy.get("city"),
            "query": query,
            "candidates": [],
            "status": "not_found",
        }

        if isinstance(candidates, dict) and "error" in candidates:
            result["status"] = "request_error"
            result["error"] = candidates["error"]

        elif candidates:
            result["status"] = "candidates_found"

            for candidate in candidates:
                result["candidates"].append({
                    "lat": candidate.get("lat"),
                    "lon": candidate.get("lon"),
                    "display_name": candidate.get("display_name"),
                    "type": candidate.get("type"),
                    "class": candidate.get("class"),
                    "importance": candidate.get("importance"),
                })

            print(f"  Найдено вариантов: {len(candidates)}")

        else:
            print("  Адрес не найден")

        results.append(result)

        # Соблюдаем ограничение публичного сервиса.
        if index < len(targets):
            time.sleep(REQUEST_DELAY)

    with OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2,
        )

    found = sum(
        1 for item in results
        if item["status"] == "candidates_found"
    )

    not_found = sum(
        1 for item in results
        if item["status"] == "not_found"
    )

    errors = sum(
        1 for item in results
        if item["status"] == "request_error"
    )

    print()
    print("Поиск завершён.")
    print(f"Проверено адресов: {len(targets)}")
    print(f"Найдены варианты: {found}")
    print(f"Не найдены: {not_found}")
    print(f"Ошибки запросов: {errors}")
    print(f"Результат: {OUTPUT}")
    print()
    print("Исходный apteki.json не изменялся.")


if __name__ == "__main__":
    main()
