
import json
from pathlib import Path
from copy import deepcopy


# =========================================================
# Пути к файлам
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FILE = BASE_DIR / "apteki.json"
OUTPUT_FILE = BASE_DIR / "apteki_review_verified.json"


# =========================================================
# Подтверждённые кандидаты
#
# Координаты берутся из ранее подготовленного отчёта
# apteki_coordinates_candidates_v2.json.
#
# Эти координаты записываются только в review_lat/review_lon.
# Исходные lat/lon не изменяются.
# =========================================================

VERIFIED_CANDIDATES = {
    949: {
        "lat": 56.1141500,
        "lon": 92.9175981,
        "status": "verified_pharmacy_name_and_address",
        "comment": (
            "Подтверждены название Фармакопейка и адрес "
            "60 лет Образования СССР, 26А. "
            "Найдена запись аптеки по этому адресу."
        ),
        "coordinate_type": "pharmacy_object",
    },

    1044: {
        "lat": 56.0562279,
        "lon": 92.9614102,
        "status": "verified_pharmacy_address",
        "comment": (
            "Подтверждена аптека Адонис по адресу "
            "Металлургов, 8А."
        ),
        "coordinate_type": "pharmacy_object",
    },

    610: {
        "lat": 56.0276917,
        "lon": 92.9096893,
        "status": "verified_address_building",
        "comment": (
            "Подтверждены аптека МЕДИНСТАЛ и адрес "
            "Партизана Железняка, 12А. "
            "Координаты соответствуют зданию, "
            "а не обязательно входу в аптеку."
        ),
        "coordinate_type": "building",
    },

    735: {
        "lat": 56.0406751,
        "lon": 92.9346641,
        "status": "verified_address_building",
        "comment": (
            "Подтверждены Новая Аптека и адрес "
            "Партизана Железняка, 48Д. "
            "Координаты соответствуют зданию."
        ),
        "coordinate_type": "building",
    },

    1140: {
        "lat": 56.0634824,
        "lon": 92.9370427,
        "status": "verified_pharmacy_address",
        "comment": (
            "Подтверждена Дешевая аптека по адресу "
            "Мате Залки, 12А. Координаты соответствуют "
            "адресному объекту."
        ),
        "coordinate_type": "building",
    },

    208: {
        "lat": 56.1180776,
        "lon": 92.9297239,
        "status": "verified_pharmacy_address",
        "comment": (
            "Подтверждены аптека Кырдал и адрес "
            "проспект 60 лет Образования СССР, 14."
        ),
        "coordinate_type": "building",
    },

    1158: {
        "lat": 56.0577481,
        "lon": 92.9010712,
        "status": "verified_pharmacy_address",
        "comment": (
            "Подтверждены аптека Добротека и адрес "
            "Светлогорский переулок, 19А. "
            "Координаты соответствуют зданию, "
            "а не обязательно входу в аптеку."
        ),
        "coordinate_type": "building",
    },
}


# =========================================================
# Кандидат, оставленный на дополнительную проверку
# =========================================================

NEEDS_MANUAL_CHECK = {
    182: {
        "status": "needs_manual_check",
        "comment": (
            "Адрес Металлургов, 12 найден, но наличие "
            "именно Дешевой аптеки по этому адресу "
            "не подтверждено. Координаты кандидата "
            "не переносятся."
        ),
        "candidate_lat": 56.0554922,
        "candidate_lon": 92.9600164,
    },
}


# =========================================================
# ID интернет-аптек
# =========================================================

ONLINE_PHARMACY_IDS = {
    1105,
    731,
    897,
    1151,
    344,
    813,
}


# =========================================================
# Основная обработка
# =========================================================

