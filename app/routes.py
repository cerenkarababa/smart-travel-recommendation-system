
from flask import Blueprint, jsonify, current_app

from app.database import get_user_recommendations


api = Blueprint("api", __name__, url_prefix="/api")


@api.get("/recommendations/<int:user_id>")
def recommendations(user_id):
    """Return destination recommendations for a user."""

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
