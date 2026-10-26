import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

import config


BASE_URL = "https://24lek.ru"
SEARCH_URL = f"{BASE_URL}/action.php"
PAGE_URL = f"{BASE_URL}/action2.php"

ARTICLE_RE = re.compile(r"^article\d+$", re.IGNORECASE)

PHARMACY_ID_RE = re.compile(
    r"open_in_map\s*\(\s*['\"]?(\d+)",
    re.IGNORECASE,
)

PRICE_RE = re.compile(
    r"^\s*"
    r"(\d+(?:[\s\u00a0]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"\s*(?:₽|руб\.?|р\.)?\s*$",
    re.IGNORECASE,
)


def _make_session() -> requests.Session:
    """Создаёт HTTP-сессию для запросов к сайту."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
    )
    return session


def _parse_price(text: str) -> Optional[float]:
    """Преобразует текст третьего span в цену."""
    if not text:
        return None

    cleaned = text.replace("\xa0", " ").strip()
    match = PRICE_RE.fullmatch(cleaned)

    if not match:
        return None

    number = re.sub(r"[\s\u00a0]", "", match.group(1))
    number = number.replace(",", ".")

    try:
        price = float(number)
    except (TypeError, ValueError):
        return None

    if price <= 0:
        return None

    return price


def _get_pharmacy_id(element: Any) -> Optional[int]:
    """Извлекает ID аптеки из open_in_map(ID)."""
    match = PHARMACY_ID_RE.search(str(element))

    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None

    if hasattr(element, "find_all"):
        for link in element.find_all("a", href=True):
            match = PHARMACY_ID_RE.search(
                str(link.get("href", ""))
            )
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    return None

    return None


def _extract_items_from_html(
    html_text: str,
) -> List[Dict[str, Any]]:
    """
    Извлекает цены из карточек товаров.

    Цена берётся только из третьего span (spans[2]).
    Если третьего span нет или значение не является ценой,
    карточка пропускается без поиска альтернативного числа.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    items: List[Dict[str, Any]] = []

    cards = soup.find_all(
        id=lambda value: isinstance(value, str)
        and ARTICLE_RE.fullmatch(value)
    )

    if not cards:
        cards = soup.select("[id^='article']")

    seen_cards: Set[str] = set()

    for card in cards:
        card_id = str(card.get("id", ""))

        if card_id and card_id in seen_cards:
            continue

        if card_id:
            seen_cards.add(card_id)

        spans = card.find_all("span")

        if len(spans) < 3:
            continue

        # Цена — строго третий span.
        price_text = spans[2].get_text(" ", strip=True)
        price = _parse_price(price_text)

        if price is None:
            continue

        # Название товара находится в первом span.
        name = spans[0].get_text(" ", strip=True)

        if not name:
            name = card.get_text(" ", strip=True)

        pharmacy_id = _get_pharmacy_id(card)

        if pharmacy_id is None:
            continue

        items.append(
            {
                "apteka_id": pharmacy_id,
                "pharmacy_id": pharmacy_id,
                "price": price,
                "name": name,
            }
        )

    return items


def _get_pagination_meta(
    html_text: str,
) -> Dict[str, Any]:
    """Получает количество строк и код для пагинации."""
    rows_match = re.search(
        r"""num_rows\s*=\s*["'](\d+)["']""",
        html_text,
        re.IGNORECASE,
    )

    code_match = re.search(
        r"""Send\s*\[\s*['"]code['"]\s*\]\s*=\s*['"]([^'"]+)['"]""",
        html_text,
        re.IGNORECASE,
    )

    total_rows = int(rows_match.group(1)) if rows_match else 0
    code = code_match.group(1) if code_match else ""

    return {
        "total_rows": total_rows,
        "code": code,
    }


def _print_response_diagnostics(
    response: requests.Response,
    query: str,
) -> None:
    """Выводит информацию об HTTP-ответе."""
    print(
        f"[24lek] Запрос: {query!r}; "
        f"HTTP {response.status_code}; "
        f"URL: {response.url}"
    )

    if response.status_code >= 400:
        preview = response.text[:500].replace("\n", " ")
        print(f"[24lek] Начало ответа: {preview}")