def main():

    # -----------------------------------------------------
    # Проверяем наличие исходного файла
    # -----------------------------------------------------

    if not SOURCE_FILE.exists():
        print(f"Ошибка: файл не найден: {SOURCE_FILE}")
        return

    try:
        with SOURCE_FILE.open("r", encoding="utf-8") as file:
            source_data = json.load(file)

    except json.JSONDecodeError as error:
        print(f"Ошибка чтения JSON: {error}")
        return

    except OSError as error:
        print(f"Ошибка открытия файла: {error}")
        return

    if not isinstance(source_data, list):
        print(
            "Ошибка: в корне apteki.json "
            "ожидался список аптек."
        )
        return

    # -----------------------------------------------------
    # Создаём независимую копию исходных данных
    # -----------------------------------------------------

    review_data = deepcopy(source_data)

    verified_count = 0
    manual_check_count = 0
    online_count = 0
    other_count = 0

    # -----------------------------------------------------
    # Обрабатываем каждую аптеку
    # -----------------------------------------------------

    for pharmacy in review_data:

        pharmacy_id = pharmacy.get("id")

        # Сохраняем исходные координаты для сравнения.
        # Поля lat и lon не изменяем.
        pharmacy["original_lat"] = pharmacy.get("lat")
        pharmacy["original_lon"] = pharmacy.get("lon")

        # По умолчанию новых координат нет.
        pharmacy["review_lat"] = None
        pharmacy["review_lon"] = None

        pharmacy["review_status"] = "no_reliable_candidate"
        pharmacy["review_comment"] = (
            "Надёжный кандидат не выбран. "
            "Требуется дополнительная проверка."
        )

        pharmacy["review_coordinate_type"] = None

        # -------------------------------------------------
        # Интернет-аптеки
        # -------------------------------------------------

        if pharmacy_id in ONLINE_PHARMACY_IDS:

            pharmacy["review_status"] = "online"
            pharmacy["review_comment"] = (
                "Интернет-аптека. "
                "Физические координаты не добавляются."
            )

            online_count += 1
            continue

        # -------------------------------------------------
        # Подтверждённые кандидаты
        # -------------------------------------------------

        if pharmacy_id in VERIFIED_CANDIDATES:

            candidate = VERIFIED_CANDIDATES[pharmacy_id]

            pharmacy["review_lat"] = candidate["lat"]
            pharmacy["review_lon"] = candidate["lon"]

            pharmacy["review_status"] = candidate["status"]
            pharmacy["review_comment"] = candidate["comment"]

            pharmacy["review_coordinate_type"] = (
                candidate["coordinate_type"]
            )

            verified_count += 1
            continue

        # -------------------------------------------------
        # Кандидат, требующий дополнительной проверки
        # -------------------------------------------------

        if pharmacy_id in NEEDS_MANUAL_CHECK:

            candidate = NEEDS_MANUAL_CHECK[pharmacy_id]

            pharmacy["review_status"] = candidate["status"]
            pharmacy["review_comment"] = candidate["comment"]

            # Координаты кандидата сохраняем отдельно,
            # чтобы они не потерялись и не воспринимались
            # как подтверждённые.
            pharmacy["manual_check_candidate_lat"] = (
                candidate["candidate_lat"]
            )

            pharmacy["manual_check_candidate_lon"] = (
                candidate["candidate_lon"]
            )

            # review_lat и review_lon остаются None.
            manual_check_count += 1
            continue

        # -------------------------------------------------
        # Все остальные записи
        # -------------------------------------------------

        other_count += 1

    # -----------------------------------------------------
    # Сохраняем отдельный файл
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
    # Итоговая статистика
    # -----------------------------------------------------

    print()
    print("=" * 60)
    print("ФАЙЛ ПРОВЕРКИ АПТЕК СОЗДАН")
    print("=" * 60)

    print(f"Всего аптек: {len(review_data)}")
    print(f"Подтверждённых кандидатов: {verified_count}")
    print(f"На дополнительной проверке: {manual_check_count}")
    print(f"Интернет-аптек: {online_count}")
    print(f"Остальных без новых координат: {other_count}")

    print()
    print(f"Результат: {OUTPUT_FILE}")

    print()
    print("Исходный apteki.json не изменялся.")
    print("Исходный apteki_review.json не изменялся.")
    print("Исходные поля lat и lon сохранены.")
    print("Подтверждённые координаты записаны")
    print("только в review_lat и review_lon.")
    print("ID 182 оставлен на дополнительную проверку.")

    print("=" * 60)


if __name__ == "__main__":
    main()
