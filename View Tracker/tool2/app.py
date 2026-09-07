import logging
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, render_template, request, jsonify

import database
import scraper
from scheduler import start_scheduler, refresh_all_tracked

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
database.init_db()
_scheduler = start_scheduler()


@app.route('/')
def home():
    return render_template('dashboard.html')


@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    # Both sites are fetched in parallel instead of one after another.
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(scraper.search_and_scrape, key, query) for key in scraper.SITES]
        all_results = []
        for future in futures:
            for item in future.result():
                item["title"] = query
                item["site_key"] = next(
                    k for k, v in scraper.SITES.items() if v["display"] == item["source"]
                )
                all_results.append(item)

    return jsonify(all_results)


@app.route('/api/tracked', methods=['GET'])
def api_list_tracked():
    return jsonify(database.list_tracked_with_latest())


@app.route('/api/tracked', methods=['POST'])
def api_add_tracked():
    data = request.get_json(force=True)
    title = (data.get('title') or '').strip()
    site_key = data.get('site_key')
    url = data.get('url')

    if not title or site_key not in scraper.SITES or not url:
        return jsonify({"error": "title, site_key and url are required"}), 400

    game_id = database.add_tracked_game(title, site_key, url)

    # Take an immediate first snapshot so the row isn't empty until the next scheduled run.
    result = scraper.scrape_single_page(site_key, url)
    database.record_snapshot(game_id, result["views"])

    return jsonify({"id": game_id, "status": "tracked"})


@app.route('/api/tracked/<int:game_id>', methods=['DELETE'])
def api_delete_tracked(game_id):
    database.delete_tracked_game(game_id)
    return jsonify({"status": "deleted"})


@app.route('/api/tracked/<int:game_id>/refresh', methods=['POST'])
def api_refresh_one(game_id):
    game = database.get_game(game_id)
    if not game:
        return jsonify({"error": "not found"}), 404
    result = scraper.scrape_single_page(game["source"], game["url"])
    database.record_snapshot(game_id, result["views"])
    return jsonify({"views": result["views"]})


@app.route('/api/refresh-all', methods=['POST'])
def api_refresh_all():
    refresh_all_tracked()
    return jsonify({"status": "refreshed"})


@app.route('/api/history/<int:game_id>')
def api_history(game_id):
    return jsonify(database.get_history(game_id))


if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)  # reloader off: avoids starting the scheduler twice
