
import csv
import json
import re
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "apteki.json"
OUTPUT_FILE = BASE_DIR / "photon_results.csv"
CACHE_FILE = BASE_DIR / "photon_cache.json"

PHOTON_URL = "https://photon.komoot.io/api/"
CITY = "Красноярск"
USER_AGENT = "PharmacyCoordinateChecker/1.0 (personal research project)"
REQUEST_DELAY = 1.2

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


def valid_coord(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


def is_website(address):
    text = str(address or "").lower()
    return (
        "www." in text
        or "http://" in text
        or "https://" in text
        or ".ru" in text
        or ".рф" in text
    )


def make_queries(address):
    address = str(address or "").strip()
    address = re.sub(r"\s+", " ", address)
    address = address.replace("пр-кт", "проспект")
    address = address.replace("пр-т", "проспект")
    address = address.replace("пр.", "проспект")
    address = address.replace("ул.", "улица")
    address = address.replace("Крас раб", "Красноярский рабочий")
    address = address.replace("Крас. раб.", "Красноярский рабочий")
    address = address.replace("60 лет образования СССР", "60 лет Образования СССР")

    queries = [
        f"{CITY}, {address}",
        f"{address}, {CITY}, Россия",
    ]

    # Убираем повторы, сохраняя порядок.
    return list(dict.fromkeys(queries))


def photon_search(query):
    try:
        response = SESSION.get(
            PHOTON_URL,
            params={
                "q": query,
                "limit": 5,
                "lat": 56.0106,
                "lon": 92.8526,
                "lang": "ru",
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("features", [])
    except (requests.RequestException, ValueError) as exc:
        print(f"  Ошибка запроса: {exc}")
        return []


def describe_feature(feature):
    props = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    coords = geometry.get("coordinates", [])

    if len(coords) < 2:
        return None

    lon, lat = coords[0], coords[1]
    if not valid_coord(lat, lon):
        return None

    parts = [
        props.get("name"),
        props.get("street"),
        props.get("housenumber"),
        props.get("postcode"),
        props.get("district"),
        props.get("city"),
        props.get("state"),
        props.get("country"),
    ]
    label = ", ".join(str(p) for p in parts if p)

    return {
        "lat": lat,
        "lon": lon,
        "label": label,
        "name": props.get("name", ""),
        "street": props.get("street", ""),
        "housenumber": props.get("housenumber", ""),
        "city": props.get("city", ""),
        "osm_type": props.get("osm_value", ""),
        "osm_id": props.get("osm_id", ""),
        "extent": props.get("extent", ""),
    }


def main():
    if not INPUT_FILE.exists():
        print(f"Не найден файл: {INPUT_FILE}")
        return

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        pharmacies = json.load(f)

    if CACHE_FILE.exists():
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            cache = json.load(f)
    else:
        cache = {}

    missing = []
    for pharmacy in pharmacies:
        if valid_coord(pharmacy.get("lat"), pharmacy.get("lon")):
            continue

        address = str(pharmacy.get("address") or "").strip()
        if not address or is_website(address):
            continue

        missing.append(pharmacy)

    print(f"Всего аптек в базе: {len(pharmacies)}")
    print(f"Адресов без координат для проверки: {len(missing)}")
    print("Запросы идут с паузой, результаты сохраняются отдельно.\n")

    rows = []

    for index, pharmacy in enumerate(missing, start=1):
        pharmacy_id = pharmacy.get("id", "")
        name = pharmacy.get("name", "")
        address = pharmacy.get("address", "")
        cache_key = f"{pharmacy_id}|{address}"

        print(f"[{index}/{len(missing)}] ID {pharmacy_id}: {name} — {address}")

        if cache_key in cache:
            candidates = cache[cache_key]
            print("  Загружено из кэша")
        else:
            candidates = []
            for query_index, query in enumerate(make_queries(address)):
                features = photon_search(query)
                for feature in features:
                    item = describe_feature(feature)
                    if item:
                        item["query"] = query
                        candidates.append(item)

                # Ограничиваем частоту запросов к публичному серверу.
                if query_index < len(make_queries(address)) - 1:
                    time.sleep(REQUEST_DELAY)

            cache[cache_key] = candidates
            CACHE_FILE.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        if not candidates:
            rows.append({
                "id": pharmacy_id,
                "name": name,
                "address": address,
                "candidate_number": "",
                "lat": "",
                "lon": "",
                "result_address": "",
                "street": "",
                "house_number": "",
                "city": "",
                "osm_type": "",
                "osm_id": "",
                "query": "",
                "osm_map": "",
                "status": "Не найдено",
            })
            print("  Кандидаты не найдены")
            continue

        for candidate_number, item in enumerate(candidates, start=1):
            osm_id = item.get("osm_id", "")
            osm_type = item.get("osm_type", "")
            osm_map = (
                f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
                if osm_type and osm_id
                else f"https://www.openstreetmap.org/?mlat={item['lat']}&mlon={item['lon']}#map=18/{item['lat']}/{item['lon']}"
            )

            rows.append({
                "id": pharmacy_id,
                "name": name,
                "address": address,
                "candidate_number": candidate_number,
                "lat": item["lat"],
                "lon": item["lon"],
                "result_address": item["label"],
                "street": item["street"],
                "house_number": item["housenumber"],
                "city": item["city"],
                "osm_type": item["osm_type"],
                "osm_id": item["osm_id"],
                "query": item.get("query", ""),
                "osm_map": osm_map,
                "status": "Проверить вручную",
            })

            print(
                f"  Вариант {candidate_number}: "
                f"{item['lat']}, {item['lon']} — {item['label']}"
            )

        time.sleep(REQUEST_DELAY)

    columns = [
        "id", "name", "address", "candidate_number",
        "lat", "lon", "result_address", "street",
        "house_number", "city", "osm_type", "osm_id",
        "query", "osm_map", "status",
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    print("\nПроверка завершена.")
    print(f"Результаты: {OUTPUT_FILE}")
    print(f"Кэш запросов: {CACHE_FILE}")
    print("Основной файл apteki.json не изменён.")
    print("Координаты из CSV нужно проверить перед применением.")


if __name__ == "__main__":
    main()
