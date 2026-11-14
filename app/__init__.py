
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template

from app.routes import api


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY",
        "development-only"
    )

    app.register_blueprint(api)

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
