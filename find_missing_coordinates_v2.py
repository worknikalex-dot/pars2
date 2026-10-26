
import json
import re
import time
import itertools
import requests

from pathlib import Path
from urllib.parse import urlencode


# ============================================================
# НАСТРОЙКИ
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "apteki.json"
OUTPUT_FILE = BASE_DIR / "apteki_coordinates_candidates_v2.json"

CITY = "Красноярск"
COUNTRY = "Россия"

# Nominatim требует не отправлять запросы чаще одного раза в секунду.
REQUEST_DELAY = 1.2

# Максимальное число результатов на один запрос.
LIMIT = 10

# Укажите здесь идентификатор своего приложения и контакт,
# если хотите использовать контактный User-Agent.
USER_AGENT = (
    "KrasnoyarskPharmacyCoordinateSearch/2.0 "
    "(Python requests)"
)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def normalize_spaces(text):
    """Убирает лишние пробелы."""
    return re.sub(r"\s+", " ", str(text)).strip()


def is_website(address):
    """Проверяет, не является ли адрес сайтом."""
    if not address:
        return True

    value = str(address).strip().lower()

    prefixes = (
        "www.",
        "http://",
        "https://",
    )

    if value.startswith(prefixes):
        return True

    if re.search(
        r"\.(ru|com|рф|net|org|рф)(/|$)",
        value
    ):
        return True

    return False


def normalize_street(street):
    """Нормализует отдельное название улицы."""
    value = normalize_spaces(street)

    value = value.replace("ё", "е").replace("Ё", "Е")

    # Исправление известной опечатки.
    value = value.replace(
        "Железнякака",
        "Железняка"
    )

    value = value.replace(
        "железнякака",
        "железняка"
    )

    # Убираем распространённые сокращения в начале.
    value = re.sub(
        r"^(ул\.?|улица)\s*",
        "",
        value,
        flags=re.IGNORECASE
    )

    value = re.sub(
        r"^(пр\.?|просп\.?|проспект)\s*",
        "",
        value,
        flags=re.IGNORECASE
    )

    value = re.sub(
        r"^(пер\.?|переулок)\s*",
        "",
        value,
        flags=re.IGNORECASE
    )

    return normalize_spaces(value)


def extract_house_number(address):
    """
    Пытается отделить номер дома от названия улицы.

    Сохраняет варианты вроде:
    1/39, 31А, 46ст1, 74д.
    """
    value = normalize_spaces(address)

    # Убираем начальные сокращения.
    value = re.sub(
        r"^(ул\.?|улица|пр\.?|просп\.?|проспект|пер\.?|переулок)\s*",
        "",
        value,
        flags=re.IGNORECASE
    )

    # Номер дома обычно находится в конце строки.
    match = re.search(
        r"(\d+\s*(?:/\s*\d+)?\s*(?:[А-Яа-яA-Za-z])?"
        r"(?:\s*(?:ст|стр)\s*\d+)?"
        r"(?:\s*к\s*\d+)?"
        r")\s*$",
        value,
        flags=re.IGNORECASE
    )

    if not match:
        return value, None

    house = normalize_spaces(match.group(1))
    street = normalize_spaces(value[:match.start()])

    if not street:
        return value, None

    return street, house


def make_street_variants(street):
    """Создаёт варианты названия улицы."""
    original = normalize_spaces(street)

    variants = []

    def add(value):
        value = normalize_spaces(value)
        if value and value not in variants:
            variants.append(value)

    add(original)

    cleaned = normalize_street(original)
    add(cleaned)

    if cleaned:
        add("улица " + cleaned)
        add("проспект " + cleaned)
        add("переулок " + cleaned)

    # Варианты е/ё.
    for value in list(variants):
        add(value.replace("е", "ё"))
        add(value.replace("ё", "е"))

    return variants


def make_house_variants(house):
    """Создаёт варианты записи номера дома."""
    if not house:
        return []

    original = normalize_spaces(house)

    variants = []

    def add(value):
        value = normalize_spaces(value)
        if value and value not in variants:
            variants.append(value)

    add(original)

    # Убираем пробелы вокруг дроби.
    add(re.sub(r"\s*/\s*", "/", original))

    # Примеры: 31А и 31 А.
    add(re.sub(r"(\d+)\s*([А-Яа-яA-Za-z])", r"\1 \2", original))

    return variants


def build_queries(address):
    """
    Формирует разные поисковые запросы:
    - исходный адрес;
    - нормализованный полный адрес;
    - улица + номер дома;
    - варианты названия улицы;
    - варианты номера дома.
    """
    address = normalize_spaces(address)

    street, house = extract_house_number(address)

    street_variants = make_street_variants(street)
    house_variants = make_house_variants(house)

    queries = []

    def add(query, query_type):
        query = normalize_spaces(query)

        if not query:
            return

        item = {
            "query": query,
            "query_type": query_type
        }

        if item not in queries:
            queries.append(item)

    # Исходная строка.
    add(
        f"{address}, {CITY}, {COUNTRY}",
        "original"
    )

    # Нормализованное название улицы.
    for street_variant in street_variants:
        add(
            f"{street_variant}, {CITY}, {COUNTRY}",
            "street_only"
        )

    # Полный адрес: улица + номер дома.
    if house:
        for street_variant, house_variant in itertools.product(
            street_variants,
            house_variants
        ):
            add(
                f"{street_variant}, {house_variant}, {CITY}, {COUNTRY}",
                "street_and_house"
            )

    return queries


# ============================================================
# ЗАПРОСЫ К NOMINATIM
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept-Language": "ru"
})


