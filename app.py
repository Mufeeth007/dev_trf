"""
Main Application Entrypoint for Developer Activity Tracker.
Flask Web Application with REST API endpoints, FerretDB integration, and Redis caching.
"""

import logging
from flask import Flask, render_template, request, jsonify
from pymongo.errors import PyMongoError, ConnectionFailure, ServerSelectionTimeoutError

from config import Config
from ferretdb_client import ferretdb_client
from redis_cache import redis_cache

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.config.from_object(Config)


# ==============================================================================
# Helper Functions
# ==============================================================================

def validate_activity_payload(data: dict, is_update: bool = False):
    """
    Validate incoming activity JSON payload.
    Returns (is_valid, errors_dict_or_none)
    """
    if not isinstance(data, dict):
        return False, {"error": "Request body must be a valid JSON object"}

    errors = {}
    required_fields = ["project_name", "title", "description", "status", "developer_name"]

    if not is_update:
        for field in required_fields:
            val = data.get(field)
            if val is None or not str(val).strip():
                errors[field] = f"Field '{field}' is required and cannot be empty."

    # Validate status if provided
    if "status" in data:
        raw_status = str(data.get("status", "")).strip().capitalize()
        if raw_status not in Config.VALID_STATUSES:
            errors["status"] = (
                f"Invalid status '{data.get('status')}'. Allowed values are: "
                f"{', '.join(Config.VALID_STATUSES)}"
            )

    # Validate string lengths
    if "project_name" in data and len(str(data["project_name"]).strip()) > 100:
        errors["project_name"] = "Project name cannot exceed 100 characters."

    if "title" in data and len(str(data["title"]).strip()) > 150:
        errors["title"] = "Activity title cannot exceed 150 characters."

    if "developer_name" in data and len(str(data["developer_name"]).strip()) > 80:
        errors["developer_name"] = "Developer name cannot exceed 80 characters."

    if "description" in data and len(str(data["description"]).strip()) > 1000:
        errors["description"] = "Description cannot exceed 1000 characters."

    if errors:
        return False, errors
    return True, None


# ==============================================================================
# Web Interface Route
# ==============================================================================

@app.route("/")
def index():
    """Render the dashboard UI."""
    return render_template("index.html")


# ==============================================================================
# Health Check Endpoint
# ==============================================================================

@app.route("/api/health", methods=["GET"])
def health_check():
    """
    Display application, FerretDB, and Redis connection status.
    """
    ferret_ok, ferret_err = ferretdb_client.check_connection()
    redis_ok, redis_err = redis_cache.check_connection()

    if ferret_ok and redis_ok:
        overall_status = "healthy"
        status_code = 200
    elif ferret_ok and not redis_ok:
        # FerretDB works, Redis down -> App can still function with FerretDB directly
        overall_status = "degraded"
        status_code = 200
    else:
        # FerretDB is offline -> Primary database unavailable
        overall_status = "unhealthy"
        status_code = 503

    return jsonify({
        "status": overall_status,
        "app": "running",
        "ferretdb": {
            "status": "connected" if ferret_ok else "disconnected",
            "database": Config.FERRETDB_DB_NAME,
            "collection": Config.FERRETDB_COLLECTION_NAME,
            "uri": Config.FERRETDB_URI,
            "error": ferret_err,
        },
        "redis": {
            "status": "connected" if redis_ok else "disconnected",
            "url": Config.REDIS_URL,
            "ttl": Config.CACHE_TTL,
            "error": redis_err,
        },
    }), status_code


# ==============================================================================
# Dashboard Statistics Endpoint
# ==============================================================================

