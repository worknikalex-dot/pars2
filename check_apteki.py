
import json
import math
from pathlib import Path
from collections import defaultdict

# ============================================================
# НАСТРОЙКИ
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
JSON_FILE = BASE_DIR / "apteki.json"

EXPECTED_TOTAL = 366

INTERNET_PHARMACY_IDS = {
    1105,
    731,
    897,
    1151,
    344,
    813,
}

# Ориентировочная географическая область Красноярска.
# Это диагностические границы, а не точная административная граница.
LAT_MIN = 55.90
LAT_MAX = 56.30
LON_MIN = 92.60
LON_MAX = 93.30

REQUIRED_FIELDS = [
    "id",
    "name",
    "address",
    "city",
]

OPTIONAL_FIELDS = [
    "district",
    "phone",
    "lat",
    "lon",
    "url",
    "geocoded_address",
    "geocode_source",
]


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

errors = []
warnings = []


def error(message):
    errors.append(message)


def warning(message):
    warnings.append(message)


def is_valid_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def is_empty(value):
    return value is None or (
        isinstance(value, str) and not value.strip()
    )


def print_section(title):
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


# ============================================================
# ЗАГРУЗКА JSON
# ============================================================

print_section("АУДИТ ФАЙЛА APTEKI.JSON")

print(f"Файл: {JSON_FILE}")

if not JSON_FILE.exists():
    print("\nОШИБКА: файл apteki.json не найден.")
    raise SystemExit(1)

try:
    with JSON_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

except json.JSONDecodeError as exc:
    print("\nОШИБКА: JSON имеет некорректный синтаксис.")
    print(f"Строка: {exc.lineno}")
    print(f"Столбец: {exc.colno}")
    print(f"Описание: {exc.msg}")
    raise SystemExit(1)

except Exception as exc:
    print(f"\nОШИБКА чтения файла: {exc}")
    raise SystemExit(1)


# ============================================================
# ПРОВЕРКА КОРНЕВОЙ СТРУКТУРЫ
# ============================================================

print_section("1. ПРОВЕРКА СТРУКТУРЫ")

if not isinstance(data, list):
    error("Корневая структура JSON должна быть списком.")

    print("ОШИБКА: корень JSON не является списком.")
    raise SystemExit(1)

print(f"Всего записей: {len(data)}")

if len(data) != EXPECTED_TOTAL:
    warning(
        f"Ожидалось {EXPECTED_TOTAL} записей, "
        f"фактически: {len(data)}."
    )
else:
    print("Количество записей соответствует ожидаемому.")


# ============================================================
# ПРОВЕРКА ЗАПИСЕЙ И ID
# ============================================================

print_section("2. ПРОВЕРКА ID И ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ")

id_positions = defaultdict(list)
valid_records = []
internet_count = 0
physical_count = 0

for index, item in enumerate(data):

    position = index + 1

    if not isinstance(item, dict):
        error(
            f"Запись №{position}: должна быть объектом JSON."
        )
        continue

    valid_records.append((position, item))

    pharmacy_id = item.get("id")

    if (
        not isinstance(pharmacy_id, int)
        or isinstance(pharmacy_id, bool)
    ):
        error(
            f"Запись №{position}: некорректный ID: "
            f"{pharmacy_id!r}"
        )
    else:
        id_positions[pharmacy_id].append(position)

    for field in REQUIRED_FIELDS:

        if field not in item:
            error(
                f"Запись №{position}, ID {pharmacy_id}: "
                f"отсутствует обязательное поле '{field}'."
            )

        elif is_empty(item[field]):
            error(
                f"Запись №{position}, ID {pharmacy_id}: "
                f"пустое обязательное поле '{field}'."
            )

    for field in OPTIONAL_FIELDS:
        if field not in item:
            warning(
                f"Запись №{position}, ID {pharmacy_id}: "
                f"отсутствует необязательное поле '{field}'."
            )

    if pharmacy_id in INTERNET_PHARMACY_IDS:
        internet_count += 1
    else:
        physical_count += 1


