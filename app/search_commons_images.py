
import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API_URL = "https://commons.wikimedia.org/w/api.php"

DESTINATIONS = [
    ("Butrint", "Albania"),
    ("Tirana", "Albania"),
    ("Algiers", "Algeria"),
    ("Oran", "Algeria"),
    ("Andorra la Vella", "Andorra"),
]


def commons_request(params):
    params.update({
        "format": "json",
        "origin": "*"
    })

    url = API_URL + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SmartTravelStudentProject/1.0 (educational use)"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def search_images(destination, country):
    search_term = f"{destination} {country}"

    data = commons_request({
        "action": "query",
        "list": "search",
        "srsearch": search_term,
        "srnamespace": 6,
        "srlimit": 5
    })

    results = data.get("query", {}).get("search", [])
    candidates = []

    for result in results:
        title = result["title"]

        details = commons_request({
            "action": "query",
            "prop": "imageinfo",
            "titles": title,
            "iiprop": "url|extmetadata",
            "iiurlwidth": 1200
        })

        pages = details.get("query", {}).get("pages", {})

        for page in pages.values():
            image_info = page.get("imageinfo", [{}])[0]
            metadata = image_info.get("extmetadata", {})

            candidates.append({
                "destination": destination,
                "country": country,
                "file_name": title,
                "image_url": image_info.get("thumburl", ""),
                "original_url": image_info.get("url", ""),
                "source_page": image_info.get("descriptionurl", ""),
                "author": metadata.get("Artist", {}).get("value", ""),
                "license": metadata.get("LicenseShortName", {}).get("value", ""),
                "license_url": metadata.get("LicenseUrl", {}).get("value", "")
            })

        time.sleep(0.5)

    return candidates


def main():
    output_dir = Path("data/destination_images")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "commons_test_results.csv"

    all_results = []

    for destination, country in DESTINATIONS:
        print(f"\nSearching: {destination}, {country}")

        try:
            results = search_images(destination, country)
            all_results.extend(results)
            print(f"Found {len(results)} image candidates.")

        except Exception as error:
            print(f"Error: {error}")

        time.sleep(1)

    fieldnames = [
        "destination",
        "country",
        "file_name",
        "image_url",
        "original_url",
        "source_page",
        "author",
        "license",
        "license_url"
    ]

    with output_file.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    print("\n------------------------------")
    print(f"Total candidates: {len(all_results)}")
    print(f"Saved to: {output_file}")
    print("------------------------------")


if __name__ == "__main__":
    main()
