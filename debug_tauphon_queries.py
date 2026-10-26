
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://24lek.ru/action.php"

QUERIES = [
    "тауфон 10 мл кап",
    "тауфон 4 10 мл",
    "тауфон 4%",
    "тауфон 10мл",
    "ТАУФОН 4 10 МЛ КАПЛИ ГЛАЗН. ОТИСИФАРМ",
]

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
})

for query in QUERIES:
    print("\n" + "=" * 70)
    print("ЗАПРОС:", query)

    try:
        response = session.get(
            BASE_URL,
            params={
                "kray": 0,
                "city": 0,
                "raon": 0,
                "query": query,
            },
            timeout=30,
        )
        print("HTTP:", response.status_code)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all(
            id=lambda value: isinstance(value, str)
            and re.fullmatch(r"article\d+", value, re.IGNORECASE)
        )
        print("Карточек на странице:", len(cards))

        found = False

        for card in cards:
            text = card.get_text(" ", strip=True)
            links = " ".join(
                a.get("href", "")
                for a in card.find_all("a", href=True)
            )

            pharmacy_539 = re.search(
                r"open_in_map\s*\(\s*['\"]?539(?:\D|$)",
                links,
                re.IGNORECASE,
            )

            if pharmacy_539 or "298,99" in text or "298.99" in text:
                found = True
                print("\n*** ВОЗМОЖНОЕ СОВПАДЕНИЕ ***")
                print("Карточка:", card.get("id"))
                print("Текст:", text)
                print("Ссылки:", links)

        if not found:
            print("Аптека 539 и цена 298,99 среди этих карточек не найдены.")

    except requests.RequestException as exc:
        print("Ошибка запроса:", exc)
