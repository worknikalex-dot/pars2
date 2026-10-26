
import re
import requests
from bs4 import BeautifulSoup

URL = "https://24lek.ru/action.php"

QUERIES = [
    "тауфон 10 мл кап",
    "тауфон 4 10",
    "тауфон 4% 10 мл",
    "тауфон 4 10 мл",
]

TARGET_PHARMACIES = {
    1091: "Аптека Эконом — Красномосковская 21Ж",
    439: "Аптека Здравсити — Свободный 28А",
    539: "Дешевая аптека — Свободный 29",
}

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
})


def extract_price(card):
    """Извлекает цену из третьего span — как в текущем парсере."""
    spans = card.find_all("span")

    if len(spans) < 3:
        return "не определена"

    raw_price = spans[2].get_text(" ", strip=True)
    raw_price = raw_price.replace("\xa0", "").replace(" ", "")
    raw_price = raw_price.replace(",", ".")

    if re.fullmatch(r"\d+(?:\.\d{1,2})?", raw_price):
        return raw_price

    return "не определена"


for query in QUERIES:
    print("\n" + "=" * 85)
    print("ПОИСКОВЫЙ ЗАПРОС:", query)

    try:
        response = session.get(
            URL,
            params={
                "kray": 0,
                "city": 0,
                "query": query,
                "raon": 1,
            },
            timeout=30,
        )

        print("URL:", response.url)
        print("HTTP:", response.status_code)
        response.raise_for_status()

    except requests.RequestException as error:
        print("ОШИБКА ЗАПРОСА:", error)
        continue

    soup = BeautifulSoup(response.text, "html.parser")

    cards = soup.find_all(
        id=lambda value: (
            isinstance(value, str)
            and re.fullmatch(r"article\d+", value, re.IGNORECASE)
        )
    )

    print("Всего карточек на странице:", len(cards))

    found = {pharmacy_id: 0 for pharmacy_id in TARGET_PHARMACIES}

    for card in cards:
        text = card.get_text(" ", strip=True)
        lower_text = text.lower()

        if "тауфон" not in lower_text:
            continue

        links = " ".join(
            a.get("href", "")
            for a in card.find_all("a", href=True)
        )

        id_match = re.search(
            r"open_in_map\s*\(\s*['\"]?(\d+)",
            links,
            re.IGNORECASE,
        )

        if not id_match:
            continue

        pharmacy_id = int(id_match.group(1))

        if pharmacy_id not in TARGET_PHARMACIES:
            continue

        found[pharmacy_id] += 1
        price = extract_price(card)

        # Показываем все найденные карточки Тауфона в целевых аптеках,
        # чтобы не пропустить нужную упаковку из-за формата названия.
        print("\nАптека:", TARGET_PHARMACIES[pharmacy_id])
        print("ID аптеки:", pharmacy_id)
        print("ID карточки:", card.get("id"))
        print("Цена:", price, "руб.")
        print("Название товара:", text)

        if re.search(r"№\s*3\b|N\s*3\b", lower_text):
            print("ПРИМЕЧАНИЕ: в названии обнаружено обозначение упаковки №3.")

    print("\nИТОГ ПО АПТЕКАМ:")
    for pharmacy_id, pharmacy_name in TARGET_PHARMACIES.items():
        print(
            f"ID {pharmacy_id} | {pharmacy_name} | "
            f"карточек Тауфона: {found[pharmacy_id]}"
        )

print("\nДиагностика завершена.")