@app.route("/api/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    """
    Retrieve activity statistics (total, success, pending, failed).
    Checks Redis cache first; falls back to FerretDB on cache miss.
    """
    # 1. Try fetching from Redis cache
    cached_stats = redis_cache.get_cached_stats()
    if cached_stats is not None:
        return jsonify({
            "success": True,
            "data": cached_stats,
            "cached": True,
            "source": "Redis",
        }), 200

    # 2. Cache miss: Fetch from FerretDB
    try:
        stats = ferretdb_client.get_dashboard_stats()
    except (ConnectionFailure, ServerSelectionTimeoutError, PyMongoError) as err:
        logger.error("FerretDB error while fetching stats: %s", err)
        return jsonify({
            "success": False,
            "error": "FerretDB is unavailable. Please verify FerretDB service is running.",
            "details": str(err),
        }), 503

    # 3. Store fresh data in Redis cache
    redis_cache.set_cached_stats(stats)

    return jsonify({
        "success": True,
        "data": stats,
        "cached": False,
        "source": "FerretDB",
    }), 200


# ==============================================================================
# Activities REST API Endpoints
# ==============================================================================

@app.route("/api/activities", methods=["GET"])
def get_activities():
    """
    Retrieve all activities with optional search query, status filter, and sorting.
    Caches results in Redis with a 60-second TTL.
    """
    search_query = request.args.get("search") or request.args.get("q") or ""
    status = request.args.get("status") or "all"
    sort_order = request.args.get("sort") or "newest"

    # Build cache key for this query
    cache_key = redis_cache.build_activities_cache_key(
        search_query=search_query,
        status=status,
        sort_order=sort_order,
    )

    # 1. Try Redis cache
    cached_data = redis_cache.get_cached_activities(cache_key)
    if cached_data is not None:
        return jsonify({
            "success": True,
            "data": cached_data,
            "count": len(cached_data),
            "cached": True,
            "source": "Redis",
        }), 200

    # 2. Fetch from FerretDB
    try:
        activities = ferretdb_client.get_activities(
            search_query=search_query,
            status=status,
            sort_order=sort_order,
        )
    except (ConnectionFailure, ServerSelectionTimeoutError, PyMongoError) as err:
        logger.error("FerretDB error while retrieving activities: %s", err)
        return jsonify({
            "success": False,
            "error": "FerretDB is unavailable. Cannot retrieve activities.",
            "details": str(err),
        }), 503

    # 3. Cache fresh results in Redis
    redis_cache.set_cached_activities(cache_key, activities)

    return jsonify({
        "success": True,
        "data": activities,
        "count": len(activities),
        "cached": False,
        "source": "FerretDB",
    }), 200


@app.route("/api/activities/<id>", methods=["GET"])
def get_activity_by_id(id):
    """
    Retrieve one activity by its ID.
    Checks Redis cache first, then FerretDB.
    """
    # 1. Check Redis cache
    cached_item = redis_cache.get_cached_activity(id)
    if cached_item is not None:
        return jsonify({
            "success": True,
            "data": cached_item,
            "cached": True,
            "source": "Redis",
        }), 200

    # 2. Fetch from FerretDB
    try:
        activity = ferretdb_client.get_activity_by_id(id)
    except (ConnectionFailure, ServerSelectionTimeoutError, PyMongoError) as err:
        logger.error("FerretDB error fetching activity %s: %s", id, err)
        return jsonify({
            "success": False,
            "error": "FerretDB is unavailable. Cannot retrieve activity.",
            "details": str(err),
        }), 503

    if not activity:
        return jsonify({
            "success": False,
            "error": f"Activity with ID '{id}' was not found.",
        }), 404

    # 3. Store in Redis cache
    redis_cache.set_cached_activity(id, activity)

    return jsonify({
        "success": True,
        "data": activity,
        "cached": False,
        "source": "FerretDB",
    }), 200


@app.route("/api/activities", methods=["POST"])
def create_activity():
    """
    Add a new developer activity.
    Saves permanently to FerretDB and invalidates Redis cache.
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "success": False,
            "error": "Invalid request. JSON body is required.",
        }), 400

    is_valid, error_details = validate_activity_payload(payload, is_update=False)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": "Validation failed for required fields.",
            "details": error_details,
        }), 400

    try:
        created_activity = ferretdb_client.insert_activity(payload)
    except (ConnectionFailure, ServerSelectionTimeoutError, PyMongoError) as err:
        logger.error("FerretDB error while inserting activity: %s", err)
        return jsonify({
            "success": False,
            "error": "Failed to save activity. FerretDB is unavailable.",
            "details": str(err),
        }), 503

    # Clear relevant Redis cached data after adding activity
    redis_cache.invalidate_activity_cache()

    return jsonify({
        "success": True,
        "message": "Activity recorded successfully.",
        "data": created_activity,
    }), 201


@app.route("/api/activities/<id>", methods=["PUT"])
def update_activity(id):
    """
    Update an existing activity by ID.
    Updates in FerretDB and clears relevant Redis cached data.
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "success": False,
            "error": "Invalid request. JSON body is required.",
        }), 400

    is_valid, error_details = validate_activity_payload(payload, is_update=True)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": "Validation failed for updated fields.",
            "details": error_details,
        }), 400

    try:
        updated_activity = ferretdb_client.update_activity(id, payload)
    except (ConnectionFailure, ServerSelectionTimeoutError, PyMongoError) as err:
        logger.error("FerretDB error updating activity %s: %s", id, err)
        return jsonify({
            "success": False,
            "error": "Failed to update activity. FerretDB is unavailable.",
            "details": str(err),
        }), 503

    if not updated_activity:
        return jsonify({
            "success": False,
            "error": f"Activity with ID '{id}' was not found.",
        }), 404

    # Clear relevant Redis cached data after updating activity
    redis_cache.invalidate_activity_cache(activity_id=id)

    return jsonify({
        "success": True,
        "message": "Activity updated successfully.",
        "data": updated_activity,
    }), 200


@app.route("/api/activities/<id>", methods=["DELETE"])
def delete_activity(id):
    """
    Delete an activity by ID.
    Deletes permanently from FerretDB and clears relevant Redis cached data.
    """
    try:
        deleted = ferretdb_client.delete_activity(id)
    except (ConnectionFailure, ServerSelectionTimeoutError, PyMongoError) as err:
        logger.error("FerretDB error deleting activity %s: %s", id, err)
        return jsonify({
            "success": False,
            "error": "Failed to delete activity. FerretDB is unavailable.",
            "details": str(err),
        }), 503

    if not deleted:
        return jsonify({
            "success": False,
            "error": f"Activity with ID '{id}' was not found.",
        }), 404

    # Clear relevant Redis cached data after deleting activity
    redis_cache.invalidate_activity_cache(activity_id=id)

    return jsonify({
        "success": True,
        "message": "Activity deleted successfully.",
    }), 200


# ==============================================================================
# Error Handlers
# ==============================================================================

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        "success": False,
        "error": "Endpoint or resource not found.",
    }), 404


@app.errorhandler(500)
def internal_server_error(error):
    logger.error("Internal Server Error: %s", error)
    return jsonify({
        "success": False,
        "error": "An internal server error occurred.",
    }), 500


# ==============================================================================
# Run Flask Server
# ==============================================================================

if __name__ == "__main__":
    host = os.environ.get("HOST", Config.HOST)
    port = int(os.environ.get("PORT", Config.PORT))
    print(f"Starting Developer Activity Tracker on http://{host}:{port}")
    print(f"FerretDB target: {Config.FERRETDB_URI} (Database: {Config.FERRETDB_DB_NAME})")
    print(f"Redis target: {Config.REDIS_URL} (TTL: {Config.CACHE_TTL}s)")
    app.run(host=host, port=port, debug=False, use_reloader=False)
