import os

from flask import jsonify

from app.api import api_bp
from app.services import DiscoveryService


@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "service": "onCamp",
        "college": "Hunter",
        "environment": os.getenv("APP_ENV", "development"),
    })


@api_bp.route("/status", methods=["GET"])
def get_status():
    service = DiscoveryService()
    return jsonify({
        "college": "Hunter",
        "seed_account": service.seed_account,
        "pipeline": service.get_seed_context(),
    })
