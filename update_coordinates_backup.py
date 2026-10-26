
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

REQUEST_DELAY = 1.5

# Адреса, которые на самом деле являются сайтами, а не адресами аптек.
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
    """Аккуратно исправляет распространённые сокращения, не меняя номер дома."""
    address = (address or "").strip()
    address = re.sub(r"\s+", " ", address)
    address = address.replace("пр-кт.", "проспект ")
    address = address.replace("пр-кт", "проспект ")
    address = address.replace("пр-т", "проспект ")
    address = address.replace("ул.", "улица ")
    address = address.replace("пер.", "переулок ")
    address = address.replace("Крас раб", "Красноярский рабочий")
    address = address.replace("Крас. раб.", "Красноярский рабочий")
    address = re.sub(r"\s+", " ", address).strip(" ,")
    return address


def make_queries(address):
    """Создаёт несколько вариантов запроса для одного адреса."""
    address = normalize_address(address)

    if not address or is_website(address):
        return []

    return [
        f"{address}, Красноярск, Красноярский край, Россия",
        f"{address}, Красноярск, Россия",
    ]


def find_coordinates(session, address):
    for query in make_queries(address):
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": 5,
            "countrycodes": "ru",
            "addressdetails": 1,
        }

        response = session.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        results = response.json()

        for result in results:
            address_data = result.get("address", {})

            city = (
                address_data.get("city")
                or address_data.get("town")
                or address_data.get("municipality")
                or address_data.get("village")
                or ""
            ).lower()

            if city and "красноярск" not in city:
                continue

            # Не принимаем результаты без признака конкретного здания/дома.
            result_type = result.get("type", "")
            result_class = result.get("class", "")

            if (
                result_class == "building"
                or result_type in ("house", "apartments")
                or address_data.get("house_number")
            ):
                return {
                    "lat": float(result["lat"]),
                    "lon": float(result["lon"]),
                    "geocoded_address": result.get("display_name", ""),
                    "geocode_source": "OpenStreetMap Nominatim",
                }

    return None


def has_coordinates(pharmacy):
    try:
        lat = float(pharmacy.get("lat"))
        lon = float(pharmacy.get("lon"))
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


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
        print(f"Резервная копия создана: {BACKUP_FILE.resolve()}")

    session = requests.Session()
    session.headers.update(HEADERS)

    fixed = 0
    skipped_websites = 0
    failed = 0
    requests_made = 0

    pending = [
        (i, pharmacy)
        for i, pharmacy in enumerate(pharmacies, start=1)
        if not has_coordinates(pharmacy)
    ]

    print(f"Всего аптек: {len(pharmacies)}")
    print(f"Без координат перед запуском: {len(pending)}")
    print("Записи с сайтами будут пропущены.")
    print("Неудачные результаты будут сохранены в кэше.\n")

    try:
        for index, pharmacy in pending:
            address = str(pharmacy.get("address") or "").strip()

            if not address:
                pharmacy["geocode_error"] = "Нет адреса"
                failed += 1
                print(f"[{index}] ПРОПУСК: пустой адрес")
                continue

            if is_website(address):
                pharmacy["geocode_error"] = (
                    "В поле адреса указан сайт, а не адрес аптеки"
                )
                skipped_websites += 1
                print(
                    f"[{index}/{len(pharmacies)}] САЙТ: "
                    f"{pharmacy.get('name')} — {address}"
                )
                continue

            queries = make_queries(address)
            result = None

            for query in queries:
                # Не используем отрицательный кэш как окончательный ответ:
                # None означает, что адрес можно попробовать снова.
                if query in cache and cache[query] is not None:
                    result = cache[query]
                    break

                try:
                    if requests_made:
                        time.sleep(REQUEST_DELAY)

                    result = find_coordinates(session, address)
                    requests_made += 1

                    # Сохраняем как успешный результат, так и неудачу.
                    # Неудачу можно будет повторно проверить при следующем запуске.
                    for q in queries:
                        cache[q] = result

                    save_json(CACHE_FILE, cache)
                    break

                except requests.HTTPError as error:
                    status = (
                        error.response.status_code
                        if error.response is not None
                        else "неизвестен"
                    )
                    print(f"HTTP {status}: {address}")

                    if status in (403, 429):
                        print("Сервис ограничил запросы. Останавливаю поиск.")
                        return

                    pharmacy["geocode_error"] = f"HTTP {status}"
                    failed += 1
                    result = None
                    break

                except (requests.RequestException, ValueError, KeyError) as error:
                    pharmacy["geocode_error"] = str(error)
                    failed += 1
                    print(f"Ошибка: {address} — {error}")
                    result = None
                    break

            if result:
                pharmacy["lat"] = result["lat"]
                pharmacy["lon"] = result["lon"]
                pharmacy["geocoded_address"] = result["geocoded_address"]
                pharmacy["geocode_source"] = result["geocode_source"]
                pharmacy.pop("geocode_error", None)

                fixed += 1
                print(
                    f"[{index}/{len(pharmacies)}] OK: {address} "
                    f"-> {result['lat']}, {result['lon']}"
                )
            elif not pharmacy.get("geocode_error", "").startswith("HTTP"):
                pharmacy["geocode_error"] = (
                    "Точный адрес здания не найден в OpenStreetMap"
                )
                failed += 1
                print(f"[{index}/{len(pharmacies)}] НЕ НАЙДЕН: {address}")

            save_json(INPUT_FILE, pharmacies)
            save_json(CACHE_FILE, cache)

    except KeyboardInterrupt:
        print("\nОстановка по запросу пользователя.")

    finally:
        save_json(INPUT_FILE, pharmacies)
        save_json(CACHE_FILE, cache)
        session.close()

    remaining = sum(not has_coordinates(p) for p in pharmacies)

    print("\nОбработка завершена.")
    print(f"Найдено координат за этот запуск: {fixed}")
    print(f"Пропущено записей с сайтами: {skipped_websites}")
    print(f"Не удалось найти / обработать: {failed}")
    print(f"Осталось аптек без координат: {remaining}")
    print(f"Файл аптек: {INPUT_FILE.resolve()}")
    print(f"Кэш: {CACHE_FILE.resolve()}")


if __name__ == "__main__":
    main()
