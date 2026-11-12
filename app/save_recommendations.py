
from pathlib import Path

import joblib
import pandas as pd

from sklearn.model_selection import GroupShuffleSplit

from .data_preprocessing import (
    build_feature_tokens,
    get_connection,
)


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

PROCESSED_DATA_FILE = (
    BASE_DIR / "data" / "processed" / "training_data.joblib"
)

MODEL_FILE = BASE_DIR / "models" / "random_forest_model.joblib"

MODEL_VERSION = "random_forest_v1"

# Generate recommendations for a manageable number of test users.
MAX_USERS = 100
TOP_N = 10


def load_model_and_data():
    """Load the trained model and preprocessed dataset."""

    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            "Trained model not found. Run model training first."
        )

    if not PROCESSED_DATA_FILE.exists():
        raise FileNotFoundError(
            "Processed dataset not found. Run preprocessing first."
        )

    model_data = joblib.load(MODEL_FILE)
    processed_data = joblib.load(PROCESSED_DATA_FILE)

    model = model_data["model"]
    X = processed_data["X"]
    y = processed_data["y"]
    metadata = processed_data["metadata"]
    binarizer = processed_data["feature_binarizer"]

    print("Trained model and processed data loaded successfully.")

    return model, X, y, metadata, binarizer


def get_test_user_ids(X, y, metadata):
    """Recreate the test split and select a limited number of users."""

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.20,
        random_state=42,
    )

    _, test_indices = next(
        splitter.split(
            X,
            y,
            groups=metadata["user_id"],
        )
    )

    test_user_ids = (
        metadata.iloc[test_indices]["user_id"]
        .drop_duplicates()
        .sort_values()
        .head(MAX_USERS)
        .tolist()
    )

    test_user_ids = [int(user_id) for user_id in test_user_ids]

    print(f"Selected test users: {len(test_user_ids):,}")

    return test_user_ids


def load_candidate_destinations(user_ids):
    """Load destinations that users have not previously rated."""

    query = """
        SELECT
            tp.user_id,
            d.destination_id,
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
        FROM travel_preferences AS tp
        CROSS JOIN destinations AS d
        WHERE tp.user_id = ANY(%s)
          AND NOT EXISTS (
              SELECT 1
              FROM destination_feedback AS f
              WHERE f.user_id = tp.user_id
                AND f.destination_id = d.destination_id
                AND f.feedback_source = 'dataset'
          )
        ORDER BY tp.user_id, d.destination_id;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (user_ids,))
            records = cursor.fetchall()
            columns = [
                column.name for column in cursor.description
            ]

    candidate_data = pd.DataFrame.from_records(
        records,
        columns=columns,
    )

    if candidate_data.empty:
        raise ValueError(
            "No new destination candidates were found for these users."
        )

    print(
        f"Candidate destinations loaded: {len(candidate_data):,}"
    )

    return candidate_data


def generate_predictions(
    model,
    binarizer,
    candidate_data,
):
    """Predict positive feedback probabilities for candidate destinations."""

    print("\nGenerating destination predictions...")

    feature_tokens = candidate_data.apply(
        build_feature_tokens,
        axis=1,
    ).tolist()

    feature_matrix = binarizer.transform(feature_tokens)

    positive_class_index = list(model.classes_).index(1)

    probabilities = model.predict_proba(feature_matrix)[
        :, positive_class_index
    ]

    recommendations = candidate_data[
        [
            "user_id",
            "destination_id",
            "destination_name",
            "country",
        ]
    ].copy()

    recommendations["predicted_probability"] = probabilities

    print("Destination predictions generated successfully.")

    return recommendations


def select_top_recommendations(predictions):
    """Select the highest-ranked destinations for each user."""

    predictions = predictions.sort_values(
        by=["user_id", "predicted_probability"],
        ascending=[True, False],
    )

    top_recommendations = (
        predictions.groupby("user_id", group_keys=False)
        .head(TOP_N)
        .copy()
    )

    top_recommendations["rank_position"] = (
        top_recommendations.groupby("user_id")
        .cumcount()
        .add(1)
    )

    print("\nTop recommendations selected.")
    print(
        f"Total recommendations: {len(top_recommendations):,}"
    )

    return top_recommendations


def save_recommendations(recommendations):
    """Save ranked recommendations into PostgreSQL."""

    insert_query = """
        INSERT INTO recommendations (
            user_id,
            destination_id,
            model_version,
            predicted_probability,
            rank_position
        )
        VALUES (%s, %s, %s, %s, %s);
    """

    user_ids = [
        int(user_id)
        for user_id in recommendations["user_id"].unique()
    ]

    records = []

    for row in recommendations.itertuples(index=False):
        records.append(
            (
                int(row.user_id),
                int(row.destination_id),
                MODEL_VERSION,
                round(float(row.predicted_probability), 5),
                int(row.rank_position),
            )
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            # Remove previous results from this model version for these users.
            cursor.execute(
                """
                DELETE FROM recommendations
                WHERE model_version = %s
                  AND user_id = ANY(%s);
                """,
                (MODEL_VERSION, user_ids),
            )

            cursor.executemany(insert_query, records)

    print(
        f"\nSaved {len(records):,} recommendations to PostgreSQL."
    )


def display_recommendations(recommendations):
    """Display a sample of generated recommendations."""

    print("\nSample Recommendations")
    print("-" * 60)

    sample = recommendations.head(10)

    for row in sample.itertuples(index=False):
        probability = row.predicted_probability * 100

        print(
            f"User: {row.user_id} | "
            f"Rank: {row.rank_position} | "
            f"Destination: {row.destination_name}, {row.country} | "
            f"Probability: {probability:.2f}%"
        )


def main():
    """Run the recommendation generation and database storage workflow."""

    print("Starting recommendation generation...")

    model, X, y, metadata, binarizer = load_model_and_data()

    user_ids = get_test_user_ids(X, y, metadata)

    candidate_data = load_candidate_destinations(user_ids)

    predictions = generate_predictions(
        model,
        binarizer,
        candidate_data,
    )

    recommendations = select_top_recommendations(predictions)

    display_recommendations(recommendations)

    save_recommendations(recommendations)

    print("\nRecommendation generation completed successfully!")


if __name__ == "__main__":
    main()
