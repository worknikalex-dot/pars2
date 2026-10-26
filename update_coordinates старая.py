
import json
import time
import shutil
from pathlib import Path

import requests

INPUT_FILE = Path("apteki.json")
BACKUP_FILE = Path("apteki_backup.json")
CACHE_FILE = Path("geocode_cache.json")

API_URL = "https://nominatim.openstreetmap.org/search"

# Укажи название своего проекта в User-Agent.
HEADERS = {
    "User-Agent": "KrasnoyarskPharmacyParser/1.0 (local research project)",
    "Accept": "application/json",
}

# Пауза между запросами.
REQUEST_DELAY = 1.5


def load_json(path, default):
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        print(f"Ошибка чтения файла: {path}")
        raise


def save_json(path, data):
    temp_path = path.with_suffix(path.suffix + ".tmp")

    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def make_query(address):
    address = (address or "").strip()

    if not address:
        return ""

    return f"{address}, Красноярск, Красноярский край, Россия"


def find_coordinates(session, address):
    query = make_query(address)

    if not query:
        return None

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
        timeout=30,
    )
    response.raise_for_status()

    results = response.json()

    if not results:
        return None

    # Не принимаем результаты, найденные только по городу.
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

        result_type = result.get("type", "")
        result_class = result.get("class", "")

        # Предпочитаем здания и адресные объекты.
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

    # Если здание не найдено, не записываем координаты улицы
    # или всего города: они могут дать неверное расстояние до аптеки.
    return None


def main():
    if not INPUT_FILE.exists():
        print("Ошибка: не найден файл apteki.json")
        return

    pharmacies = load_json(INPUT_FILE, [])

    if not isinstance(pharmacies, list):
        print("Ошибка: apteki.json должен содержать список аптек.")
        return

    # Кэш нужен, чтобы повторно не искать одинаковые адреса.
    cache = load_json(CACHE_FILE, {})

    if not isinstance(cache, dict):
        print("Ошибка: geocode_cache.json должен содержать объект.")
        return

    if not BACKUP_FILE.exists():
        shutil.copy2(INPUT_FILE, BACKUP_FILE)
        print(f"Резервная копия: {BACKUP_FILE.resolve()}")

    session = requests.Session()
    session.headers.update(HEADERS)

    total = len(pharmacies)
    found = 0
    failed = 0
    requests_made = 0

    print(f"Всего аптек: {total}")
    print("Поиск координат через OpenStreetMap...")
    print("Запросы выполняются с паузой; процесс может занять время.\n")

    try:
        for index, pharmacy in enumerate(pharmacies, start=1):
            if pharmacy.get("lat") is not None and pharmacy.get("lon") is not None:
                found += 1
                continue

            address = pharmacy.get("address", "")
            query = make_query(address)

            if not query:
                pharmacy["geocode_error"] = "Нет адреса"
                failed += 1
                continue

            if query in cache:
                result = cache[query]
            else:
                try:
                    # Для длительных массовых запросов Nominatim
                    # ограничивает использование; не запускай несколько
                    # копий скрипта одновременно.
                    if requests_made:
                        time.sleep(REQUEST_DELAY)

                    result = find_coordinates(session, address)
                    requests_made += 1

                    cache[query] = result
                    save_json(CACHE_FILE, cache)

                except requests.HTTPError as error:
                    status = (
                        error.response.status_code
                        if error.response is not None
                        else "неизвестен"
                    )

                    print(f"\nHTTP {status}: {address}")

                    if status in (403, 429):
                        print(
                            "Сервис ограничил запросы. "
                            "Останавливаю скрипт, чтобы не нарушать правила."
                        )
                        save_json(INPUT_FILE, pharmacies)
                        save_json(CACHE_FILE, cache)
                        return

                    pharmacy["geocode_error"] = f"HTTP {status}"
                    failed += 1
                    save_json(INPUT_FILE, pharmacies)
                    continue

                except (requests.RequestException, ValueError, KeyError) as error:
                    pharmacy["geocode_error"] = str(error)
                    failed += 1
                    print(f"[{index}/{total}] Ошибка: {address} — {error}")
                    save_json(INPUT_FILE, pharmacies)
                    continue

            if result:
                pharmacy["lat"] = result["lat"]
                pharmacy["lon"] = result["lon"]
                pharmacy["geocoded_address"] = result["geocoded_address"]
                pharmacy["geocode_source"] = result["geocode_source"]
                pharmacy.pop("geocode_error", None)

                found += 1
                print(
                    f"[{index}/{total}] OK: {address} "
                    f"-> {result['lat']}, {result['lon']}"
                )
            else:
                pharmacy["geocode_error"] = (
                    "Точный адрес здания не найден в OpenStreetMap"
                )
                failed += 1
                print(f"[{index}/{total}] НЕ НАЙДЕН: {address}")

            # Сохраняем прогресс после каждой аптеки.
            save_json(INPUT_FILE, pharmacies)
            save_json(CACHE_FILE, cache)

    except KeyboardInterrupt:
        print("\nОстановка по запросу пользователя.")

    finally:
        save_json(INPUT_FILE, pharmacies)
        save_json(CACHE_FILE, cache)
        session.close()

    print("\nОбработка завершена.")
    print("Аптек с координатами:", found)
    print("Не удалось найти точно:", failed)
    print("Файл аптек:", INPUT_FILE.resolve())
    print("Кэш запросов:", CACHE_FILE.resolve())


if __name__ == "__main__":
    main()
