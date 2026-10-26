# -*- coding: utf-8 -*-
"""Диагностика поиска интернет-аптек на 24lek.ru.

Не изменяет main.py, lek24_parser.py, products.xlsx или report.xlsx.
Запускать из папки проекта:
    python diagnostika_internet_aptek.py
"""

import json
import time
from collections import Counter
from pathlib import Path

from lek24_parser import search_drug_prices, _make_session

QUERY = "пенталгин 12 таб"
INTERNET_PHARMACIES = {
    1105: "Аптека.ру",
    731: "Аптека Легко",
    897: "Губернскиеаптеки.рф ЗАКАЗАТЬ",
    1151: "Аптека ФАРМЭКОНОМ ЗАКАЗАТЬ на",
    344: "Нейрон",
    813: "ТаблеткиТут",
}
PHARMACIES_FILE = Path("apteki.json")


def normalize_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_pharmacy_names(path):
    """Загружает названия аптек из apteki.json, если формат позволяет."""
    if not path.exists():
        print(f"[Предупреждение] Не найден {path}; названия возьмём из списка ID.")
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception as exc:
        print(f"[Предупреждение] Не удалось прочитать {path}: {exc}")
        return {}

    if isinstance(data, dict):
        records = data.get("list", data.get("pharmacies", data.get("data", [])))
        if isinstance(records, dict):
            records = list(records.values())
    elif isinstance(data, list):
        records = data
    else:
        records = []

    names = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        pharmacy_id = normalize_id(
            item.get("id", item.get("apteka_id", item.get("pharmacy_id")))
        )
        name = item.get("name", item.get("title", item.get("apteka_name")))
        if pharmacy_id is not None and name:
            names[pharmacy_id] = str(name)
    return names


def get_id(item):
    return normalize_id(item.get("apteka_id", item.get("pharmacy_id", item.get("id"))))


def main():
    print("=" * 72)
    print("ДИАГНОСТИКА ИНТЕРНЕТ-АПТЕК НА 24LEK.RU")
    print("=" * 72)
    print(f"Запрос: {QUERY!r}")
    print("Режим: читаем результаты поиска, не создаём и не меняем report.xlsx")
    print("\nЦелевые интернет-аптеки:")
    for pharmacy_id, name in INTERNET_PHARMACIES.items():
        print(f"  ID {pharmacy_id}: {name}")

    pharmacy_names = load_pharmacy_names(PHARMACIES_FILE)
    session = _make_session()
    all_items = []

    # Сначала ищем по всем районам, затем отдельно по Железнодорожному,
    # где ранее подтверждались цены трёх ближайших физических аптек.
    for raon_id, district_name in ((0, "все районы"), (1, "Железнодорожный")):
        print(f"\n{'-' * 72}\nПоиск: {district_name} (raon={raon_id})")
        try:
            items = search_drug_prices(
                QUERY,
                needed_apteka_ids=None,
                session=session,
                raon_id=raon_id,
            )
        except Exception as exc:
            print(f"[ОШИБКА] Поиск завершился исключением: {type(exc).__name__}: {exc}")
            continue

        if not items:
            print("Парсер не вернул карточек для этого поиска.")
            continue

        print(f"Парсер вернул карточек: {len(items)}")
        all_items.extend(items)
        counts = Counter(get_id(item) for item in items)
        print("Количество карточек по целевым ID:")
        for pharmacy_id, name in INTERNET_PHARMACIES.items():
            print(f"  ID {pharmacy_id} ({name}): {counts.get(pharmacy_id, 0)}")

        print("\nКарточки целевых интернет-аптек:")
        found_target = False
        for item in items:
            pharmacy_id = get_id(item)
            if pharmacy_id not in INTERNET_PHARMACIES:
                continue
            found_target = True
            product_name = item.get("name", "(название товара не извлечено)")
            price = item.get("price", "(цена не извлечена)")
            pharmacy_name = pharmacy_names.get(pharmacy_id, INTERNET_PHARMACIES[pharmacy_id])
            print(f"  Аптека: {pharmacy_name} [ID {pharmacy_id}]")
            print(f"  Товар:  {product_name}")
            print(f"  Цена:   {price}")
            print()
        if not found_target:
            print("  Карточек с шестью заданными ID в результатах нет.")

        print("Карточки с названием товара, содержащим «пенталгин»:")
        matching_names = [
            item for item in items
            if "пенталгин" in str(item.get("name", "")).lower()
        ]
        if not matching_names:
            print("  Не найдено карточек, в названии которых извлечённого товара есть «пенталгин».")
        else:
            for item in matching_names[:30]:
                pharmacy_id = get_id(item)
                pharmacy_name = pharmacy_names.get(
                    pharmacy_id,
                    INTERNET_PHARMACIES.get(pharmacy_id, "название аптеки отсутствует в apteki.json"),
                )
                print(
                    f"  ID {pharmacy_id} | {pharmacy_name} | "
                    f"{item.get('price')} | {item.get('name')}"
                )
            if len(matching_names) > 30:
                print(f"  ... и ещё {len(matching_names) - 30} карточек")

        time.sleep(0.5)

    # Сводка по двум поискам: одинаковые карточки могут встретиться дважды.
    print(f"\n{'=' * 72}\nИТОГОВАЯ СВОДКА")
    unique = {}
    for item in all_items:
        key = (
            get_id(item),
            str(item.get("name", "")),
            str(item.get("price", "")),
        )
        unique[key] = item

    target_counts = Counter(key[0] for key in unique if key[0] in INTERNET_PHARMACIES)
    print(f"Всего уникальных карточек, возвращённых парсером: {len(unique)}")
    for pharmacy_id, name in INTERNET_PHARMACIES.items():
        print(f"  ID {pharmacy_id} — {name}: {target_counts.get(pharmacy_id, 0)} карточек")

    if not any(target_counts.values()):
        print(
            "\nВывод: текущий парсер не вернул карточек ни для одного из шести ID. "
            "Это ещё не доказывает отсутствие товаров на сайте; нужно проверить "
            "сырой ответ action.php и структуру HTML карточек."
        )
    else:
        print(
            "\nВывод: хотя бы для одной интернет-аптеки карточки найдены. "
            "Сравните ID, названия товаров и цены выше с тем, что попадает в отчёт."
        )

    print("\nДиагностика завершена. Существующие файлы проекта не изменялись.")


if __name__ == "__main__":
    main()
