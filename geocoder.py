# -*- coding: utf-8 -*-
"""
Геокодирование адреса через Dadata Suggestions API (бесплатный, без карты оплаты).
Документация: https://dadata.ru/api/geocode/
"""

import requests
import config


class GeocodeError(Exception):
    pass


def geocode_address(address: str):
    """
    Возвращает (lat, lon, full_address) для введённого пользователем адреса.
    Используется Dadata suggest API "address" — он не требует платной подписки
    и возвращает координаты (geo_lat/geo_lon) прямо в подсказке.
    """
    if config.DADATA_TOKEN in ("", "ВАШ_API_KEY_DADATA", None):
        raise GeocodeError(
            "Не задан DADATA_TOKEN в config.py. "
            "Получите бесплатный ключ на https://dadata.ru/api/suggest/address/ "
            "и впишите его в config.py."
        )

    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {config.DADATA_TOKEN}",
    }
    query = address
    if config.DADATA_CITY_HINT and config.DADATA_CITY_HINT.lower() not in address.lower():
        query = f"{config.DADATA_CITY_HINT}, {address}"

    payload = {
        "query": query,
        "count": 5,
        "locations": [{"city": config.DADATA_CITY_HINT}] if config.DADATA_CITY_HINT else None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise GeocodeError(f"Dadata API вернул ошибку {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    suggestions = data.get("suggestions", [])
    if not suggestions:
        raise GeocodeError(f"Dadata не нашла адрес: {address!r}")

    # Берём первую подсказку с координатами
    for s in suggestions:
        d = s.get("data", {})
        lat, lon = d.get("geo_lat"), d.get("geo_lon")
        if lat and lon:
            return float(lat), float(lon), s.get("value", address)

    raise GeocodeError(
        f"Dadata нашла адрес {address!r}, но без координат. Уточните адрес (укажите дом)."
    )


if __name__ == "__main__":
    lat, lon, full = geocode_address("Свободный 60")
    print(full, lat, lon)