def search_drug_prices(
    query: str,
    needed_apteka_ids: Optional[Set[int]] = None,
    session: Optional[requests.Session] = None,
    raon_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Ищет цены на 24lek.ru.

    raon_id:
        None — использует config.RAON_ID_24LEK;
        0 — все районы;
        1–7 — конкретный район Красноярска.

    Прежние вызовы из main.py остаются совместимыми.

    Возвращает записи с полями:
        apteka_id, pharmacy_id, price, name
    """
    query = str(query or "").strip()

    if not query:
        print("[24lek] Пустой поисковый запрос — пропускаю.")
        return []

    own_session = session is None

    if session is None:
        session = _make_session()

    selected_raon = (
        getattr(config, "RAON_ID_24LEK", 0)
        if raon_id is None
        else raon_id
    )

    params = {
        "kray": 0,
        "city": getattr(config, "CITY_ID_24LEK", ""),
        "raon": selected_raon,
        "query": query,
    }

    try:
        response = session.get(
            SEARCH_URL,
            params=params,
            timeout=30,
        )
        _print_response_diagnostics(response, query)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(
            f"[24lek] Ошибка поискового запроса "
            f"{query!r}, raon={selected_raon}: {exc}"
        )
        if own_session:
            session.close()
        return []

    all_items: List[Dict[str, Any]] = []
    seen_records: Set[Tuple[int, float, str]] = set()

    def add_items(page_html: str) -> int:
        """Добавляет уникальные записи с одной страницы."""
        added = 0

        for item in _extract_items_from_html(page_html):
            pharmacy_id = item["apteka_id"]

            if (
                needed_apteka_ids is not None
                and pharmacy_id not in needed_apteka_ids
            ):
                continue

            key = (
                pharmacy_id,
                item["price"],
                item["name"],
            )

            if key in seen_records:
                continue

            seen_records.add(key)
            all_items.append(item)
            added += 1

        return added

    first_page_count = add_items(response.text)

    print(
        f"[24lek] {query!r}, raon={selected_raon}: "
        f"первая страница — {first_page_count} подходящих позиций."
    )

    pagination = _get_pagination_meta(response.text)
    total_rows = pagination["total_rows"]
    code = pagination["code"]

    if total_rows <= 0 or not code:
        print(
            f"[24lek] {query!r}: пагинация недоступна "
            f"(num_rows={total_rows}, "
            f"code={'есть' if code else 'нет'})."
        )

        if own_session:
            session.close()

        return all_items

    page_size = 50
    max_pages = max(
        1,
        int(getattr(config, "MAX_PAGES_PER_QUERY", 20)),
    )
    request_delay = max(
        0.0,
        float(getattr(config, "REQUEST_DELAY", 0.5)),
    )

    max_offset = min(total_rows, page_size * max_pages)

    for offset in range(page_size, max_offset, page_size):
        data = {
            "a": query,
            "city": params["city"],
            "raon": params["raon"],
            "num": offset,
            "code": code,
        }

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": response.url,
        }

        try:
            page_response = session.post(
                PAGE_URL,
                data=data,
                headers=headers,
                timeout=30,
            )
            _print_response_diagnostics(page_response, query)
            page_response.raise_for_status()
        except requests.RequestException as exc:
            print(
                f"[24lek] Ошибка пагинации для {query!r}, "
                f"raon={selected_raon}, offset={offset}: {exc}"
            )
            continue

        added = add_items(page_response.text)

        print(
            f"[24lek] {query!r}, raon={selected_raon}: "
            f"offset={offset}, добавлено {added}, "
            f"всего {len(all_items)}."
        )

        if request_delay:
            time.sleep(request_delay)

    if needed_apteka_ids is not None:
        found_ids = {
            item["apteka_id"] for item in all_items
        }
        missing_ids = sorted(
            needed_apteka_ids - found_ids
        )

        if missing_ids:
            print(
                f"[24lek] {query!r}, raon={selected_raon}: "
                f"не найдены цены для ID аптек: {missing_ids}"
            )

    if own_session:
        session.close()

    print(
        f"[24lek] {query!r}, raon={selected_raon}: "
        f"всего найдено {len(all_items)} ценовых записей."
    )

    return all_items