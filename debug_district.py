
import requests
from bs4 import BeautifulSoup

url = "https://24lek.ru/action.php"

response = requests.get(
    url,
    params={
        "kray": 0,
        "city": 0,
        "raon": 0,
        "query": "тауфон 4 10",
    },
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        )
    },
    timeout=30,
)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

print("Формы на странице:")
for form in soup.find_all("form"):
    print("\nFORM:", form.get("action"), form.get("method"))
    for item in form.find_all(["input", "select", "button"]):
        print(
            item.name,
            "name=", item.get("name"),
            "id=", item.get("id"),
            "value=", item.get("value"),
            "text=", item.get_text(" ", strip=True)[:100],
        )

print("\nУпоминания района и параметра raon в скриптах:")
for script in soup.find_all("script"):
    text = script.string or script.get_text()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "raon" in line.lower() or "Железнодорожный" in line:
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            print("\n".join(lines[start:end]))
            print("---")
