
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from app.data_preprocessing import get_connection


API_URL = "https://commons.wikimedia.org/w/api.php"

OUTPUT_DIR = Path("data/destination_images")
PROGRESS_FILE = OUTPUT_DIR / "commons_progress.csv"

REQUEST_DELAY = 2.5
MAX_RETRIES = 5
MAX_IMAGES_PER_DESTINATION = 3


class HTMLCleaner(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def get_text(self):
        return unescape(" ".join(self.parts)).strip()


def clean_html(value):
    cleaner = HTMLCleaner()
    cleaner.feed(value or "")
    return cleaner.get_text()


def api_request(params):
    params.update({
        "action": "query",
        "format": "json",
        "origin": "*",
        "maxlag": 5
    })

    url = API_URL + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SmartTravelStudentProject/1.0 (educational project)"
        }
    )

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return json.loads(response.read().decode("utf-8"))

        except Exception as error:
            if attempt == MAX_RETRIES - 1:
                raise error

            wait = min(30 * (2 ** attempt), 300)
            print(f"Request error: {error}")
            print(f"Waiting {wait} seconds before retry...")
            time.sleep(wait)

    return {}


def search_images(destination, country):
    data = api_request({
        "generator": "search",
        "gsrsearch": f"{destination} {country}",
        "gsrnamespace": 6,
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": 1200
    })

    pages = data.get("query", {}).get("pages", {})

    ordered_pages = sorted(
        pages.values(),
        key=lambda page: page.get("index", 9999)
    )

    candidates = []

    destination_words = [
        word.lower()
        for word in re.findall(r"[a-zA-ZÀ-ÿ]+", destination)
        if len(word) > 2
    ]

    country_words = [
        word.lower()
        for word in re.findall(r"[a-zA-ZÀ-ÿ]+", country)
        if len(word) > 2
    ]

    for page in ordered_pages:
        title = page.get("title", "")
        title_lower = title.lower()

        image_info = page.get("imageinfo", [{}])[0]
        mime = image_info.get("mime", "")

        # Only accept normal image files.
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            continue

        # Avoid unrelated images.
        destination_matches = sum(
            word in title_lower for word in destination_words
        )

        country_matches = sum(
            word in title_lower for word in country_words
        )

        if destination_matches == 0:
            continue

        metadata = image_info.get("extmetadata", {})

        license_name = clean_html(
            metadata.get("LicenseShortName", {}).get("value", "")
        )

        license_url = metadata.get(
            "LicenseUrl", {}
        ).get("value", "")

        # Do not automatically use images without license information.
        if not license_name:
            continue

        author = clean_html(
            metadata.get("Artist", {}).get("value", "")
        )

        candidates.append({
            "file_name": title,
            "image_url": image_info.get("thumburl", ""),
            "source_page": image_info.get("descriptionurl", ""),
            "author": author,
            "license": license_name,
            "license_url": license_url,
            "score": destination_matches * 10 + country_matches
        })

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return candidates[:MAX_IMAGES_PER_DESTINATION]


def load_completed_keys():
    completed = set()

    if PROGRESS_FILE.exists():
        with PROGRESS_FILE.open(
            newline="", encoding="utf-8"
        ) as file:
            for row in csv.DictReader(file):
                completed.add(row["source_destination_key"])

    return completed


def save_progress(key, destination, country, status):
    file_exists = PROGRESS_FILE.exists()

    with PROGRESS_FILE.open(
        "a", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "source_destination_key",
                "destination",
                "country",
                "status"
            ]
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "source_destination_key": key,
            "destination": destination,
            "country": country,
            "status": status
        })


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    completed = load_completed_keys()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    destination_id,
                    source_destination_key,
                    destination_name,
                    country
                FROM destinations
                ORDER BY destination_id;
            """)

            destinations = cursor.fetchall()

    total = len(destinations)
    saved_count = 0
    skipped_count = 0

    print(f"Total destinations: {total}")
    print(f"Already processed: {len(completed)}")
    print("Starting automatic image search...\n")

    for index, destination in enumerate(destinations, start=1):
        destination_id = int(destination[0])
        source_key = str(destination[1])
        name = destination[2]
        country = destination[3] or ""

        if source_key in completed:
            skipped_count += 1
            continue

        print(f"[{index}/{total}] {name}, {country}")

        try:
            candidates = search_images(name, country)

            if not candidates:
                print("  No suitable licensed image found.")
                save_progress(
                    source_key, name, country, "no_match"
                )
                completed.add(source_key)
                time.sleep(REQUEST_DELAY)
                continue

            with get_connection() as connection:
                with connection.cursor() as cursor:
                    for image_index, candidate in enumerate(candidates):
                        cursor.execute("""
                            INSERT INTO destination_images (
                                destination_id,
                                image_url,
                                source_page,
                                author,
                                license,
                                license_url,
                                is_primary
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """, (
                            destination_id,
                            candidate["image_url"],
                            candidate["source_page"],
                            candidate["author"],
                            candidate["license"],
                            candidate["license_url"],
                            image_index == 0
                        ))

            save_progress(
                source_key, name, country, "saved"
            )

            completed.add(source_key)
            saved_count += 1

            print(
                f"  Saved {len(candidates)} images. "
                f"Primary: {candidates[0]['file_name']}"
            )

        except Exception as error:
            print(f"  Error: {error}")
            print("  This destination will be retried next run.")

        time.sleep(REQUEST_DELAY)

    print("\n------------------------------")
    print("IMAGE SEARCH FINISHED")
    print(f"Total destinations: {total}")
    print(f"Newly saved destinations: {saved_count}")
    print(f"Previously processed: {skipped_count}")
    print(f"Progress file: {PROGRESS_FILE}")
    print("------------------------------")


if __name__ == "__main__":
    main()
