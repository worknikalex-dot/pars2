import re
import requests
from bs4 import BeautifulSoup

URL = "https://24lek.ru/karta.php?encoding=utf8&apteka=539"

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

response = session.get(URL, timeout=30)
print("HTTP:", response.status_code)
print("URL:", response.url)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
cards = soup.find_all(id=lambda value: isinstance(value, str) and re.fullmatch(r"article\d+", value, re.IGNORECASE))
matches = [card for card in cards if "ТАУФОН" in card.get_text(" ", strip=True).upper()]

print("Всего карточек article:", len(cards))
print("Карточек с ТАУФОНОМ:", len(matches))

for card in matches:
print("\n--- КАРТОЧКА", card.get("id"), "---")
print("ТЕКСТ:", card.get_text(" ", strip=True))
print("КОЛИЧЕСТВО SPAN:", len(card.find_all("span")))
print(card.prettify()[:8000])

if not matches:
print("\nКарточки не найдены. Фрагмент HTML страницы:")
print(response.text[:3000])

session.close()