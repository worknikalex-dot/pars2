
import re
import time
import requests
import config
from bs4 import BeautifulSoup

BASE_URL = "https://24lek.ru"
SEARCH_URL = f"{BASE_URL}/action.php"
PAGE_URL = f"{BASE_URL}/action2.php"
QUERY = "тауфон 10 мл кап"

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
})

params = {
    "kray": 0,
    "city": getattr(config, "CITY_ID_24LEK", ""),
    "raon": getattr(config, "RAON_ID_24LEK", ""),
    "query": QUERY,
}

response = session.get(SEARCH_URL, params=params, timeout=30)
print("Первая страница HTTP:", response.status_code)
response.raise_for_status()

def inspect(html, page_label):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all(
        id=lambda value: isinstance(value, str)
        and re.fullmatch(r"article\d+", value, re.IGNORECASE)
    )
    matches = 0

    for card in cards:
        text = card.get_text(" ", strip=True)
        links = " ".join(
            a.get("href", "") for a in card.find_all("a", href=True)
        )
        if (
            re.search(r"open_in_map\s*\(\s*['\"]?539", links)
            or "298,99" in text
            or "298.99" in text
        ):
            matches += 1
            print(f"\nНАЙДЕНО: {page_label}")
            print("Карточка:", card.get("id"))
            print("Текст:", text)
            print("Ссылки:", links)

    return len(cards), matches

total_cards, matches = inspect(response.text, "первая страница")

rows_match = re.search(
    r"""num_rows\s*=\s*["'](\d+)["']""",
    response.text,
    re.IGNORECASE,
)
code_match = re.search(
    r"""Send\s*\[\s*['"]code['"]\s*\]\s*=\s*['"]([^'"]+)['"]""",
    response.text,
    re.IGNORECASE,
)

total_rows = int(rows_match.group(1)) if rows_match else 0
code = code_match.group(1) if code_match else ""

print("\nВсего строк по сайту:", total_rows)
print("Код пагинации получен:", bool(code))
print("Карточек на первой странице:", total_cards)

if not code or total_rows <= 0:
    print("Пагинацию не удалось определить. Остановлено.")
else:
    for offset in range(50, min(total_rows, 1000), 50):
        data = {
            "a": QUERY,
            "city": params["city"],
            "raon": params["raon"],
            "num": offset,
            "code": code,
        }
        try:
            page = session.post(
                PAGE_URL,
                data=data,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": response.url,
                },
                timeout=30,
            )
            print(
                f"Страница offset={offset}: "
                f"HTTP {page.status_code}, HTML={len(page.text)}"
            )
            if page.status_code != 200:
                print("Начало ответа:", page.text[:200].replace("\n", " "))
                continue

            count, found = inspect(page.text, f"offset={offset}")
            total_cards += count
            matches += found
            time.sleep(0.5)
        except requests.RequestException as exc:
            print(f"Ошибка offset={offset}: {exc}")

print("\nВсего просмотрено карточек:", total_cards)
print("Совпадений с аптекой 539 или ценой 298,99:", matches)