def search_nominatim(query):
    """Выполняет один запрос к Nominatim."""
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": LIMIT,
        "countrycodes": "ru"
    }

    try:
        response = session.get(
            NOMINATIM_URL,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        return response.json(), None

    except requests.RequestException as error:
        return [], str(error)

    except ValueError as error:
        return [], f"Ошибка разбора JSON: {error}"


# ============================================================
# ОБРАБОТКА АПТЕК
# ============================================================

def has_coordinates(pharmacy):
    """Проверяет наличие обеих координат."""
    return (
        pharmacy.get("lat") is not None
        and pharmacy.get("lon") is not None
    )


def make_candidate(result, query_info, pharmacy):
    """Преобразует результат Nominatim в запись-кандидат."""
    address_data = result.get("address", {})

    display_name = result.get("display_name", "")

    house_number = address_data.get("house_number")

    # Street-only запрос или результат без номера дома
    # не должен считаться точным совпадением.
    exact_house = bool(house_number)

    query_type = query_info["query_type"]

    if query_type == "street_only":
        match_level = "street_only"
    elif exact_house:
        match_level = "has_house_number"
    else:
        match_level = "no_house_number"

    return {
        "query": query_info["query"],
        "query_type": query_type,
        "match_level": match_level,
        "has_house_number": exact_house,

        "lat": result.get("lat"),
        "lon": result.get("lon"),

        "display_name": display_name,

        "osm_type": result.get("osm_type"),
        "osm_id": result.get("osm_id"),
        "category": result.get("category"),
        "type": result.get("type"),

        "result_address": address_data,

        "returned_house_number": house_number,
        "returned_road": (
            address_data.get("road")
            or address_data.get("pedestrian")
            or address_data.get("residential")
        ),

        "pharmacy_id": pharmacy.get("id"),
        "pharmacy_name": pharmacy.get("name"),
        "source_address": pharmacy.get("address")
    }


def main():
    if not INPUT_FILE.exists():
        print(f"Не найден файл: {INPUT_FILE}")
        return

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        pharmacies = json.load(file)

    if not isinstance(pharmacies, list):
        print("Ошибка: apteki.json должен содержать список аптек.")
        return

    results = []

    total = len(pharmacies)

    skipped_coordinates = 0
    skipped_websites = 0
    processed = 0

    total_requests = 0
    successful_requests = 0
    failed_requests = 0

    print(f"Всего аптек: {total}")

    for index, pharmacy in enumerate(pharmacies, start=1):

        if has_coordinates(pharmacy):
            skipped_coordinates += 1
            continue

        address = pharmacy.get("address")

        if is_website(address):
            skipped_websites += 1
            continue

        processed += 1

        print()
        print(
            f"[{index}/{total}] "
            f"ID {pharmacy.get('id')} — "
            f"{pharmacy.get('name')}"
        )
        print(f"Адрес: {address}")

        queries = build_queries(address)

        pharmacy_result = {
            "id": pharmacy.get("id"),
            "name": pharmacy.get("name"),
            "address": address,
            "district": pharmacy.get("district"),
            "city": pharmacy.get("city", CITY),

            "search_queries": queries,
            "candidates": [],
            "errors": []
        }

        for query_info in queries:
            query = query_info["query"]

            print(f"  Поиск: {query}")

            found, error = search_nominatim(query)

            total_requests += 1

            if error:
                failed_requests += 1

                pharmacy_result["errors"].append({
                    "query": query,
                    "error": error
                })

                print(f"    Ошибка: {error}")

            else:
                successful_requests += 1

                if found:
                    print(
                        f"    Найдено вариантов: {len(found)}"
                    )

                    for item in found:
                        candidate = make_candidate(
                            item,
                            query_info,
                            pharmacy
                        )

                        pharmacy_result["candidates"].append(
                            candidate
                        )

                else:
                    print("    Ничего не найдено")

            # Соблюдаем ограничение Nominatim.
            time.sleep(REQUEST_DELAY)

        results.append(pharmacy_result)

        print(
            "  Всего кандидатов для аптеки: "
            f"{len(pharmacy_result['candidates'])}"
        )

    output = {
        "city": CITY,
        "source": "OpenStreetMap Nominatim",
        "input_file": INPUT_FILE.name,

        "statistics": {
            "total_pharmacies": total,
            "processed": processed,
            "skipped_with_coordinates": skipped_coordinates,
            "skipped_websites_or_empty": skipped_websites,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "pharmacies_with_candidates": sum(
                1 for item in results if item["candidates"]
            ),
            "pharmacies_without_candidates": sum(
                1 for item in results if not item["candidates"]
            )
        },

        "results": results
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 55)
    print("ПОИСК ЗАВЕРШЁН")
    print("=" * 55)

    print(f"Всего аптек: {total}")
    print(f"Обработано: {processed}")
    print(f"Уже с координатами: {skipped_coordinates}")
    print(f"Пропущено сайтов и пустых адресов: {skipped_websites}")

    print(f"Всего запросов: {total_requests}")
    print(f"Успешных запросов: {successful_requests}")
    print(f"Ошибок запросов: {failed_requests}")

    print(
        "Аптек с кандидатами: "
        f"{output['statistics']['pharmacies_with_candidates']}"
    )

    print(
        "Аптек без кандидатов: "
        f"{output['statistics']['pharmacies_without_candidates']}"
    )

    print()
    print(f"Результаты сохранены в:\n{OUTPUT_FILE}")

    print()
    print("Файл apteki.json не изменялся.")


if __name__ == "__main__":
    main()
