from flask import Flask, render_template
from dotenv import load_dotenv
import os

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "development-only")

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