# ============================================================
# ДУБЛИКАТЫ ID
# ============================================================

print_section("3. ПРОВЕРКА ДУБЛИКАТОВ ID")

duplicates = {
    pharmacy_id: positions
    for pharmacy_id, positions in id_positions.items()
    if len(positions) > 1
}

if duplicates:
    for pharmacy_id, positions in duplicates.items():
        error(
            f"Дублирующийся ID {pharmacy_id}, "
            f"позиции в JSON: {positions}"
        )
else:
    print("Дубликатов ID не обнаружено.")


# ============================================================
# ПРОВЕРКА КООРДИНАТ
# ============================================================

print_section("4. ПРОВЕРКА КООРДИНАТ")

missing_coordinates = []
invalid_coordinates = []
suspicious_coordinates = []
outside_krasnoyarsk = []

coordinate_groups = defaultdict(list)

valid_coordinate_count = 0

for position, item in valid_records:

    pharmacy_id = item.get("id")
    name = item.get("name", "Без названия")

    lat = item.get("lat")
    lon = item.get("lon")

    is_internet = pharmacy_id in INTERNET_PHARMACY_IDS

    # Интернет-аптеки не требуют координат.
    if is_internet:

        if lat is not None or lon is not None:
            warning(
                f"Интернет-аптека ID {pharmacy_id}: "
                f"координаты заполнены. "
                f"lat={lat!r}, lon={lon!r}"
            )

        continue

    # Физические аптеки должны иметь обе координаты.
    if lat is None and lon is None:

        missing_coordinates.append(
            (pharmacy_id, name, item.get("address"))
        )
        continue

    if lat is None or lon is None:

        invalid_coordinates.append(
            (
                pharmacy_id,
                name,
                f"Одна координата отсутствует: "
                f"lat={lat!r}, lon={lon!r}"
            )
        )
        continue

    if not is_valid_number(lat) or not is_valid_number(lon):

        invalid_coordinates.append(
            (
                pharmacy_id,
                name,
                f"Неверный тип координат: "
                f"lat={lat!r}, lon={lon!r}"
            )
        )
        continue

    if not (-90 <= lat <= 90):

        invalid_coordinates.append(
            (
                pharmacy_id,
                name,
                f"Широта вне диапазона: {lat}"
            )
        )
        continue

    if not (-180 <= lon <= 180):

        invalid_coordinates.append(
            (
                pharmacy_id,
                name,
                f"Долгота вне диапазона: {lon}"
            )
        )
        continue

    valid_coordinate_count += 1

    # Округление используется только для поиска
    # одинаковых координат, исходные значения не меняются.
    coordinate_key = (round(lat, 6), round(lon, 6))

    coordinate_groups[coordinate_key].append(
        (pharmacy_id, name, item.get("address"))
    )

    # Проверка ориентировочных границ Красноярска.
    if not (
        LAT_MIN <= lat <= LAT_MAX
        and LON_MIN <= lon <= LON_MAX
    ):

        outside_krasnoyarsk.append(
            (pharmacy_id, name, lat, lon, item.get("address"))
        )

    # Подозрительные крайние значения.
    if lat == 0 or lon == 0:
        suspicious_coordinates.append(
            (pharmacy_id, name, lat, lon)
        )


# ============================================================
# ОТЧЕТ ПО ПРОПУСКАМ КООРДИНАТ
# ============================================================

print_section("5. ФИЗИЧЕСКИЕ АПТЕКИ БЕЗ КООРДИНАТ")

if missing_coordinates:

    for pharmacy_id, name, address in missing_coordinates:
        error(
            f"ID {pharmacy_id} | {name} | {address}"
        )
else:
    print("У всех физических аптек координаты присутствуют.")


# ============================================================
# ОТЧЕТ ПО НЕКОРРЕКТНЫМ КООРДИНАТАМ
# ============================================================

