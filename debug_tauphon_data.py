import requests

url = "https://24lek.ru/data.json.php"

params = {
    "query": "",
    "city": "0",
    "raon": "0",
    "apteka": "539",
    "remove_content": "1",
}

response = requests.get(
    url,
    params=params,
    headers={
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://24lek.ru/karta.php?encoding=utf8&apteka=539",
    },
    timeout=30,
)

print("HTTP:", response.status_code)
print("URL:", response.url)
print("Размер ответа:", len(response.text))
print("Начало ответа:")
print(response.text[:5000])

with open("debug_tauphon_data.json", "w", encoding="utf-8") as file:
    file.write(response.text)

print("\nОтвет сохранён в debug_tauphon_data.json")