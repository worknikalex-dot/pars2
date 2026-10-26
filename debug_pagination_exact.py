
import requests
from bs4 import BeautifulSoup

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
})

search_url = "https://24lek.ru/action.php"
page_url = "https://24lek.ru/action2.php"

params = {
    "kray": 0,
    "city": 0,
    "raon": 0,
    "query": "тауфон 10 мл кап",
}

first = session.get(search_url, params=params, timeout=30)
print("Поиск:", first.status_code, first.url)
first.raise_for_status()

soup = BeautifulSoup(first.text, "html.parser")
print("Код пагинации из HTML:")

for script in soup.find_all("script"):
    text = script.string or script.get_text()
    if "Send['code']" in text:
        print(text[:3000])

payload = {
    "a": "тауфон 10 мл кап",
    "city": "0",
    "raon": "0",
    "num": "50",
    "code": "98fdcc1c42",
}

print("\nPOST без дополнительных заголовков:")
r1 = session.post(page_url, data=payload, timeout=30)
print("HTTP:", r1.status_code)
print("URL:", r1.url)
print("Размер ответа:", len(r1.text))
print("Начало ответа:", repr(r1.text[:300]))

print("\nPOST с заголовками AJAX:")
r2 = session.post(
    page_url,
    data=payload,
    headers={
        "X-Requested-With": "XMLHttpRequest",
        "Referer": first.url,
    },
    timeout=30,
)
print("HTTP:", r2.status_code)
print("Размер ответа:", len(r2.text))
print("Начало ответа:", repr(r2.text[:300]))
