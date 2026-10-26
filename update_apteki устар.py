# -*- coding: utf-8 -*-
"""
Сбор apteki.json из публичного справочника 24lek.ru.
Запуск: python update_apteki.py
Требуются requests и beautifulsoup4. Токен берётся из config.py.
Скрипт сохраняет только аптеки, у которых город в справочнике — Красноярск.
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

BASE = "https://24lek.ru/"
LIST_URL = urljoin(BASE, "apteki.php")
OUT = Path("apteki.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

try:
    from config import DADATA_TOKEN
except Exception as exc:
    raise SystemExit("Не удалось импортировать DADATA_TOKEN из config.py") from exc

if not DADATA_TOKEN or "ВАШ_API_KEY" in DADATA_TOKEN:
    raise SystemExit("Сначала укажи действительный DADATA_TOKEN в config.py")

session = requests.Session()
session.headers.update(HEADERS)


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def parse_pharmacies(html):
    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "karta.php" not in href or "apteka=" not in href:
            continue
        qs = parse_qs(urlparse(urljoin(BASE, href)).query)
        raw_id = (qs.get("apteka") or [None])[0]
        if not raw_id or not raw_id.isdigit() or raw_id in seen:
            continue

        # На странице список обычно расположен строками; ищем ближайший <tr>,
        # а если его нет — ближайший контейнер с достаточным контекстом.
        node = a
        for _ in range(5):
            if node.parent is None:
                break
            node = node.parent
            if getattr(node, "name", None) == "tr":
                break
        row_text = clean(node.get_text(" ", strip=True))
        if not row_text:
            row_text = clean(a.parent.get_text(" ", strip=True))

        # Не включаем другие города. Город обычно стоит в конце строки.
        if not re.search(r"Красноярск\s*$", row_text, flags=re.I):
            continue

        address = clean(a.get_text(" ", strip=True))
        if not address or address.lower().startswith("www."):
            continue

        # Имя аптеки — текст перед ссылкой в строке/контейнере.
        full_text = clean(node.get_text(" ", strip=True))
        before = full_text.split(address, 1)[0].strip(" \t-—|")
        # Убираем хвостовые поля района/телефона, если структура строки не табличная.
        name = before or "Аптека"
        name = re.sub(r"\s+", " ", name).strip()
        records.append({
            "id": int(raw_id),
            "name": name,
            "address": address,
            "city": "Красноярск",
        })
        seen.add(raw_id)

    return records


def geocode(address):
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
    response = session.post(
        url,
        headers={
            "Authorization": f"Token {DADATA_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "query": address,
            "count": 1,
            "locations": [{"city": "Красноярск"}],
        },
        timeout=20,
    )
    response.raise_for_status()
    suggestions = response.json().get("suggestions", [])
    if not suggestions:
        return None
    data = suggestions[0].get("data") or {}
    lat, lon = data.get("geo_lat"), data.get("geo_lon")
    if not lat or not lon:
        return None
    return str(lat), str(lon), suggestions[0].get("value", address)


def main():
    print(f"Загружаю список аптек: {LIST_URL}")
    response = session.get(LIST_URL, timeout=30)
    response.raise_for_status()
    pharmacies = parse_pharmacies(response.text)
    if not pharmacies:
        raise SystemExit(
            "Не удалось извлечь аптеки из HTML. Возможно, сайт изменил структуру "
            "или отдал защитную страницу. apteki.json не изменён."
        )

    print(f"Найдено записей Красноярска: {len(pharmacies)}")
    output = []
    failures = []
    for i, p in enumerate(pharmacies, 1):
        full_address = f"Красноярск, {p['address']}"
        try:
            result = geocode(full_address)
            if result:
                p["lat"], p["lon"], p["geocoded_address"] = result
                output.append(p)
                print(f"[{i}/{len(pharmacies)}] OK ID={p['id']} {p['name']} — {p['address']}")
            else:
                failures.append({**p, "reason": "DaData не вернула координаты"})
                print(f"[{i}/{len(pharmacies)}] НЕТ КООРДИНАТ: {p['address']}")
        except Exception as e:
            failures.append({**p, "reason": str(e)})
            print(f"[{i}/{len(pharmacies)}] ОШИБКА {p['address']}: {e}")
        time.sleep(0.15)

    if not output:
        raise SystemExit("Ни одной аптеки с координатами. apteki.json не изменён.")

    # Записываем атомарно, чтобы при сбое не повредить старый файл.
    temp = OUT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(OUT)

    if failures:
        Path("apteki_failed.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"\nГотово: {len(output)} аптек записано в {OUT.resolve()}")
    if failures:
        print(f"Не удалось геокодировать {len(failures)} записей; см. apteki_failed.json")
    print("Проверь несколько записей на карте перед использованием для точного радиуса 300 м.")


if __name__ == "__main__":
    main()
