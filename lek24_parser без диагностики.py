
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config


BASE_URL = "https://24lek.ru"
SEARCH_URL = f"{BASE_URL}/action.php"
PAGE_URL = f"{BASE_URL}/action2.php"

ARTICLE_RE = re.compile(r"^article\d+$", re.IGNORECASE)

PHARMACY_ID_RE = re.compile(
    r"""open_in_map\s*\(\s*['"]?(\d+)""",
    re.IGNORECASE,
)

PRICE_RE = re.compile(
    r"^\s*"
    r"(\d+(?:[\s\u00a0]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"\s*(?:₽|руб\.?|р\.)?\s*$",
    re.IGNORECASE,
)

INTERNET_PHARMACIES = {
    1105: {
        "domains": ("apteka.ru",),
        "names": ("аптека.ру",),
    },
    731: {
        "domains": ("aptekalegko.ru",),
        "names": ("аптека легко",),
    },
    897: {
        "domains": ("gubernskieapteki.ru",),
        "names": ("губернскиеаптеки", "губернские аптеки"),
    },
    1151: {
        "domains": ("pharmeconom.ru",),
        "names": ("фармэконом",),
    },
    344: {
        "domains": ("аптеканейрон.рф",),
        "names": ("нейрон",),
    },
    813: {
        "domains": ("таблеткитут.рф",),
        "names": ("таблеткитут", "таблетки тут"),
    },
}


def _make_session() -> requests.Session:
    """Создаёт HTTP-сессию для запросов к сайту."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    })
    return session


def _parse_price(text: str) -> Optional[float]:
    """Преобразует текст цены в число."""
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

    return price if price > 0 else None


def _normalize_host(host: str) -> str:
    """Нормализует домен."""
    host = (host or "").strip().lower().rstrip(".")

    try:
        host = host.encode("ascii").decode("idna")
    except UnicodeError:
        pass

    return host


def _get_internet_pharmacy_id(element: Any) -> Optional[int]:
    """Определяет интернет-аптеку по домену или тексту ссылки."""
    if not hasattr(element, "find_all"):
        return None

    for link in element.find_all("a", href=True):
        href = unquote(str(link.get("href", ""))).strip()
        link_text = link.get_text(" ", strip=True).lower()

        try:
            host = _normalize_host(urlparse(href).hostname or "")
        except ValueError:
            host = ""

        for pharmacy_id, info in INTERNET_PHARMACIES.items():
            for domain in info["domains"]:
                normalized_domain = _normalize_host(domain)

                if (
                    host == normalized_domain
                    or host.endswith("." + normalized_domain)
                ):
                    return pharmacy_id

            if any(name in link_text for name in info["names"]):
                return pharmacy_id

    return None


def _get_pharmacy_id(element: Any) -> Optional[int]:
    """Определяет ID физической или интернет-аптеки."""
    match = PHARMACY_ID_RE.search(str(element))

    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    if hasattr(element, "find_all"):
        for link in element.find_all("a", href=True):
            match = PHARMACY_ID_RE.search(str(link.get("href", "")))

            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass

    return _get_internet_pharmacy_id(element)


def _get_card_url(card: Any) -> str:
    """Извлекает ссылку на карточку товара на 24lek.ru."""
    base_host = _normalize_host(urlparse(BASE_URL).hostname or "")

    for link in card.find_all("a", href=True):
        href = unquote(str(link.get("href", "")).strip())

        if not href or href.startswith(
            ("javascript:", "mailto:", "tel:", "#")
        ):
            continue

        try:
            parsed = urlparse(href)
        except ValueError:
            continue

        if parsed.scheme and parsed.netloc:
            host = _normalize_host(parsed.hostname or "")

            if host != base_host and not host.endswith("." + base_host):
                continue

        absolute_url = urljoin(BASE_URL, href)

        if urlparse(absolute_url).path:
            return absolute_url

    return ""


def _extract_items_from_html(html_text: str) -> List[Dict[str, Any]]:
    """Извлекает цены из HTML-карточек товаров."""
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

        price = _parse_price(spans[2].get_text(" ", strip=True))

        if price is None:
            continue

        name = spans[0].get_text(" ", strip=True)

        if not name:
            name = card.get_text(" ", strip=True)

        pharmacy_id = _get_pharmacy_id(card)

        if pharmacy_id is None:
            continue

        items.append({
            "apteka_id": pharmacy_id,
            "pharmacy_id": pharmacy_id,
            "price": price,
            "name": name,
            "source": BASE_URL,
            "url": _get_card_url(card),
        })

    return items


def _get_pagination_meta(html_text: str) -> Dict[str, Any]:
    """Извлекает возможные метаданные пагинации."""
    rows_match = re.search(
        r"""num_rows\s*=\s*["']?(\d+)["']?""",
        html_text,
        re.IGNORECASE,
    )

    code_match = re.search(
        r"""Send\s*\[\s*['"]code['"]\s*\]\s*=\s*['"]([^'"]+)['"]""",
        html_text,
        re.IGNORECASE,
    )

    return {
        "total_rows": int(rows_match.group(1)) if rows_match else 0,
        "code": code_match.group(1) if code_match else "",
    }


