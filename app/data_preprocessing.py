
import json
import os
from pathlib import Path

import joblib
import pandas as pd
import psycopg
from dotenv import load_dotenv
from sklearn.preprocessing import MultiLabelBinarizer


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
OUTPUT_FILE = PROCESSED_DATA_DIR / "training_data.joblib"

# Load environment variables
load_dotenv(BASE_DIR / ".env")


def get_connection():
    """Create and return a PostgreSQL database connection."""

    required_variables = [
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]

    missing_variables = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing_variables:
        raise EnvironmentError(
            f"Missing environment variables: {', '.join(missing_variables)}"
        )

    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5434"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def load_feedback_data():
    """Load user preferences and destination feedback directly from PostgreSQL."""

    query = """
        SELECT
            f.user_id,
            f.destination_id,
            f.feedback_label,
            d.destination_name,
            d.country,
            tp.age_range,
            tp.budget_level,
            tp.season,
            tp.experience_preferences,
            tp.scenery_preferences,
            tp.activity_level,
            tp.safety_preference,
            tp.popularity_preference,
            tp.region_preferences
        FROM destination_feedback AS f
        JOIN travel_preferences AS tp
            ON tp.user_id = f.user_id
        JOIN destinations AS d
            ON d.destination_id = f.destination_id
        WHERE f.feedback_label IN (0, 1)
          AND f.feedback_source = 'dataset'
        ORDER BY f.user_id, f.destination_id;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            records = cursor.fetchall()
            columns = [column.name for column in cursor.description]

    if not records:
        raise ValueError("No feedback records were found in the database.")

    data = pd.DataFrame.from_records(records, columns=columns)

    print(f"Loaded {len(data):,} feedback records from PostgreSQL.")

    return data


def normalize_values(value):
    """Convert a JSON value into a consistent list of strings."""

    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value if item is not None]

    if isinstance(value, dict):
        return []

    if isinstance(value, str):
        try:
            parsed_value = json.loads(value)

            if isinstance(parsed_value, list):
                return [
                    str(item)
                    for item in parsed_value
                    if item is not None
                ]

            if parsed_value is not None:
                return [str(parsed_value)]

        except json.JSONDecodeError:
            return [value]

    return [str(value)]


def build_feature_tokens(row):
    """Convert one user's preferences and destination into feature tokens."""

    tokens = []

    preference_fields = {
        "age_range": "age",
        "budget_level": "budget",
        "season": "season",
        "experience_preferences": "experience",
        "scenery_preferences": "scenery",
        "activity_level": "activity",
        "safety_preference": "safety",
        "popularity_preference": "popularity",
    }

    for column, feature_name in preference_fields.items():
        selected_values = normalize_values(row[column])

        for value in selected_values:
            tokens.append(f"{feature_name}_{value}")

    # Process regional preferences stored as a JSON object.
    region_preferences = row["region_preferences"]

    if isinstance(region_preferences, str):
        try:
            region_preferences = json.loads(region_preferences)
        except json.JSONDecodeError:
            region_preferences = {}

    if isinstance(region_preferences, dict):
        region_modes = normalize_values(
            region_preferences.get("form_r")
        )

        region_codes = normalize_values(
            region_preferences.get("form_rr")
        )

        for value in region_modes:
            tokens.append(f"region_mode_{value}")

        for value in region_codes:
            tokens.append(f"region_{value}")

    # Add destination information.
    country = row["country"]

    if pd.notna(country):
        tokens.append(f"country_{country}")

    tokens.append(f"destination_{row['destination_id']}")

    return tokens


def prepare_features(data):
    """Convert preference data into a sparse numerical feature matrix."""

    print("Converting travel preferences into numerical features...")

    feature_tokens = data.apply(build_feature_tokens, axis=1).tolist()

    # MultiLabelBinarizer converts selected preferences into binary features.
    binarizer = MultiLabelBinarizer(sparse_output=True)

    feature_matrix = binarizer.fit_transform(feature_tokens)

    target = data["feedback_label"].astype("int8").to_numpy()

    # Keep destination and user information separately for later recommendations.
    metadata = data[
        [
            "user_id",
            "destination_id",
            "destination_name",
            "country",
            "feedback_label",
        ]
    ].copy()

    print(f"Number of records: {feature_matrix.shape[0]:,}")
    print(f"Number of features: {feature_matrix.shape[1]:,}")
    print(f"Number of positive labels: {(target == 1).sum():,}")
    print(f"Number of negative labels: {(target == 0).sum():,}")

    return feature_matrix, target, metadata, binarizer


def save_processed_data(feature_matrix, target, metadata, binarizer):
    """Save the processed dataset and feature encoder for model training."""

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    processed_data = {
        "X": feature_matrix,
        "y": target,
        "metadata": metadata,
        "feature_binarizer": binarizer,
    }

    joblib.dump(processed_data, OUTPUT_FILE, compress=3)

    print(f"Processed data saved to: {OUTPUT_FILE}")


def prepare_data():
    """Run the complete data preprocessing workflow."""

    print("Starting data preprocessing...")

    data = load_feedback_data()

    feature_matrix, target, metadata, binarizer = prepare_features(data)

    save_processed_data(
        feature_matrix,
        target,
        metadata,
        binarizer,
    )

    print("Data preprocessing completed successfully!")


if __name__ == "__main__":
    prepare_data()
