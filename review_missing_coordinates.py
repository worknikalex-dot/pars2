import csv
import json
import re
import time
from pathlib import Path

import requests

INPUT_FILE = Path("apteki.json")
OUTPUT_FILE = Path("coordinate_candidates.csv")
API_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "KrasnoyarskPharmacyParser/1.0 (local research project)",
    "Accept": "application/json",
}

REQUEST_DELAY = 1.2
TIMEOUT = (5, 15)

WEBSITE_RE = re.compile(
    r"(www\.|https?://|\.ru\b|\.рф\b|\.com\b|\.net\b)",
    re.IGNORECASE,
)


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def has_coordinates(pharmacy):
    try:
        lat = float(pharmacy.get("lat"))
        lon = float(pharmacy.get("lon"))
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


def normalize_address(address):
    address = (address or "").strip()
    address = re.sub(r"\s+", " ", address)
    replacements = {
        "пр-кт.": "проспект",
        "пр-кт": "проспект",
        "пр-т": "проспект",
        "ул.": "улица",
        "пер.": "переулок",
        "Крас раб": "Красноярский рабочий",
        "Крас. раб.": "Красноярский рабочий",
    }
    for old, new in replacements.items():
        address = address.replace(old, new)
    return re.sub(r"\s+", " ", address).strip(" ,")


def make_queries(address):
    address = normalize_address(address)
    if not address or WEBSITE_RE.search(address):
        return []

    return [
        f"{address}, Красноярск, Красноярский край, Россия",
        f"{address}, Красноярск, Россия",
        f"{address}, Красноярск",
    ]


def is_krasnoyarsk(result):
    address = result.get("address", {})
    text = " ".join(
        str(address.get(key, ""))
        for key in (
            "city",
            "town",
            "municipality",
            "county",
            "state",
            "region",
        )
    ).lower()

    display = result.get("display_name", "").lower()

    # В результатах OSM административное деление может быть записано
    # по-разному. Отбрасываем результат только при явном другом городе.
    if any(
        word in text
        for word in ("новосибирск", "омск", "кемерово", "абакан")
    ):
        return False

    return (
        "красноярск" in text
        or "красноярск" in display
    )


def search(session, query):
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
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def main():
    if not INPUT_FILE.exists():
        print("ОШИБКА: не найден apteki.json")
        return

    pharmacies = load_json(INPUT_FILE)
    if not isinstance(pharmacies, list):
        print("ОШИБКА: apteki.json должен содержать список")
        return

    pending = [
        (index, pharmacy)
        for index, pharmacy in enumerate(pharmacies, start=1)
        if not has_coordinates(pharmacy)
    ]

    session = requests.Session()
    session.headers.update(HEADERS)

    rows = []
    request_count = 0

    print(f"Всего аптек: {len(pharmacies)}")
    print(f"Без координат: {len(pending)}")
    print("База apteki.json не будет изменена.\n")

    try:
        for index, pharmacy in pending:
            address = str(pharmacy.get("address") or "").strip()
            name = str(pharmacy.get("name") or "")
            pharmacy_id = pharmacy.get("id", "")

            if not address or WEBSITE_RE.search(address):
                print(f"[{index}] Пропуск: {name} — {address}")
                continue

            print(f"[{index}/{len(pharmacies)}] {name} — {address}")
            queries = make_queries(address)
            seen = set()

            for query in queries:
                try:
                    if request_count:
                        time.sleep(REQUEST_DELAY)

                    results = search(session, query)
                    request_count += 1

                    for result in results:
                        try:
                            lat = float(result["lat"])
                            lon = float(result["lon"])
                        except (KeyError, TypeError, ValueError):
                            continue

                        display = result.get("display_name", "")
                        key = (round(lat, 6), round(lon, 6), display)
                        if key in seen:
                            continue
                        seen.add(key)

                        address_data = result.get("address", {})
                        rows.append({
                            "pharmacy_id": pharmacy_id,
                            "name": name,
                            "original_address": address,
                            "query": query,
                            "lat": lat,
                            "lon": lon,
                            "city_check": (
                                "Красноярск"
                                if is_krasnoyarsk(result)
                                else "ПРОВЕРИТЬ ГОРОД"
                            ),
                            "house_number": address_data.get(
                                "house_number", ""
                            ),
                            "osm_type": result.get("type", ""),
                            "osm_class": result.get("class", ""),
                            "display_name": display,
                            "osm_link": (
                                "https://www.openstreetmap.org/"
                                f"?mlat={lat}&mlon={lon}"
                                f"#map=18/{lat}/{lon}"
                            ),
                            "manual_check": "ПРОВЕРИТЬ ВРУЧНУЮ",
                        })

                    print(f"    Найдено вариантов: {len(results)}")

                except requests.HTTPError as error:
                    status = (
                        error.response.status_code
                        if error.response is not None
                        else "неизвестен"
                    )
                    print(f"    HTTP {status}: {query}")

                    if status in (403, 429):
                        print("Сервис ограничил запросы. Останавливаю поиск.")
                        raise

                except (requests.RequestException, ValueError) as error:
                    print(f"    Ошибка запроса: {error}")

    except KeyboardInterrupt:
        print("\nОстановлено пользователем.")
    finally:
        session.close()

    columns = [
        "pharmacy_id",
        "name",
        "original_address",
        "query",
        "lat",
        "lon",
        "city_check",
        "house_number",
        "osm_type",
        "osm_class",
        "display_name",
        "osm_link",
        "manual_check",
    ]

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print("\nПоиск завершён.")
    print(f"Запросов выполнено: {request_count}")
    print(f"Кандидатов сохранено: {len(rows)}")
    print(f"Результат: {OUTPUT_FILE.resolve()}")
    print("Координаты в apteki.json не изменялись.")


if __name__ == "__main__":
    main()