print_section("6. НЕКОРРЕКТНЫЕ КООРДИНАТЫ")

if invalid_coordinates:

    for pharmacy_id, name, reason in invalid_coordinates:
        error(
            f"ID {pharmacy_id} | {name} | {reason}"
        )
else:
    print("Некорректных координат не обнаружено.")


# ============================================================
# ОТЧЕТ ПО ПОДОЗРИТЕЛЬНЫМ КООРДИНАТАМ
# ============================================================

print_section("7. ПОДОЗРИТЕЛЬНЫЕ КООРДИНАТЫ")

if suspicious_coordinates:

    for pharmacy_id, name, lat, lon in suspicious_coordinates:
        warning(
            f"ID {pharmacy_id} | {name} | "
            f"lat={lat}, lon={lon}"
        )
else:
    print("Нулевых координат не обнаружено.")


# ============================================================
# КООРДИНАТЫ ЗА ПРЕДЕЛАМИ ОРИЕНТИРОВОЧНОГО КРАСНОЯРСКА
# ============================================================

print_section("8. КООРДИНАТЫ ЗА ПРЕДЕЛАМИ ГОРОДА")

if outside_krasnoyarsk:

    for pharmacy_id, name, lat, lon, address in outside_krasnoyarsk:

        warning(
            f"ID {pharmacy_id} | {name} | "
            f"{address} | lat={lat}, lon={lon}"
        )
else:
    print("Все координаты находятся в заданном диапазоне.")


# ============================================================
# ОДИНАКОВЫЕ КООРДИНАТЫ
# ============================================================

print_section("9. ПРОВЕРКА ОДИНАКОВЫХ КООРДИНАТ")

same_coordinates_found = False

for coords, pharmacies in coordinate_groups.items():

    if len(pharmacies) > 1:

        same_coordinates_found = True

        warning(
            f"Одинаковые координаты {coords}:"
        )

        for pharmacy_id, name, address in pharmacies:
            warning(
                f"  ID {pharmacy_id} | {name} | {address}"
            )

if not same_coordinates_found:
    print("Совпадающих координат не обнаружено.")


# ============================================================
# ИТОГОВАЯ СТАТИСТИКА
# ============================================================

print_section("10. ИТОГОВАЯ СТАТИСТИКА")

print(f"Всего записей: {len(data)}")
print(f"Корректных объектов: {len(valid_records)}")
print(f"Физических аптек: {physical_count}")
print(f"Интернет-аптек: {internet_count}")
print(f"Физических аптек с координатами: {valid_coordinate_count}")
print(f"Физических аптек без координат: {len(missing_coordinates)}")
print(f"Записей с некорректными координатами: {len(invalid_coordinates)}")
print(f"Координат вне ориентировочной области: {len(outside_krasnoyarsk)}")
print(f"Ошибок: {len(errors)}")
print(f"Предупреждений: {len(warnings)}")


# ============================================================
# ПОЛНЫЙ СПИСОК ОШИБОК И ПРЕДУПРЕЖДЕНИЙ
# ============================================================

print_section("11. СПИСОК ОШИБОК")

if errors:
    for number, message in enumerate(errors, 1):
        print(f"{number}. {message}")
else:
    print("Ошибок не обнаружено.")


print_section("12. СПИСОК ПРЕДУПРЕЖДЕНИЙ")

if warnings:
    for number, message in enumerate(warnings, 1):
        print(f"{number}. {message}")
else:
    print("Предупреждений нет.")


# ============================================================
# ЗАВЕРШЕНИЕ
# ============================================================

print_section("АУДИТ ЗАВЕРШЕН")

if errors:
    print("РЕЗУЛЬТАТ: обнаружены ошибки, требуется проверка.")
elif warnings:
    print("РЕЗУЛЬТАТ: критических ошибок нет, есть предупреждения.")
else:
    print("РЕЗУЛЬТАТ: ошибок и предупреждений не обнаружено.")

print("\nФайл apteki.json не изменялся.")
