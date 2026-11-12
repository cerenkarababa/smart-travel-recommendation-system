
import ast
import json
import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv


# Define project paths
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATASET_PATH = BASE_DIR / "data" / "raw" / "travel_preferences.csv"
DESTINATIONS_PATH = BASE_DIR / "data" / "raw" / "destination_ids.txt"


def load_dataset():
    """Load the original dataset and destination list."""

    users_df = pd.read_csv(DATASET_PATH)

    with open(DESTINATIONS_PATH, "r", encoding="utf-8") as file:
        destination_lines = file.read().splitlines()

    print("Dataset loaded successfully!")
    print(f"Number of user records: {len(users_df):,}")
    print(f"Number of destinations: {len(destination_lines):,}")
    print(f"Number of columns: {len(users_df.columns)}")

    return users_df, destination_lines


def parse_destination_ids(value):
    """Convert a destination list into unique integer IDs."""

    if pd.isna(value):
        return []

    try:
        parsed = ast.literal_eval(value)

        if not isinstance(parsed, list):
            return []

        return list(dict.fromkeys(int(item) for item in parsed))

    except (ValueError, SyntaxError, TypeError):
        return []


def parse_json_list(value):
    """Convert an encoded list into a JSON array."""

    if pd.isna(value):
        return None

    try:
        parsed = ast.literal_eval(value) if isinstance(value, str) else value

        if not isinstance(parsed, list):
            return None

        return json.dumps([str(item) for item in parsed])

    except (ValueError, SyntaxError, TypeError):
        return None


def prepare_feedback(users_df):
    """Clean feedback and exclude conflicting evaluations."""

    feedback_records = []
    conflict_count = 0

    for _, row in users_df.iterrows():

        user_id = str(row["id"])

        feedback_groups = {
            1: parse_destination_ids(row["yes_swipes"]),
            0: parse_destination_ids(row["no_swipes"]),
            2: parse_destination_ids(row["maybe_swipes"])
        }

        destination_groups = {}

        for label, destination_ids in feedback_groups.items():
            for destination_id in destination_ids:
                destination_groups.setdefault(destination_id, []).append(label)

        conflicting_ids = {
            destination_id
            for destination_id, labels in destination_groups.items()
            if len(labels) > 1
        }

        conflict_count += len(conflicting_ids)

        for label, destination_ids in feedback_groups.items():
            for destination_id in destination_ids:

                if destination_id not in conflicting_ids:
                    feedback_records.append((
                        user_id,
                        str(destination_id),
                        label
                    ))

    feedback_df = pd.DataFrame(
        feedback_records,
        columns=[
            "source_user_key",
            "source_destination_key",
            "feedback_label"
        ]
    )

    print("\nFeedback cleaning completed!")
    print(f"Clean feedback records: {len(feedback_df):,}")
    print(f"Conflicting pairs excluded: {conflict_count:,}")

    for label, name in [(1, "Yes"), (0, "No"), (2, "Maybe")]:
        count = (feedback_df["feedback_label"] == label).sum()
        print(f"{name} records: {count:,}")

    return feedback_df


def prepare_destinations(destination_lines):
    """Convert destination lines into database records."""

    records = []

    for index, line in enumerate(destination_lines):

        line = line.strip()

        if not line:
            continue

        source_key, separator, destination_text = line.partition(" ")

        if separator and source_key.isdigit():
            destination_id = source_key
            line = destination_text.strip()
        else:
            destination_id = str(index)

        if "," in line:
            destination_name, country = line.rsplit(",", 1)
            destination_name = destination_name.strip()
            country = country.strip()
        else:
            destination_name = line
            country = None

        records.append((
            destination_id,
            destination_name,
            country
        ))

    return records


def prepare_profile(row):
    """Preserve original dataset fields as JSON."""

    profile = {}

    for column in row.index:

        if column in [
            "id",
            "yes_swipes",
            "no_swipes",
            "maybe_swipes"
        ]:
            continue

        value = row[column]

        if pd.isna(value):
            profile[column] = None
        elif isinstance(value, str):
            try:
                parsed = ast.literal_eval(value)

                if isinstance(parsed, list):
                    profile[column] = parsed
                else:
                    profile[column] = value

            except (ValueError, SyntaxError):
                profile[column] = value
        else:
            profile[column] = value

    return json.dumps(profile, default=str)


