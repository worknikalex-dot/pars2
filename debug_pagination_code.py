
import requests
from bs4 import BeautifulSoup

url = "https://24lek.ru/action.php"
params = {
    "kray": 0,
    "city": 0,
    "raon": 0,
    "query": "тауфон 10 мл кап",
}

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
}

response = requests.get(
    url,
    params=params,
    headers=headers,
    timeout=30,
)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

for script in soup.find_all("script"):
    src = script.get("src", "")
    if src:
        print(src)

    text = script.string or script.get_text()
    if any(word in text.lower() for word in (
        "action2.php", "send[", "num_rows", "ajax"
    )):
        print("\n--- ФРАГМЕНТ SCRIPT ---")
        print(text[:10000])