def _print_response_diagnostics(
    response: requests.Response,
    query: str,
) -> None:
    """Выводит информацию об HTTP-ответе."""
    print(
        f"[24lek] Запрос: {query!r}; "
        f"HTTP {response.status_code}; URL: {response.url}"
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

    Сохраняет совместимость с вызовом из main.py:
        search_drug_prices(query, needed_apteka_ids, session, raon_id)

    Полнота поиска не считается подтверждённой, если:
    - отсутствуют метаданные количества строк;
    - необходимая пагинация завершилась ошибкой;
    - достигнут установленный лимит страниц.

    Поля результата:
        source, url, search_complete, search_status, search_reason
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

    all_items: List[Dict[str, Any]] = []
    seen_records: Set[Tuple[int, float, str]] = set()
    search_complete = False
    incomplete_reason = "Полнота поиска не подтверждена"

    def add_items(page_html: str) -> int:
        added = 0

        for item in _extract_items_from_html(page_html):
            pharmacy_id = item["apteka_id"]

            if (
                needed_apteka_ids is not None
                and pharmacy_id not in needed_apteka_ids
            ):
                continue

            key = (pharmacy_id, item["price"], item["name"])

            if key in seen_records:
                continue

            seen_records.add(key)
            all_items.append(item)
            added += 1

        return added

    try:
        try:
            response = session.get(
                SEARCH_URL,
                params=params,
                timeout=30,
            )
            _print_response_diagnostics(response, query)
            response.raise_for_status()
        except requests.RequestException as exc:
            incomplete_reason = f"Ошибка начального запроса: {exc}"
            print(
                f"[24lek] Ошибка поискового запроса "
                f"{query!r}, raon={selected_raon}: {exc}"
            )
            return []

        first_page_count = add_items(response.text)

        print(
            f"[24lek] {query!r}, raon={selected_raon}: "
            f"первая страница — {first_page_count} подходящих позиций."
        )

        pagination = _get_pagination_meta(response.text)
        total_rows = pagination["total_rows"]
        code = pagination["code"]

        if total_rows <= 0:
            incomplete_reason = (
                "Не удалось определить общее количество строк (num_rows)"
            )
            print(f"[24lek] {query!r}: {incomplete_reason}.")

        elif total_rows <= 50:
            # Нам неизвестно, означает ли num_rows общее число результатов
            # или иной счётчик. Поэтому не объявляем поиск полным только
            # на основании значения этого поля.
            incomplete_reason = (
                f"num_rows={total_rows}, но значение поля не подтверждено; "
                "полнота первой страницы неизвестна"
            )
            print(f"[24lek] {query!r}: {incomplete_reason}.")

        elif not code:
            incomplete_reason = (
                f"Обнаружено num_rows={total_rows}, "
                "но не найден код пагинации"
            )
            print(f"[24lek] {query!r}: {incomplete_reason}.")

        else:
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
            pagination_ok = True
            offsets = range(page_size, max_offset, page_size)

            for offset in offsets:
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
                    pagination_ok = False

                    status_code = (
                        exc.response.status_code
                        if isinstance(exc, requests.HTTPError)
                        and exc.response is not None
                        else None
                    )

                    incomplete_reason = (
                        f"Пагинация прервана на offset={offset}; "
                        f"HTTP {status_code or 'ошибка запроса'}"
                    )
                    print(f"[24lek] {query!r}: {incomplete_reason}.")
                    break

                added = add_items(page_response.text)

                print(
                    f"[24lek] {query!r}, raon={selected_raon}: "
                    f"offset={offset}, добавлено {added}, "
                    f"всего {len(all_items)}."
                )

                if request_delay:
                    time.sleep(request_delay)

            if pagination_ok:
                if total_rows <= max_offset:
                    incomplete_reason = (
                        "Запросы пагинации завершились, но соответствие "
                        "num_rows фактическому числу результатов "
                        "не подтверждено"
                    )
                else:
                    incomplete_reason = (
                        f"Достигнут лимит страниц; num_rows={total_rows}"
                    )

    finally:
        if own_session:
            session.close()

    status = "FOUND" if all_items else "INCOMPLETE"

    for item in all_items:
        item["search_complete"] = search_complete
        item["search_status"] = status
        item["search_reason"] = incomplete_reason

    if needed_apteka_ids is not None:
        found_ids = {item["apteka_id"] for item in all_items}
        missing_ids = sorted(needed_apteka_ids - found_ids)

        if missing_ids:
            print(
                f"[24lek] {query!r}, raon={selected_raon}: "
                f"нет подходящих ценовых записей для ID аптек: "
                f"{missing_ids}"
            )

    print(
        f"[24lek] {query!r}, raon={selected_raon}: "
        f"найдено {len(all_items)} ценовых записей; "
        f"полный поиск: {'да' if search_complete else 'нет'}; "
        f"статус: {status}."
    )

    if incomplete_reason:
        print(f"[24lek] Причина неполного поиска: {incomplete_reason}")

    return all_items
