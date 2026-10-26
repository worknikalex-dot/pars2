
import json
from pathlib import Path
from copy import deepcopy


# ---------------------------------------------------------
# Пути к файлам
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FILE = BASE_DIR / "apteki.json"
OUTPUT_FILE = BASE_DIR / "apteki_review.json"


# ---------------------------------------------------------
# Восемь наиболее надёжных адресных кандидатов
#
# Координаты взяты из анализа отчёта
# apteki_candidates_short.txt.
#
# Для большинства записей найдена точка здания,
# а не подтверждённая точка самой аптеки.
# ---------------------------------------------------------

RELIABLE_CANDIDATES = {
    949: {
        "lat": 56.1141500,
        "lon": 92.9175981,
        "review_status": "pharmacy_name_and_address_match",
        "review_comment": (
            "Совпадают название Фармакопейка и адрес "
            "60 лет Образования СССР, 26А. "
            "Найден объект аптеки."
        ),
    },

    1044: {
        "lat": 56.0562279,
        "lon": 92.9614102,
        "review_status": "address_match_pharmacy_type_name_unconfirmed",
        "review_comment": (
            "Найден объект pharmacy по адресу "
            "Металлургов, 8А. Название Адонис "
            "в результате OSM не подтверждено."
        ),
    },

    610: {
        "lat": 56.0276917,
        "lon": 92.9096893,
        "review_status": "building_address_match_pharmacy_not_confirmed",
        "review_comment": (
            "Совпадает адрес Партизана Железняка, 12А. "
            "Координаты здания, расположение самой аптеки "
            "в здании отдельно не подтверждено."
        ),
    },

    735: {
        "lat": 56.0406751,
        "lon": 92.9346641,
        "review_status": "building_address_match_pharmacy_not_confirmed",
        "review_comment": (
            "Совпадает адрес Партизана Железняка, 48Д. "
            "Координаты здания, а не подтверждённой точки аптеки."
        ),
    },

    1140: {
        "lat": 56.0634824,
        "lon": 92.9370427,
        "review_status": "building_address_match_pharmacy_not_confirmed",
        "review_comment": (
            "Совпадает адрес Мате Залки, 12А. "
            "Найдено здание, наличие аптеки в нём "
            "отдельно не подтверждено."
        ),
    },

    208: {
        "lat": 56.1180776,
        "lon": 92.9297239,
        "review_status": "building_address_match_pharmacy_not_confirmed",
        "review_comment": (
            "Совпадает адрес проспект 60 лет Образования СССР, 14. "
            "Найдено здание по точному номеру дома."
        ),
    },

    182: {
        "lat": 56.0554922,
        "lon": 92.9600164,
        "review_status": "building_address_match_pharmacy_not_confirmed",
        "review_comment": (
            "Совпадает адрес проспект Металлургов, 12. "
            "Найдено здание по точному номеру дома."
        ),
    },

    1158: {
        "lat": 56.0577481,
        "lon": 92.9010712,
        "review_status": "building_address_match_pharmacy_not_confirmed",
        "review_comment": (
            "Совпадает адрес Светлогорский переулок, 19А "
            "и Советский район. Найден коммерческий объект "
            "в здании; сама аптека отдельно не подтверждена."
        ),
    },
}


# ---------------------------------------------------------
# Три адреса для дополнительной проверки
#
# Координаты намеренно не добавляются.
# ---------------------------------------------------------

NEEDS_CHECK = {
    1173: (
        "Адрес неоднозначен: в исходной записи "
        "'60 лет СССР 8 8'. Найдены варианты дома №8, "
        "но точное соответствие не подтверждено."
    ),

    1254: (
        "Найден дом 74Д на проспекте имени газеты "
        "Красноярский Рабочий, но район результата "
        "не совпадает с районом исходной записи."
    ),

    725: (
        "Найден дом 7А на улице Новостроек в Солонцах. "
        "Это не соответствует указанному Железнодорожному району."
    ),
}


# ---------------------------------------------------------
# Проверка, является ли запись интернет-аптекой
# ---------------------------------------------------------

def is_online_pharmacy(pharmacy):
    address = str(pharmacy.get("address", "")).strip().lower()
    url = str(pharmacy.get("url", "")).strip().lower()

    website_markers = (
        "www.",
        "http://",
        "https://",
        ".ru",
        ".рф",
        ".com",
    )

    return (
        any(marker in address for marker in website_markers)
        or any(marker in url for marker in website_markers)
        and not address
    )


