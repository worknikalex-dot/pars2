import requests
from config import DADATA_TOKEN, DADATA_CITY_HINT

response = requests.post(
    "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address",
    headers={
        "Authorization": f"Token {DADATA_TOKEN}",
        "Content-Type": "application/json",
    },
    json={
        "query": "Красноярск, улица Ленина, 1",
        "count": 1,
        "locations": [{"city": DADATA_CITY_HINT}],
    },
    timeout=15,
)

print("HTTP:", response.status_code)
print(response.text[:1000])
response.raise_for_status()