
import re
import requests
from bs4 import BeautifulSoup

URL = "https://24lek.ru/action.php"

params = {
    "kray": 0,
    "city": 0,
    "query": "тауфон 10 мл кап",
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

response = session.get(URL, params=params, timeout=30)

print("HTTP:", response.status_code)
print("URL:", response.url)
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

    is_target = (
        re.search(
            r"open_in_map\s*\(\s*['\"]?539(?:\D|$)",
            links,
            re.IGNORECASE,
        )
        or (
            "Дешевая аптека" in text
            and "Свободный 29" in text
            and ("298,99" in text or "298.99" in text)
        )
    )

    if is_target:
        found = True
        print("\n*** НАЙДЕНА НУЖНАЯ КАРТОЧКА ***")
        print("ID карточки:", card.get("id"))
        print("Текст:", text)
        print("Ссылки:", links)

if not found:
    print("Нужная карточка не найдена среди результатов первой страницы.")

print("\nПараметры пагинации:")

for script in soup.find_all("script"):
    text = script.string or script.get_text()

    rows = re.search(r"""num_rows\s*=\s*["'](\d+)["']""", text)
    code = re.search(
        r"""Send\s*\[\s*['"]code['"]\s*\]\s*=\s*['"]([^'"]+)['"]""",
        text,
    )

    if rows:
        print("Всего результатов:", rows.group(1))

    if code:
        print("Код пагинации получен:", bool(code.group(1)))
