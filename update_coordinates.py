import json
import time
import shutil
import re
from pathlib import Path

import requests

INPUT_FILE = Path("apteki.json")
BACKUP_FILE = Path("apteki_backup.json")
CACHE_FILE = Path("geocode_cache.json")

API_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "KrasnoyarskPharmacyParser/1.0 (local research project)",
    "Accept": "application/json",
}

REQUEST_DELAY = 1.2
REQUEST_TIMEOUT = (5, 15)

WEBSITE_RE = re.compile(
    r"(www\.|https?://|\.ru\b|\.рф\b|\.com\b|\.net\b)",
    re.IGNORECASE,
)


def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def is_website(address):
    return bool(WEBSITE_RE.search((address or "").strip()))


def normalize_address(address):
    address = (address or "").strip()
    address = re.sub(r"\s+", " ", address)
    address = address.replace("пр-кт.", "проспект ")
    address = address.replace("пр-кт", "проспект ")
    address = address.replace("пр-т", "проспект ")
    address = address.replace("ул.", "улица ")
    address = address.replace("пер.", "переулок ")
    address = address.replace("Крас раб", "Красноярский рабочий")
    address = address.replace("Крас. раб.", "Красноярский рабочий")
    return re.sub(r"\s+", " ", address).strip(" ,")


def make_queries(address):
    address = normalize_address(address)
    if not address or is_website(address):
        return []

    return [
        f"{address}, Красноярск, Красноярский край, Россия",
        f"{address}, Красноярск, Россия",
    ]


def has_coordinates(pharmacy):
    try:
        lat = float(pharmacy.get("lat"))
        lon = float(pharmacy.get("lon"))
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


def search_query(session, query):
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 5,
        "countrycodes": "ru",
        "addressdetails": 1,
    }

    response = session.get(
        API_URL,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    results = response.json()

    for item in results:
        address_data = item.get("address", {})

        city = (
            address_data.get("city")
            or address_data.get("town")
            or address_data.get("municipality")
            or address_data.get("village")
            or ""
        ).lower()

        if city and "красноярск" not in city:
            continue

        result_type = item.get("type", "")
        result_class = item.get("class", "")

        if (
            address_data.get("house_number")
            or result_class == "building"
            or result_type in ("house", "apartments")
        ):
            try:
                return {
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                    "geocoded_address": item.get("display_name", ""),
                    "geocode_source": "OpenStreetMap Nominatim",
                }
            except (KeyError, TypeError, ValueError):
                continue

    return None


def find_coordinates(session, address, cache, last_request):
    queries = make_queries(address)

    for query in queries:
        if query in cache and cache[query] is not None:
            return cache[query]

        elapsed = time.monotonic() - last_request[0]
        if last_request[0] and elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

        result = search_query(session, query)
        last_request[0] = time.monotonic()

        cache[query] = result
        save_json(CACHE_FILE, cache)

        if result is not None:
            return result

    return None


def main():
    if not INPUT_FILE.exists():
        print("Ошибка: не найден apteki.json")
        return

    pharmacies = load_json(INPUT_FILE, [])
    if not isinstance(pharmacies, list):
        print("Ошибка: apteki.json должен содержать список аптек.")
        return

    cache = load_json(CACHE_FILE, {})
    if not isinstance(cache, dict):
        print("Ошибка: geocode_cache.json должен содержать объект.")
        return

    if not BACKUP_FILE.exists():
        shutil.copy2(INPUT_FILE, BACKUP_FILE)
        print(f"Создана резервная копия: {BACKUP_FILE.resolve()}")

    session = requests.Session()
    session.headers.update(HEADERS)

    fixed = 0
    skipped_websites = 0
    failed = 0
    last_request = [0.0]

    pending = [
        (index, pharmacy)
        for index, pharmacy in enumerate(pharmacies, start=1)
        if not has_coordinates(pharmacy)
    ]

    print(f"Всего аптек: {len(pharmacies)}")
    print(f"Без координат: {len(pending)}")
    print("Аптеки с координатами изменяться не будут.\n")

    try:
        for index, pharmacy in pending:
            address = str(pharmacy.get("address") or "").strip()
            name = pharmacy.get("name", "Без названия")

            if not address:
                pharmacy["geocode_error"] = "Нет адреса"
                failed += 1
                print(f"[{index}] ПРОПУСК: пустой адрес")
                save_json(INPUT_FILE, pharmacies)
                continue

            if is_website(address):
                pharmacy["geocode_error"] = (
                    "В поле адреса указан сайт, а не адрес аптеки"
                )
                skipped_websites += 1
                print(f"[{index}] САЙТ: {name} — {address}")
                save_json(INPUT_FILE, pharmacies)
                continue

            print(f"[{index}/{len(pharmacies)}] Ищу: {name} — {address}")

            try:
                result = find_coordinates(
                    session, address, cache, last_request
                )

                if result:
                    pharmacy["lat"] = result["lat"]
                    pharmacy["lon"] = result["lon"]
                    pharmacy["geocoded_address"] = result["geocoded_address"]
                    pharmacy["geocode_source"] = result["geocode_source"]
                    pharmacy.pop("geocode_error", None)
                    fixed += 1

                    print(
                        f"    КАНДИДАТ: {result['lat']}, {result['lon']}\n"
                        f"    {result['geocoded_address']}"
                    )
                else:
                    pharmacy["geocode_error"] = (
                        "Точный адрес здания не найден в OpenStreetMap"
                    )
                    failed += 1
                    print("    Точный адрес здания не найден")

            except requests.HTTPError as error:
                status = (
                    error.response.status_code
                    if error.response is not None
                    else "неизвестен"
                )
                pharmacy["geocode_error"] = f"HTTP {status}"
                failed += 1
                print(f"    Ошибка HTTP {status}")

                if status in (403, 429):
                    print(
                        "Сервис ограничил запросы. "
                        "Обработка остановлена."
                    )
                    break

            except (requests.RequestException, ValueError, KeyError) as error:
                pharmacy["geocode_error"] = str(error)
                failed += 1
                print(f"    Ошибка запроса: {error}")

            save_json(INPUT_FILE, pharmacies)
            save_json(CACHE_FILE, cache)

    except KeyboardInterrupt:
        print("\nОбработка остановлена пользователем.")

    finally:
        save_json(INPUT_FILE, pharmacies)
        save_json(CACHE_FILE, cache)
        session.close()

        remaining = sum(not has_coordinates(p) for p in pharmacies)

    print("\nОбработка завершена.")
    print(f"Добавлено координат: {fixed}")
    print(f"Пропущено сайтов: {skipped_websites}")
    print(f"Не удалось обработать: {failed}")
    print(f"Осталось без координат: {remaining}")
    print(f"База аптек: {INPUT_FILE.resolve()}")
    print(f"Кэш: {CACHE_FILE.resolve()}")


if __name__ == "__main__":
    main()