# ---------------------------------------------------------
# Основная обработка
# ---------------------------------------------------------

def main():
    if not SOURCE_FILE.exists():
        print(f"Ошибка: не найден файл {SOURCE_FILE}")
        return

    try:
        with SOURCE_FILE.open("r", encoding="utf-8") as file:
            source_data = json.load(file)
    except json.JSONDecodeError as error:
        print(f"Ошибка чтения JSON: {error}")
        return

    if not isinstance(source_data, list):
        print(
            "Ошибка: ожидался JSON-массив аптек "
            "в корне файла apteki.json."
        )
        return

    # Копируем исходные данные целиком.
    # Изменения будут выполняться только в этой копии.
    review_data = deepcopy(source_data)

    reliable_count = 0
    check_count = 0
    online_count = 0
    without_coordinates_count = 0

    for pharmacy in review_data:
        pharmacy_id = pharmacy.get("id")

        # Сохраняем исходные координаты в отдельные поля,
        # чтобы было видно, что было в исходном файле.
        pharmacy["original_lat"] = pharmacy.get("lat")
        pharmacy["original_lon"] = pharmacy.get("lon")

        # По умолчанию координаты исходной записи не меняем.
        pharmacy["review_status"] = "not_reviewed"
        pharmacy["review_comment"] = (
            "Координаты кандидата не добавлялись."
        )

        # Интернет-аптеки не геокодируем.
        if is_online_pharmacy(pharmacy):
            pharmacy["review_status"] = "online"
            pharmacy["review_comment"] = (
                "Интернет-аптека. Физический адрес "
                "для геокодирования отсутствует."
            )
            pharmacy["review_lat"] = None
            pharmacy["review_lon"] = None
            online_count += 1
            continue

        # Восемь наиболее надёжных кандидатов.
        if pharmacy_id in RELIABLE_CANDIDATES:
            candidate = RELIABLE_CANDIDATES[pharmacy_id]

            pharmacy["review_lat"] = candidate["lat"]
            pharmacy["review_lon"] = candidate["lon"]
            pharmacy["review_status"] = candidate["review_status"]
            pharmacy["review_comment"] = candidate["review_comment"]

            reliable_count += 1
            continue

        # Три адреса, требующих дополнительной проверки.
        if pharmacy_id in NEEDS_CHECK:
            pharmacy["review_status"] = "needs_manual_check"
            pharmacy["review_comment"] = NEEDS_CHECK[pharmacy_id]
            pharmacy["review_lat"] = None
            pharmacy["review_lon"] = None

            check_count += 1
            continue

        # Все остальные аптеки остаются без новых координат.
        pharmacy["review_lat"] = None
        pharmacy["review_lon"] = None
        pharmacy["review_status"] = "no_reliable_candidate"
        pharmacy["review_comment"] = (
            "Надёжный адресный кандидат не выбран. "
            "Требуется дополнительная проверка."
        )

        without_coordinates_count += 1

    # -----------------------------------------------------
    # Сохраняем отдельный review-файл
    # -----------------------------------------------------

    try:
        with OUTPUT_FILE.open("w", encoding="utf-8") as file:
            json.dump(
                review_data,
                file,
                ensure_ascii=False,
                indent=4,
            )
    except OSError as error:
        print(f"Ошибка сохранения файла: {error}")
        return

    # -----------------------------------------------------
    # Итог
    # -----------------------------------------------------

    print()
    print("=" * 55)
    print("ФАЙЛ ПРОВЕРКИ АПТЕК СОЗДАН")
    print("=" * 55)

    print(f"Всего аптек в исходном файле: {len(source_data)}")
    print(f"Надёжных кандидатов: {reliable_count}")
    print(f"Адресов для дополнительной проверки: {check_count}")
    print(f"Интернет-аптек: {online_count}")
    print(f"Остальных записей без новых координат: {without_coordinates_count}")

    print()
    print(f"Результат: {OUTPUT_FILE}")
    print()
    print("Исходный apteki.json не изменялся.")
    print("Исходные поля аптек сохранены.")
    print("Координаты кандидатов записаны только в review_lat/review_lon.")
    print("=" * 55)


if __name__ == "__main__":
    main()
