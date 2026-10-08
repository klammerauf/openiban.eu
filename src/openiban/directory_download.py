"""Bounded downloads from the configured official publishers only."""

from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from bs4 import BeautifulSoup

from openiban.directories import MAX_BYTES, SOURCES, parse_directory


def validate_url(country: str, url: str) -> str:
    if country not in SOURCES:
        raise ValueError("Unbekanntes Verzeichnisland.")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in SOURCES[country].hosts
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or parsed.fragment
        or len(url) > 1000
    ):
        raise ValueError("Quellen-URL muss beim offiziellen HTTPS-Publisher liegen.")
    return url


class OfficialRedirects(HTTPRedirectHandler):
    def __init__(self, country: str):
        self.country = country

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(self.country, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(country: str, url: str) -> bytes:
    validate_url(country, url)
    opener = build_opener(OfficialRedirects(country))
    try:
        with opener.open(
            Request(url, headers={"User-Agent": "OpenIBAN.eu directory importer"}), timeout=30
        ) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_BYTES:
                raise ValueError("Download größer als 20 MiB.")
            content = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ValueError(
            "Offizielle Quelle nicht erreichbar; aktiver Bestand bleibt unverändert."
        ) from exc
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Download leer oder größer als 20 MiB.")
    return content


def discover_url(country: str, page: bytes) -> str:
    source = SOURCES[country]
    soup = BeautifulSoup(page.decode("utf-8-sig"), "html.parser")
    links = set()
    for a in soup.select("a[href]"):
        url = urljoin(source.page, a["href"])
        path = urlsplit(url).path.lower()
        if country == "LT" and path.endswith("-en.csv") and "fik_kodai" in path:
            links.add(validate_url(country, url))
        if country == "LV" and path.endswith(".xls") and "bic_saraksts" in path:
            links.add(validate_url(country, url))
    # LV pages also carry an older hidden link. Follow the visible 'BIC list'.
    if country == "LV":
        visible = {
            urljoin(source.page, a["href"])
            for a in soup.select("a[href]")
            if a.get_text(" ", strip=True).lower() == "bic list"
        }
        links &= visible
    if len(links) != 1:
        raise ValueError("Downloadlink fehlt/mehrdeutig; offizielle Quellen-URL explizit angeben.")
    return links.pop()


def download_directory(country: str, source_url: str | None = None) -> tuple[bytes, str]:
    if country not in SOURCES:
        raise ValueError("Unbekanntes Land.")
    source = SOURCES[country]
    url = source_url or source.download
    if url is None:
        url = discover_url(country, fetch(country, source.page))
    content = fetch(country, url)
    parse_directory(country, content)
    return content, url
