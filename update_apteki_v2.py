
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

URL = "https://24lek.ru/apteki.php"
OUTPUT_FILE = Path("apteki.json")
DEBUG_FILE = Path("apteki_catalog_debug.html")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    )
}


def clean_text(value):
    """Убирает лишние пробелы из текста."""
    return " ".join(value.split()).strip()


def main():
    print("Загружаю каталог аптек:", URL)

    try:
        response = requests.get(
            URL,
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding

    except requests.RequestException as error:
        print("Не удалось загрузить каталог:", error)
        return

    DEBUG_FILE.write_text(
        response.text,
        encoding="utf-8"
    )

    soup = BeautifulSoup(response.text, "html.parser")

    print("HTTP:", response.status_code)
    print("Размер HTML:", len(response.text))

    # На сайте каталог представлен блоком .table.
    table = soup.find("div", class_="table")

    if table is None:
        print("Не найден блок каталога div.table.")
        print("HTML сохранён в:", DEBUG_FILE.resolve())
        print("Файл apteki.json не изменён.")
        return

    # Заголовки столбцов.
    header = table.find("div", class_="th", recursive=False)

    if header is None:
        print("Не найдена строка заголовков каталога.")
        print("Файл apteki.json не изменён.")
        return

    headers = [
        clean_text(span.get_text(" ", strip=True)).lower()
        for span in header.find_all("span", recursive=False)
    ]

    print("Столбцы:", headers)

    # Определяем индексы столбцов по заголовкам.
    try:
        name_index = headers.index("аптека")
        address_index = headers.index("адрес")
        district_index = headers.index("район")
        phone_index = headers.index("телефон")
        city_index = headers.index("город")
    except ValueError:
        print("Не удалось определить необходимые столбцы.")
        print("Файл apteki.json не изменён.")
        return

    pharmacies = []
    seen_ids = set()
    total_rows = 0
    krasnoyarsk_rows = 0

    for row in table.find_all("div", recursive=False):
        # Пропускаем заголовок.
        if "th" in row.get("class", []):
            continue

        cells = row.find_all("span", recursive=False)

        if len(cells) < len(headers):
            continue

        total_rows += 1

        name = clean_text(
            cells[name_index].get_text(" ", strip=True)
        )
        address = clean_text(
            cells[address_index].get_text(" ", strip=True)
        )
        district = clean_text(
            cells[district_index].get_text(" ", strip=True)
        )
        phone = clean_text(
            cells[phone_index].get_text(" ", strip=True)
        )
        city = clean_text(
            cells[city_index].get_text(" ", strip=True)
        )

        # Фильтруем строго по отдельному столбцу «Город».
        if city.casefold() != "красноярск".casefold():
            continue

        link = cells[address_index].find("a", href=True)

        if link is None:
            continue

        href = link["href"]
        query = parse_qs(urlparse(href).query)
        id_values = query.get("apteka", [])

        if not id_values or not id_values[0].isdigit():
            continue

        pharmacy_id = int(id_values[0])

        if pharmacy_id in seen_ids:
            continue

        krasnoyarsk_rows += 1
        seen_ids.add(pharmacy_id)

        pharmacies.append({
            "id": pharmacy_id,
            "name": name,
            "address": address,
            "district": district,
            "phone": phone,
            "city": city,
            "lat": None,
            "lon": None,
            "url": urljoin(URL, href),
        })

    print("Всего строк каталога:", total_rows)
    print("Строк с городом Красноярск:", krasnoyarsk_rows)

    # Защита существующего файла от случайной пустой выгрузки.
    if not pharmacies:
        print("Аптеки Красноярска не найдены.")
        print("Существующий apteki.json не изменён.")
        print("HTML для проверки:", DEBUG_FILE.resolve())
        return

    pharmacies.sort(
        key=lambda item: (
            item["address"].casefold(),
            item["id"]
        )
    )

    # Сохраняем только после успешного разбора каталога.
    OUTPUT_FILE.write_text(
        json.dumps(
            pharmacies,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print("Готово!")
    print("Сохранено аптек Красноярска:", len(pharmacies))
    print("Файл:", OUTPUT_FILE.resolve())
    print()
    print("Первые 10 записей:")

    for pharmacy in pharmacies[:10]:
        print(
            f'ID: {pharmacy["id"]} | '
            f'{pharmacy["name"]} | '
            f'{pharmacy["address"]} | '
            f'район: {pharmacy["district"]} | '
            f'{pharmacy["phone"]}'
        )

    print()
    print("Координаты пока не заполнены.")
    print("Следующий этап — геокодирование адресов через DaData.")


if __name__ == "__main__":
    main()
