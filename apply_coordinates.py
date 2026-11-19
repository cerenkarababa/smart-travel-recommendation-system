
import csv
import psycopg2


# Connect to PostgreSQL
connection = psycopg2.connect(
    host="localhost",
    port=5434,
    database="smart_travel",
    user="travel_user",
    password="Cerentravel2026"
)

cursor = connection.cursor()

# Read matched coordinates
with open(
    "data/geonames/coordinate_matches.csv",
    encoding="utf-8"
) as file:

    reader = csv.DictReader(file)
    updates = []

    for row in reader:
        latitude = float(row["latitude"])
        longitude = float(row["longitude"])

        # Validate coordinate ranges
        if not (-90 <= latitude <= 90):
            print("Invalid latitude:", row["destination_name"])
            continue

        if not (-180 <= longitude <= 180):
            print("Invalid longitude:", row["destination_name"])
            continue

        updates.append((
            latitude,
            longitude,
            int(row["destination_id"])
        ))


# Update only destinations without existing coordinates
try:
    cursor.executemany("""
        UPDATE destinations
        SET latitude = %s,
            longitude = %s
        WHERE destination_id = %s
          AND latitude IS NULL
          AND longitude IS NULL;
    """, updates)

    updated_count = cursor.rowcount
    connection.commit()

    print("\n--- DATABASE UPDATE REPORT ---")
    print(f"CSV records: {len(updates)}")
    print(f"Successfully updated: {updated_count}")
    print(f"Not updated: {len(updates) - updated_count}")

except Exception as error:
    connection.rollback()
    print("Update failed:", error)
    raise

finally:
    cursor.close()
    connection.close()
