import re
import time
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8'
}

REQUEST_TIMEOUT = 10
POLITE_DELAY_SECONDS = 0.3  # small gap between page fetches so we don't hammer the source site


def get_session():
    """A requests Session with retry/backoff so one dropped connection doesn't
    just show up as a permanent 'Error' in the dashboard."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def clean_number(raw_text):
    numbers = re.findall(r'\d+', raw_text.replace(',', ''))
    return int(''.join(numbers)) if numbers else None


def is_valid_post_url(url, domain):
    if not url or not url.startswith('http'):
        return False
    parsed = urlparse(url)
    if domain not in parsed.netloc:
        return False
    invalid_patterns = ['/category/', '/tag/', '/page/', '/author/', '/comment', '#', '?s=', '/contact', '/about']
    return not any(pattern in url.lower() for pattern in invalid_patterns)


def _extract_views_downloadha(soup):
    counter = soup.select_one('div.tptn_counter')
    return clean_number(counter.text) if counter else None


def _extract_views_dlfox(soup):
    label_td = soup.find(
        lambda tag: tag.name == 'td' and 'head_info' in tag.get('class', []) and 'تعداد بازدید' in tag.text
    )
    if not label_td:
        return None
    value_td = label_td.find_next_sibling('td')
    return clean_number(value_td.text) if value_td else None


# Single source of truth for both sites -- add a new site by adding one entry here.
SITES = {
    'downloadha': {
        'display': 'Downloadha',
        'domain': 'downloadha.com',
        'search_url': 'https://www.downloadha.com/?s={q}',
        'home_url': 'https://www.downloadha.com',
        'listing_selector': 'article a, .post a, .post-title a, h2 a, h3 a, .entry-title a',
        'extract_views': _extract_views_downloadha,
    },
    'dlfox': {
        'display': 'DLFox',
        'domain': 'dlfox.com',
        'search_url': 'https://www.dlfox.com/?s={q}',
        'home_url': 'https://www.dlfox.com',
        'listing_selector': '.post_title a, .title_post a, article a, h2 a, h3 a, .post a',
        'extract_views': _extract_views_dlfox,
    },
}


def scrape_single_page(site_key, url, session=None):
    """Fetch one post page and pull its view count. Used both for ad-hoc
    search results and for refreshing a tracked game."""
    cfg = SITES[site_key]
    session = session or get_session()
    try:
        res = session.get(url, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        views = cfg['extract_views'](soup)
        return {"source": cfg['display'], "url": url, "views": views if views is not None else "N/A"}
    except requests.RequestException:
        return {"source": cfg['display'], "url": url, "views": "Error"}


def search_and_scrape(site_key, query, max_results=5, session=None):
    cfg = SITES[site_key]
    session = session or get_session()

    search_url = cfg['search_url'].format(q=quote(query))
    try:
        res = session.get(search_url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        return [{"source": cfg['display'], "url": None, "views": f"Network error: {e.__class__.__name__}"}]

    if res.status_code != 200:
        return [{"source": cfg['display'], "url": None, "views": f"HTTP {res.status_code}"}]

    # Direct post redirect: the search engine sent us straight to a single matching post
    landed_on_home = res.url.rstrip('/') == cfg['home_url'].rstrip('/')
    if '?s=' not in res.url and cfg['domain'] in res.url and not landed_on_home:
        soup = BeautifulSoup(res.text, 'html.parser')
        views = cfg['extract_views'](soup)
        return [{"source": cfg['display'], "url": res.url, "views": views if views is not None else "N/A"}]

    soup = BeautifulSoup(res.text, 'html.parser')
    all_links = soup.select(cfg['listing_selector'])

    target_urls = []
    for a in all_links:
        href = a.get('href')
        if is_valid_post_url(href, cfg['domain']) and href not in target_urls:
            target_urls.append(href)
            if len(target_urls) >= max_results:
                break

    if not target_urls:
        return [{"source": cfg['display'], "url": None, "views": "Not Found"}]

    results = []
    for i, target_url in enumerate(target_urls):
        results.append(scrape_single_page(site_key, target_url, session))
        if i < len(target_urls) - 1:
            time.sleep(POLITE_DELAY_SECONDS)
    return results
