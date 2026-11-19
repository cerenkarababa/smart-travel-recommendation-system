
import csv
import re
import unicodedata
from collections import defaultdict

import psycopg2


# Normalize destination and city names
def normalize(value):
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


# PostgreSQL connection
connection = psycopg2.connect(
    host="localhost",
    port=5434,
    database="smart_travel",
    user="travel_user",
    password="Cerentravel2026"
)

cursor = connection.cursor()


# Load country codes
country_codes = {}

with open(
    "data/geonames/countryInfo.txt",
    encoding="utf-8"
) as file:
    for line in file:
        if line.startswith("#") or not line.strip():
            continue

        columns = line.strip().split("\t")

        if len(columns) > 4:
            country_codes[normalize(columns[4])] = columns[0]


# Country aliases
country_aliases = {
    "Czech Republic": "CZ",
    "Cape Verde": "CV",
    "Ivory Coast": "CI",
    "South Korea": "KR",
    "North Korea": "KP",
    "Russia": "RU",
    "Vietnam": "VN",
    "Laos": "LA",
    "Moldova": "MD",
    "Syria": "SY",
    "Taiwan": "TW",
    "Bolivia": "BO",
    "Tanzania": "TZ",
    "Venezuela": "VE",
    "Brunei": "BN",
    "Iran": "IR",
    "Palestine": "PS"
}

for country, code in country_aliases.items():
    country_codes[normalize(country)] = code


# Load GeoNames records
geonames = defaultdict(list)

with open(
    "data/geonames/cities500.txt",
    encoding="utf-8"
) as file:
    reader = csv.reader(file, delimiter="\t")

    for row in reader:
        if len(row) < 19:
            continue

        name = row[1]
        ascii_name = row[2]
        alternate_names = row[3].split(",")

        latitude = float(row[4])
        longitude = float(row[5])
        feature_code = row[7]
        country_code = row[8]
        population = int(row[14] or 0)

        record = (
            latitude,
            longitude,
            name,
            population,
            feature_code
        )

        names = {
            normalize(name),
            normalize(ascii_name)
        }

        names.update(
            normalize(alias)
            for alias in alternate_names
            if alias
        )

        for normalized_name in names:
            if normalized_name:
                geonames[
                    (country_code, normalized_name)
                ].append(record)


# Get destinations without coordinates
cursor.execute("""
    SELECT destination_id, destination_name, country
    FROM destinations
    WHERE latitude IS NULL OR longitude IS NULL
    ORDER BY destination_id;
""")

destinations = cursor.fetchall()

matched = []
unmatched = []
ambiguous = []


# GeoNames feature codes for major administrative centers
MAJOR_FEATURES = {"PPLC", "PPLA", "PPLA2"}

# Other populated place codes
POPULATED_FEATURES = {"PPL", "PPLX", "PPLA3", "PPLA4"}


for destination_id, name, country in destinations:

    country_code = country_codes.get(normalize(country))

    if not country_code:
        unmatched.append((
            destination_id,
            name,
            country,
            "Country not found"
        ))
        continue

    normalized_name = normalize(name)

    # Exact name match
    results = geonames.get(
        (country_code, normalized_name),
        []
    )

    # Try the part before the comma
    if not results and "," in name:
        base_name = name.split(",")[0].strip()

        results = geonames.get(
            (country_code, normalize(base_name)),
            []
        )

    # Group records by distinct coordinates
    coordinate_groups = defaultdict(list)

    for result in set(results):
        latitude, longitude, matched_name, population, feature_code = result

        coordinate_groups[
            (latitude, longitude)
        ].append(result)

    # No result
    if len(coordinate_groups) == 0:
        unmatched.append((
            destination_id,
            name,
            country,
            "No exact match"
        ))
        continue

    # Only one distinct coordinate
    if len(coordinate_groups) == 1:
        coordinates = next(iter(coordinate_groups))
        candidates = coordinate_groups[coordinates]

        best_result = max(
            candidates,
            key=lambda item: item[3]
        )

        matched.append((
            destination_id,
            name,
            country,
            best_result[0],
            best_result[1],
            best_result[2],
            "Single coordinate match"
        ))
        continue

    # Multiple coordinates: evaluate candidates
    candidates = []

    for coordinates, records in coordinate_groups.items():
        for record in records:
            latitude, longitude, matched_name, population, feature_code = record

            score = 0

            if feature_code == "PPLC":
                score += 100
            elif feature_code == "PPLA":
                score += 80
            elif feature_code == "PPLA2":
                score += 60
            elif feature_code in POPULATED_FEATURES:
                score += 20

            if normalize(matched_name) == normalized_name:
                score += 30

            if population >= 1000000:
                score += 20
            elif population >= 100000:
                score += 10
            elif population >= 10000:
                score += 5

            candidates.append({
                "latitude": latitude,
                "longitude": longitude,
                "name": matched_name,
                "population": population,
                "feature": feature_code,
                "score": score
            })

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    best = candidates[0]
    second = candidates[1]

    # Conservative automatic selection
    if (
        best["feature"] in MAJOR_FEATURES
        and best["score"] >= second["score"] + 30
        and normalize(best["name"]) == normalized_name
    ):
        matched.append((
            destination_id,
            name,
            country,
            best["latitude"],
            best["longitude"],
            best["name"],
            "High-confidence candidate"
        ))

    else:
        ambiguous.append((
            destination_id,
            name,
            country,
            candidates
        ))


# Save matched records
with open(
    "data/geonames/coordinate_matches.csv",
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "destination_id",
        "destination_name",
        "country",
        "latitude",
        "longitude",
        "matched_name",
        "match_reason"
    ])

    writer.writerows(matched)


# Save unmatched records
with open(
    "data/geonames/coordinate_unmatched.csv",
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "destination_id",
        "destination_name",
        "country",
        "reason"
    ])

    writer.writerows(unmatched)


# Save ambiguous records
with open(
    "data/geonames/coordinate_ambiguous.csv",
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.writer(file)

    writer.writerow([
        "destination_id",
        "destination_name",
        "country",
        "possible_matches"
    ])

    for destination_id, name, country, candidates in ambiguous:
        writer.writerow([
            destination_id,
            name,
            country,
            repr(candidates)
        ])


# Print report
print("\n--- COORDINATE MATCHING REPORT ---")
print(f"Total destinations: {len(destinations)}")
print(f"Matched: {len(matched)}")
print(f"Unmatched: {len(unmatched)}")
print(f"Ambiguous: {len(ambiguous)}")

print("\nFirst 15 matches:")

for item in matched[:15]:
    print(
        f"{item[1]}, {item[2]} -> "
        f"{item[3]}, {item[4]} ({item[6]})"
    )

print("\nReports saved in data/geonames/")

cursor.close()
connection.close()
