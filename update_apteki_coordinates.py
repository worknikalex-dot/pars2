
import json
from pathlib import Path


# Файл apteki.json находится рядом со скриптом
FILE_PATH = Path(__file__).resolve().parent / "apteki.json"


# Координаты подтверждённых аптек: ID -> (широта, долгота)
COORDINATES = {
    # Ранее подтверждённые 8 аптек
    182: (56.0554922, 92.9600164),
    208: (56.1180776, 92.9297239),
    610: (56.0276917, 92.9096893),
    735: (56.0406751, 92.9346641),
    949: (56.1141500, 92.9175981),
    1044: (56.0562279, 92.9614102),
    1140: (56.0634824, 92.9370427),
    1158: (56.0577481, 92.9010712),

    # Аптеки, проверенные вручную
    1173: (56.119223, 92.934408),
    979: (56.015017, 92.856138),
    132: (55.991752, 92.910262),
    1137: (55.989994, 92.987180),
    771: (55.991284, 92.939295),
    520: (56.011057, 92.889430),
    1254: (56.010819, 92.963363),
    1057: (55.994929, 92.953138),
    797: (55.995610, 92.950120),
    861: (56.020289, 92.758355),
    133: (56.022565, 92.796634),
    214: (56.046847, 92.946805),
    1276: (55.985035, 92.865454),
    177: (55.977435, 92.850254),
}


def main():
    if not FILE_PATH.exists():
        print(f"ОШИБКА: файл не найден: {FILE_PATH}")
        return

    try:
        with FILE_PATH.open("r", encoding="utf-8") as file:
            pharmacies = json.load(file)
    except (json.JSONDecodeError, OSError) as error:
        print(f"ОШИБКА чтения файла: {error}")
        return

    if not isinstance(pharmacies, list):
        print("ОШИБКА: корневой элемент JSON должен быть списком аптек.")
        return

    pharmacies_by_id = {}

    for pharmacy in pharmacies:
        if isinstance(pharmacy, dict) and "id" in pharmacy:
            pharmacies_by_id[pharmacy["id"]] = pharmacy

    missing_ids = sorted(set(COORDINATES) - set(pharmacies_by_id))

    if missing_ids:
        print("ОШИБКА: в apteki.json отсутствуют ID:", missing_ids)
        print("Файл не изменён.")
        return

    updated = []

    for pharmacy_id, (lat, lon) in COORDINATES.items():
        pharmacy = pharmacies_by_id[pharmacy_id]

        pharmacy["lat"] = lat
        pharmacy["lon"] = lon

        updated.append(pharmacy_id)

    try:
        with FILE_PATH.open("w", encoding="utf-8") as file:
            json.dump(
                pharmacies,
                file,
                ensure_ascii=False,
                indent=2
            )
            file.write("\n")
    except OSError as error:
        print(f"ОШИБКА записи файла: {error}")
        return

    print("Обновление завершено.")
    print(f"Всего аптек в файле: {len(pharmacies)}")
    print(f"Обновлено аптек: {len(updated)}")
    print("ID аптек:", sorted(updated))
    print("Изменены только поля lat и lon указанных аптек.")
    print("ID 725 не изменялся.")


if __name__ == "__main__":
    main()

