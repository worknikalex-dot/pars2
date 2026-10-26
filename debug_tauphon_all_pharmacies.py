
import re
import requests
from bs4 import BeautifulSoup

URL = "https://24lek.ru/action.php"

QUERY = "тауфон 10 мл кап"

TARGET_PHARMACIES = {
    1091: "Аптека Эконом — Красномосковская 21Ж",
    439: "Аптека Здравсити — Свободный 28А",
    539: "Дешевая аптека — Свободный 29",
}

params = {
    "kray": 0,
    "city": 0,
    "query": QUERY,
    "raon": 1,
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

print("Запрос:", QUERY)
print("Район: Железнодорожный (raon=1)")
print()

response = session.get(URL, params=params, timeout=30)

print("HTTP:", response.status_code)
print("URL:", response.url)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

cards = soup.find_all(
    id=lambda value: isinstance(value, str)
    and re.fullmatch(r"article\d+", value, re.IGNORECASE)
)

print("Карточек на первой странице:", len(cards))

found = {}

for card in cards:
    text = card.get_text(" ", strip=True)
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

    spans = card.find_all("span")
    price = None

    # На проверенных карточках цена находится в третьем span.
    if len(spans) >= 3:
        raw_price = spans[2].get_text(" ", strip=True)
        raw_price = raw_price.replace("\xa0", "").replace(" ", "")
        raw_price = raw_price.replace(",", ".")

        if re.fullmatch(r"\d+(?:\.\d{1,2})?", raw_price):
            price = raw_price

    found[pharmacy_id] = {
        "text": text,
        "price": price,
        "card_id": card.get("id"),
    }

print("\nРЕЗУЛЬТАТЫ ПРОВЕРКИ")
print("=" * 70)

for pharmacy_id, pharmacy_name in TARGET_PHARMACIES.items():
    print(f"\nАптека ID {pharmacy_id}: {pharmacy_name}")

    result = found.get(pharmacy_id)

    if result is None:
        print("  Не найдена среди карточек первой страницы.")
        continue

    print("  Карточка:", result["card_id"])
    print("  Цена:", result["price"] if result["price"] else "не извлечена")
    print("  Полный текст:", result["text"])

print("\nПараметры пагинации:")

for script in soup.find_all("script"):
    text = script.string or script.get_text()

    rows_match = re.search(
        r"""num_rows\s*=\s*["'](\d+)["']""",
        text,
    )

    if rows_match:
        print("Всего результатов:", rows_match.group(1))
        break

print("\nПроверка завершена.")
