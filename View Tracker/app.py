import re
from urllib.parse import quote, urlparse
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8'
}

def clean_number(raw_text):
    numbers = re.findall(r'\d+', raw_text.replace(',', ''))
    return int(''.join(numbers)) if numbers else 0

def is_valid_post_url(url, domain):
    if not url or not url.startswith('http'):
        return False
    parsed = urlparse(url)
    if domain not in parsed.netloc:
        return False
    
    invalid_patterns = ['/category/', '/tag/', '/page/', '/author/', '/comment', '#', '?s=', '/contact', '/about']
    return not any(pattern in url.lower() for pattern in invalid_patterns)


# --- DOWNLOADHA SCRAPER (Multiple Results) ---
def search_and_scrape_downloadha(query, max_results=5):
    try:
        search_url = f"https://www.downloadha.com/?s={quote(query)}"
        res = requests.get(search_url, headers=HEADERS, timeout=10)
        
        if res.status_code != 200:
            return [{"source": "Downloadha", "url": None, "views": f"HTTP {res.status_code}"}]

        # Direct post redirect
        if '?s=' not in res.url and 'downloadha.com/' in res.url and res.url != 'https://www.downloadha.com/':
            soup = BeautifulSoup(res.text, 'html.parser')
            counter = soup.select_one('div.tptn_counter')
            views = clean_number(counter.text) if counter else "N/A"
            return [{"source": "Downloadha", "url": res.url, "views": views}]

        soup = BeautifulSoup(res.text, 'html.parser')
        all_links = soup.select('article a, .post a, .post-title a, h2 a, h3 a, .entry-title a')
        
        # Collect unique valid URLs up to max_results
        target_urls = []
        for a in all_links:
            href = a.get('href')
            if is_valid_post_url(href, 'downloadha.com') and href not in target_urls:
                target_urls.append(href)
                if len(target_urls) >= max_results:
                    break

        if not target_urls:
            return [{"source": "Downloadha", "url": None, "views": "Not Found"}]

        # Scrape view counts for each target URL
        results = []
        for target_url in target_urls:
            try:
                post_res = requests.get(target_url, headers=HEADERS, timeout=10)
                post_soup = BeautifulSoup(post_res.text, 'html.parser')
                counter = post_soup.select_one('div.tptn_counter')
                views = clean_number(counter.text) if counter else "N/A"
                results.append({"source": "Downloadha", "url": target_url, "views": views})
            except Exception:
                results.append({"source": "Downloadha", "url": target_url, "views": "Error"})

        return results

    except Exception:
        return [{"source": "Downloadha", "url": None, "views": "Error"}]


# --- DLFOX SCRAPER (Multiple Results) ---
def search_and_scrape_dlfox(query, max_results=5):
    try:
        search_url = f"https://www.dlfox.com/?s={quote(query)}"
        res = requests.get(search_url, headers=HEADERS, timeout=10)
        
        if res.status_code != 200:
            return [{"source": "DLFox", "url": None, "views": f"HTTP {res.status_code}"}]

        # Direct post redirect
        if '?s=' not in res.url and 'dlfox.com/' in res.url and res.url != 'https://www.dlfox.com/':
            soup = BeautifulSoup(res.text, 'html.parser')
            label_td = soup.find(lambda tag: tag.name == 'td' and 'head_info' in tag.get('class', []) and 'تعداد بازدید' in tag.text)
            if label_td:
                value_td = label_td.find_next_sibling('td')
                views = clean_number(value_td.text) if value_td else "N/A"
            else:
                views = "N/A"
            return [{"source": "DLFox", "url": res.url, "views": views}]

        soup = BeautifulSoup(res.text, 'html.parser')
        all_links = soup.select('.post_title a, .title_post a, article a, h2 a, h3 a, .post a')
        
        # Collect unique valid URLs up to max_results
        target_urls = []
        for a in all_links:
            href = a.get('href')
            if is_valid_post_url(href, 'dlfox.com') and href not in target_urls:
                target_urls.append(href)
                if len(target_urls) >= max_results:
                    break

        if not target_urls:
            return [{"source": "DLFox", "url": None, "views": "Not Found"}]

        # Scrape view counts for each target URL
        results = []
        for target_url in target_urls:
            try:
                post_res = requests.get(target_url, headers=HEADERS, timeout=10)
                post_soup = BeautifulSoup(post_res.text, 'html.parser')
                label_td = post_soup.find(lambda tag: tag.name == 'td' and 'head_info' in tag.get('class', []) and 'تعداد بازدید' in tag.text)
                if label_td:
                    value_td = label_td.find_next_sibling('td')
                    views = clean_number(value_td.text) if value_td else "N/A"
                else:
                    views = "N/A"
                results.append({"source": "DLFox", "url": target_url, "views": views})
            except Exception:
                results.append({"source": "DLFox", "url": target_url, "views": "Error"})

        return results

    except Exception:
        return [{"source": "DLFox", "url": None, "views": "Error"}]


# --- ROUTES ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    downloadha_results = search_and_scrape_downloadha(query)
    dlfox_results = search_and_scrape_dlfox(query)

    # Flatten results into one list
    all_results = []
    for item in downloadha_results + dlfox_results:
        all_results.append({"title": query, **item})

    return jsonify(all_results)


if __name__ == '__main__':
    app.run(debug=True, port=5000)