def get_connection():
    """Create a PostgreSQL connection."""

    required_variables = [
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD"
    ]

    missing_variables = [
        variable for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing_variables:
        raise ValueError(
            "Missing environment variables: "
            + ", ".join(missing_variables)
        )

    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5434"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )


def import_data(users_df, destination_lines, feedback_df):
    """Import all prepared records into PostgreSQL."""

    destination_records = prepare_destinations(destination_lines)

    print("\nPreparing database import...")

    with get_connection() as conn:

        with conn.cursor() as cur:

            # Prevent accidental duplicate preference imports
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM users),
                    (SELECT COUNT(*) FROM destinations),
                    (SELECT COUNT(*) FROM travel_preferences),
                    (SELECT COUNT(*) FROM destination_feedback);
            """)

            existing_counts = cur.fetchone()

            if any(count > 0 for count in existing_counts):
                raise RuntimeError(
                    "The database already contains records. "
                    "Import cancelled to prevent duplicate data."
                )

            # Create temporary staging tables
            cur.execute("""
                CREATE TEMP TABLE stg_users (
                    source_user_key TEXT PRIMARY KEY
                ) ON COMMIT DROP;

                CREATE TEMP TABLE stg_destinations (
                    source_destination_key TEXT PRIMARY KEY,
                    destination_name TEXT NOT NULL,
                    country TEXT
                ) ON COMMIT DROP;

                CREATE TEMP TABLE stg_preferences (
                    source_user_key TEXT PRIMARY KEY,
                    age_range TEXT,
                    budget_level TEXT,
                    season TEXT,
                    experience_preferences TEXT,
                    scenery_preferences TEXT,
                    activity_level TEXT,
                    safety_preference TEXT,
                    popularity_preference TEXT,
                    region_preferences TEXT,
                    source_profile TEXT
                ) ON COMMIT DROP;

                CREATE TEMP TABLE stg_feedback (
                    source_user_key TEXT,
                    source_destination_key TEXT,
                    feedback_label SMALLINT
                ) ON COMMIT DROP;
            """)

            # Stage users
            print("Staging users...")

            with cur.copy("""
                COPY stg_users (source_user_key) FROM STDIN
            """) as copy:

                for user_id in users_df["id"].astype(str):
                    copy.write_row((user_id,))

            # Stage destinations
            print("Staging destinations...")

            with cur.copy("""
                COPY stg_destinations (
                    source_destination_key,
                    destination_name,
                    country
                ) FROM STDIN
            """) as copy:

                for record in destination_records:
                    copy.write_row(record)

            # Stage user preferences
            print("Staging preferences...")

            with cur.copy("""
                COPY stg_preferences (
                    source_user_key,
                    age_range,
                    budget_level,
                    season,
                    experience_preferences,
                    scenery_preferences,
                    activity_level,
                    safety_preference,
                    popularity_preference,
                    region_preferences,
                    source_profile
                ) FROM STDIN
            """) as copy:

                for _, row in users_df.iterrows():

                    user_id = str(row["id"])

                    form_r = parse_json_list(row["form_r"])
                    form_rr = parse_json_list(row["form_rr"])

                    region_data = {
                        "form_r": json.loads(form_r) if form_r else None,
                        "form_rr": json.loads(form_rr) if form_rr else None
                    }

                    if all(value is None for value in region_data.values()):
                        region_json = None
                    else:
                        region_json = json.dumps(region_data)

                    copy.write_row((
                        user_id,
                        parse_json_list(row["form_a"]),
                        parse_json_list(row["form_b"]),
                        parse_json_list(row["form_c"]),
                        parse_json_list(row["form_f"]),
                        parse_json_list(row["form_g"]),
                        parse_json_list(row["form_h"]),
                        parse_json_list(row["form_i"]),
                        parse_json_list(row["form_j"]),
                        region_json,
                        prepare_profile(row)
                    ))

            # Stage cleaned feedback
            print("Staging feedback...")

            with cur.copy("""
                COPY stg_feedback (
                    source_user_key,
                    source_destination_key,
                    feedback_label
                ) FROM STDIN
            """) as copy:

                for record in feedback_df.itertuples(index=False, name=None):
                    copy.write_row(record)

            # Insert users
            print("Importing users...")

            cur.execute("""
                INSERT INTO users (source_user_key)
                SELECT source_user_key
                FROM stg_users;
            """)

            # Insert destinations
            print("Importing destinations...")

            cur.execute("""
                INSERT INTO destinations (
                    source_destination_key,
                    destination_name,
                    country
                )
                SELECT
                    source_destination_key,
                    destination_name,
                    country
                FROM stg_destinations;
            """)

            # Insert travel preferences
            print("Importing travel preferences...")

            cur.execute("""
                INSERT INTO travel_preferences (
                    user_id,
                    age_range,
                    budget_level,
                    season,
                    experience_preferences,
                    scenery_preferences,
                    activity_level,
                    safety_preference,
                    popularity_preference,
                    region_preferences,
                    source_profile,
                    created_at
                )
                SELECT
                    u.user_id,
                    NULLIF(p.age_range, '')::jsonb,
                    NULLIF(p.budget_level, '')::jsonb,
                    NULLIF(p.season, '')::jsonb,
                    NULLIF(p.experience_preferences, '')::jsonb,
                    NULLIF(p.scenery_preferences, '')::jsonb,
                    NULLIF(p.activity_level, '')::jsonb,
                    NULLIF(p.safety_preference, '')::jsonb,
                    NULLIF(p.popularity_preference, '')::jsonb,
                    NULLIF(p.region_preferences, '')::jsonb,
                    NULLIF(p.source_profile, '')::jsonb,
                    NOW()
                FROM stg_preferences p
                JOIN users u
                    ON u.source_user_key = p.source_user_key;
            """)

            # Insert feedback with internal database identifiers
            print("Importing feedback records...")

            cur.execute("""
                INSERT INTO destination_feedback (
                    user_id,
                    destination_id,
                    feedback_label,
                    feedback_source
                )
                SELECT
                    u.user_id,
                    d.destination_id,
                    f.feedback_label,
                    'dataset'
                FROM stg_feedback f
                JOIN users u
                    ON u.source_user_key = f.source_user_key
                JOIN destinations d
                    ON d.source_destination_key = f.source_destination_key;
            """)

            # Display final database counts
            print("\nDatabase import completed successfully!")

            cur.execute("""
                SELECT 'users' AS table_name, COUNT(*) FROM users
                UNION ALL
                SELECT 'destinations', COUNT(*) FROM destinations
                UNION ALL
                SELECT 'travel_preferences', COUNT(*) FROM travel_preferences
                UNION ALL
                SELECT 'destination_feedback', COUNT(*) FROM destination_feedback;
            """)

            for table_name, count in cur.fetchall():
                print(f"{table_name}: {count:,}")


if __name__ == "__main__":

    users_df, destination_lines = load_dataset()

    feedback_df = prepare_feedback(users_df)

    import_data(
        users_df,
        destination_lines,
        feedback_df
    )
