
from pathlib import Path

import joblib
import pandas as pd

from flask import Blueprint, jsonify, current_app, request

from app.database import get_user_recommendations
from app.data_preprocessing import build_feature_tokens, get_connection


api = Blueprint("api", __name__, url_prefix="/api")

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_FILE = BASE_DIR / "models" / "random_forest_model.joblib"

PROCESSED_DATA_FILE = (
    BASE_DIR / "data" / "processed" / "training_data.joblib"
)


def load_recommendation_model():
    """Load the existing trained model and feature encoder."""

    if not MODEL_FILE.exists():
        raise FileNotFoundError("Trained model file was not found.")

    if not PROCESSED_DATA_FILE.exists():
        raise FileNotFoundError("Processed training data was not found.")

    model_data = joblib.load(MODEL_FILE)
    processed_data = joblib.load(PROCESSED_DATA_FILE)

    model = model_data["model"]
    binarizer = processed_data["feature_binarizer"]

    return model, binarizer


def get_form_list(data, field_name):
    """Read a preference field as a list of strings."""

    value = data.get(field_name, [])

    if value is None:
        return []

    if not isinstance(value, list):
        value = [value]

    return [
        str(item)
        for item in value
        if item is not None
    ]


def get_candidate_destinations(region_codes=None):
    """Load destinations, optionally filtered by selected regions."""

    query = """
        SELECT
            destination_id,
            destination_name,
            country,
            region
        FROM destinations
        WHERE destination_id IS NOT NULL
          AND destination_name IS NOT NULL
    """

    params = []

    if region_codes:
        placeholders = ", ".join(
            ["%s"] * len(region_codes)
        )

        query += f" AND region IN ({placeholders})"
        params.extend(region_codes)

    query += " ORDER BY destination_id"

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)

            records = cursor.fetchall()

            columns = [
                column.name
                for column in cursor.description
            ]

    return pd.DataFrame.from_records(
        records,
        columns=columns
    )


def select_balanced_recommendations(
    candidates,
    selected_regions=None,
    limit=10
):
    """
    Select recommendations fairly across selected regions.

    The model probabilities are not changed.
    Only the number of recommendations per region is balanced.
    """

    if candidates.empty:
        return candidates.copy()

    # If no specific regions were selected,
    # return the globally highest-scoring destinations.

    if not selected_regions:
        return (
            candidates.sort_values(
                by="predicted_probability",
                ascending=False
            )
            .head(limit)
            .copy()
        )

    selected_regions = list(dict.fromkeys(selected_regions))

    region_count = len(selected_regions)

    base_quota = limit // region_count
    remainder = limit % region_count

    selected_groups = []

    # First, take an approximately equal number
    # of destinations from every selected region.

    for index, region in enumerate(selected_regions):

        quota = base_quota

        if index < remainder:
            quota += 1

        region_candidates = candidates[
            candidates["region"] == region
        ].sort_values(
            by="predicted_probability",
            ascending=False
        )

        selected_groups.append(
            region_candidates.head(quota)
        )

    balanced = pd.concat(
        selected_groups,
        ignore_index=True
    )

    # If a region did not have enough destinations,
    # fill the remaining places from other selected regions.

    if len(balanced) < limit:

        remaining_candidates = candidates[
            ~candidates["destination_id"].isin(
                balanced["destination_id"]
            )
        ]

        remaining_candidates = remaining_candidates.sort_values(
            by="predicted_probability",
            ascending=False
        )

        needed = limit - len(balanced)

        extra = remaining_candidates.head(needed)

        balanced = pd.concat(
            [balanced, extra],
            ignore_index=True
        )

    # Keep the final list ordered by model probability.

    return (
        balanced.sort_values(
            by="predicted_probability",
            ascending=False
        )
        .head(limit)
        .copy()
    )


@api.get("/recommendations/<int:user_id>")
def recommendations(user_id):
    """Return previously saved recommendations for a user."""

    try:
        results = get_user_recommendations(user_id)

        if not results:
            return jsonify({
                "success": True,
                "user_id": user_id,
                "count": 0,
                "recommendations": [],
                "message": "No recommendations found for this user."
            }), 200

        return jsonify({
            "success": True,
            "user_id": user_id,
            "count": len(results),
            "recommendations": results
        }), 200

    except Exception:

        current_app.logger.exception(
            "Failed to retrieve recommendations."
        )

        return jsonify({
            "success": False,
            "message": "An error occurred while retrieving recommendations."
        }), 500


