"""
FerretDB Client Module for Developer Activity Tracker.
Connects to FerretDB using pymongo (MongoDB wire protocol).
Provides full CRUD, search, filter, and statistics operations.
"""

import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import MongoClient, ReturnDocument, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError, ConnectionFailure, ServerSelectionTimeoutError

from config import Config


class FerretDBClient:
    """Handles communication with FerretDB."""

    def __init__(self, uri: Optional[str] = None, db_name: Optional[str] = None):
        self.uri = uri or Config.FERRETDB_URI
        self.db_name = db_name or Config.FERRETDB_DB_NAME
        self.collection_name = Config.FERRETDB_COLLECTION_NAME
        self._client: Optional[MongoClient] = None

    def get_client(self) -> MongoClient:
        """Get or initialize the PyMongo client for FerretDB."""
        if self._client is None:
            self._client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=2500,
                connectTimeoutMS=2500,
                socketTimeoutMS=3000,
            )
        return self._client

    def get_database(self):
        """Get the FerretDB database instance."""
        client = self.get_client()
        return client[self.db_name]

    def get_collection(self):
        """Get the activities collection in FerretDB."""
        db = self.get_database()
        return db[self.collection_name]

    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """
        Check if FerretDB is reachable.
        Returns:
            (True, None) if connected.
            (False, error_message) if connection failed.
        """
        try:
            client = self.get_client()
            # Perform a fast ping command against FerretDB
            client.admin.command("ping")
            return True, None
        except (ConnectionFailure, ServerSelectionTimeoutError) as err:
            return False, f"Cannot connect to FerretDB at {self.uri}: {str(err)}"
        except PyMongoError as err:
            return False, f"FerretDB error: {str(err)}"
        except Exception as err:
            return False, f"Unexpected error connecting to FerretDB: {str(err)}"

    @staticmethod
    def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a FerretDB BSON document to a JSON-serializable dictionary."""
        if not doc:
            return {}
        return {
            "id": str(doc.get("_id", "")),
            "project_name": doc.get("project_name", ""),
            "title": doc.get("title", ""),
            "description": doc.get("description", ""),
            "status": doc.get("status", "Pending"),
            "developer_name": doc.get("developer_name", ""),
            "created_at": doc.get("created_at", ""),
            "updated_at": doc.get("updated_at", ""),
        }

    def insert_activity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a new activity record into FerretDB.
        """
        collection = self.get_collection()

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        doc = {
            "project_name": str(data.get("project_name", "")).strip(),
            "title": str(data.get("title", "")).strip(),
            "description": str(data.get("description", "")).strip(),
            "status": str(data.get("status", "Pending")).strip(),
            "developer_name": str(data.get("developer_name", "")).strip(),
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        # Normalize status to title case
        if doc["status"].capitalize() in Config.VALID_STATUSES:
            doc["status"] = doc["status"].capitalize()

        result = collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return self.serialize_doc(doc)

    def get_activities(
        self,
        search_query: Optional[str] = None,
        status: Optional[str] = None,
        sort_order: str = "newest",
    ) -> List[Dict[str, Any]]:
        """
        Retrieve activities from FerretDB with optional search, filter, and sorting.
        """
        collection = self.get_collection()
        query: Dict[str, Any] = {}

        # Search by project name or activity title
        if search_query and search_query.strip():
            term = re.escape(search_query.strip())
            query["$or"] = [
                {"project_name": {"$regex": term, "$options": "i"}},
                {"title": {"$regex": term, "$options": "i"}},
                {"developer_name": {"$regex": term, "$options": "i"}},
            ]

        # Filter by status
        if status and status.strip() and status.strip().lower() != "all":
            norm_status = status.strip().capitalize()
            query["status"] = norm_status

        # Sort order: newest or oldest by created_at / _id
        sort_direction = DESCENDING if sort_order.lower() == "newest" else ASCENDING

        cursor = collection.find(query).sort("created_at", sort_direction)
        return [self.serialize_doc(doc) for doc in cursor]

    def get_activity_by_id(self, activity_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single activity by its ID.
        """
        if not activity_id or not ObjectId.is_valid(activity_id):
            return None

        collection = self.get_collection()
        try:
            doc = collection.find_one({"_id": ObjectId(activity_id)})
            return self.serialize_doc(doc) if doc else None
        except InvalidId:
            return None

    def update_activity(
        self, activity_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing activity record in FerretDB.
        """
        if not activity_id or not ObjectId.is_valid(activity_id):
            return None

        collection = self.get_collection()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        update_fields: Dict[str, Any] = {
            "updated_at": now_iso,
        }

        if "project_name" in data:
            update_fields["project_name"] = str(data["project_name"]).strip()
        if "title" in data:
            update_fields["title"] = str(data["title"]).strip()
        if "description" in data:
            update_fields["description"] = str(data["description"]).strip()
        if "status" in data:
            val = str(data["status"]).strip().capitalize()
            if val in Config.VALID_STATUSES:
                update_fields["status"] = val
        if "developer_name" in data:
            update_fields["developer_name"] = str(data["developer_name"]).strip()

        try:
            updated_doc = collection.find_one_and_update(
                {"_id": ObjectId(activity_id)},
                {"$set": update_fields},
                return_document=ReturnDocument.AFTER,
            )
            return self.serialize_doc(updated_doc) if updated_doc else None
        except InvalidId:
            return None

    def delete_activity(self, activity_id: str) -> bool:
        """
        Delete an activity record from FerretDB.
        Returns True if deleted, False otherwise.
        """
        if not activity_id or not ObjectId.is_valid(activity_id):
            return False

        collection = self.get_collection()
        try:
            result = collection.delete_one({"_id": ObjectId(activity_id)})
            return result.deleted_count > 0
        except InvalidId:
            return False

    def get_dashboard_stats(self) -> Dict[str, int]:
        """
        Calculate total activities and counts by status (Success, Pending, Failed).
        """
        collection = self.get_collection()
        total = collection.count_documents({})
        success = collection.count_documents({"status": "Success"})
        pending = collection.count_documents({"status": "Pending"})
        failed = collection.count_documents({"status": "Failed"})

        return {
            "total": total,
            "success": success,
            "pending": pending,
            "failed": failed,
        }


# Global singleton instance for application use
ferretdb_client = FerretDBClient()