@api.post("/recommendations")
def recommend_from_preferences():
    """Generate recommendations directly from website preferences."""

    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "success": False,
                "message": "Invalid request data."
            }), 400

        # Read user preferences.

        age_range = get_form_list(data, "age_range")
        budget_level = get_form_list(data, "budget_level")
        season = get_form_list(data, "season")

        experience = get_form_list(
            data, "experience_preferences"
        )

        scenery = get_form_list(
            data, "scenery_preferences"
        )

        activity = get_form_list(data, "activity_level")
        safety = get_form_list(data, "safety_preference")
        popularity = get_form_list(data, "popularity_preference")

        region_mode = get_form_list(data, "form_r")
        region_codes = get_form_list(data, "form_rr")

        # Validate required preferences.

        required_preferences = {
            "age_range": age_range,
            "budget_level": budget_level,
            "season": season,
            "experience_preferences": experience,
            "scenery_preferences": scenery,
            "activity_level": activity,
            "safety_preference": safety,
            "popularity_preference": popularity,
            "form_r": region_mode
        }

        missing_fields = [
            field
            for field, values in required_preferences.items()
            if not values
        ]

        if missing_fields:
            return jsonify({
                "success": False,
                "message": "Some required preferences are missing.",
                "missing_fields": missing_fields
            }), 400

        # Validate region selection.

        if region_mode[0] == "1" and not region_codes:
            return jsonify({
                "success": False,
                "message": "Please select at least one region."
            }), 400

        # Build user preference structure.

        user_preferences = {
            "age_range": age_range,
            "budget_level": budget_level,
            "season": season,
            "experience_preferences": experience,
            "scenery_preferences": scenery,
            "activity_level": activity,
            "safety_preference": safety,
            "popularity_preference": popularity,
            "region_preferences": {
                "form_r": region_mode,
                "form_rr": region_codes
            }
        }

        # Load model and encoder.

        model, binarizer = load_recommendation_model()

        # Filter candidates according to selected regions.

        selected_regions = (
            list(dict.fromkeys(region_codes))
            if region_mode[0] == "1"
            else None
        )

        candidates = get_candidate_destinations(
            selected_regions
        )

        if candidates.empty:
            return jsonify({
                "success": True,
                "count": 0,
                "recommendations": [],
                "message": "No destinations were found for the selected regions."
            }), 200

        # Add user preferences to every candidate.

        for field, value in user_preferences.items():
            candidates[field] = [
                value
            ] * len(candidates)

        # Generate feature tokens.

        feature_tokens = candidates.apply(
            build_feature_tokens,
            axis=1
        ).tolist()

        # Transform features using the saved encoder.

        feature_matrix = binarizer.transform(
            feature_tokens
        )

        # Predict positive feedback probability.

        classes = list(model.classes_)

        if 1 not in classes:
            raise ValueError(
                "The trained model does not contain positive class 1."
            )

        positive_class_index = classes.index(1)

        probabilities = model.predict_proba(
            feature_matrix
        )[:, positive_class_index]

        candidates["predicted_probability"] = probabilities

        # Select balanced recommendations.

        recommendations = select_balanced_recommendations(
            candidates,
            selected_regions=selected_regions,
            limit=10
        )

        recommendations["rank_position"] = range(
            1,
            len(recommendations) + 1
        )

        # Prepare JSON response.

        result = []

        for row in recommendations.itertuples(index=False):

            result.append({
                "destination_id": int(row.destination_id),
                "destination_name": row.destination_name,
                "country": row.country,
                "predicted_probability": round(
                    float(row.predicted_probability),
                    5
                ),
                "rank_position": int(row.rank_position)
            })

        return jsonify({
            "success": True,
            "count": len(result),
            "recommendations": result
        }), 200

    except Exception:

        current_app.logger.exception(
            "Failed to generate recommendations from preferences."
        )

        return jsonify({
            "success": False,
            "message": "An error occurred while generating recommendations."
        }), 500
