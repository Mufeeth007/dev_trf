"""
Redis Cache Module for Developer Activity Tracker.
Provides high-performance caching for activity lists and dashboard statistics.
Includes graceful fallback if Redis server is unreachable.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from config import Config

logger = logging.getLogger(__name__)


class RedisCache:
    """Manages Redis connection and caching operations."""

    def __init__(self, redis_url: Optional[str] = None, default_ttl: Optional[int] = None):
        self.redis_url = redis_url or Config.REDIS_URL
        self.default_ttl = default_ttl or Config.CACHE_TTL
        self._client: Optional[redis.Redis] = None

    def get_client(self) -> redis.Redis:
        """Get or initialize Redis client with timeouts."""
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                protocol=2,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
        return self._client

    def check_connection(self) -> Tuple[bool, Optional[str]]:
        """
        Check if Redis is reachable.
        Returns:
            (True, None) if ping succeeded.
            (False, error_message) if connection failed.
        """
        try:
            client = self.get_client()
            client.ping()
            return True, None
        except (ConnectionError, TimeoutError) as err:
            return False, f"Redis unavailable at {self.redis_url}: {str(err)}"
        except RedisError as err:
            return False, f"Redis error: {str(err)}"
        except Exception as err:
            return False, f"Unexpected error connecting to Redis: {str(err)}"

    def get(self, key: str) -> Optional[Any]:
        """Safely fetch and deserialize a JSON object from Redis."""
        try:
            client = self.get_client()
            val = client.get(key)
            if val is not None:
                return json.loads(val)
            return None
        except (RedisError, json.JSONDecodeError, Exception) as err:
            logger.warning("Redis GET failed for key '%s': %s", key, err)
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Safely serialize and store an object in Redis with TTL expiration."""
        try:
            client = self.get_client()
            expire_seconds = ttl if ttl is not None else self.default_ttl
            payload = json.dumps(value)
            client.set(key, payload, ex=expire_seconds)
            return True
        except (RedisError, TypeError, Exception) as err:
            logger.warning("Redis SET failed for key '%s': %s", key, err)
            return False

    def delete(self, key: str) -> bool:
        """Safely delete a key from Redis."""
        try:
            client = self.get_client()
            client.delete(key)
            return True
        except (RedisError, Exception) as err:
            logger.warning("Redis DELETE failed for key '%s': %s", key, err)
            return False

    def build_activities_cache_key(
        self,
        search_query: Optional[str] = None,
        status: Optional[str] = None,
        sort_order: str = "newest",
    ) -> str:
        """Generate a consistent Redis key for an activity list query."""
        q = (search_query or "").strip().lower()
        s = (status or "all").strip().lower()
        sort = (sort_order or "newest").strip().lower()
        return f"activities:list:q={q}:s={s}:sort={sort}"

    def get_cached_activities(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch cached activity list from Redis."""
        return self.get(cache_key)

    def set_cached_activities(
        self,
        cache_key: str,
        activities: List[Dict[str, Any]],
        ttl: Optional[int] = None,
    ) -> bool:
        """Store activity list in Redis."""
        return self.set(cache_key, activities, ttl=ttl)

    def get_cached_activity(self, activity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch cached individual activity document."""
        return self.get(f"activity:{activity_id}")

    def set_cached_activity(
        self,
        activity_id: str,
        activity: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Store individual activity document in Redis."""
        return self.set(f"activity:{activity_id}", activity, ttl=ttl)

    def get_cached_stats(self) -> Optional[Dict[str, int]]:
        """Fetch cached dashboard statistics from Redis."""
        return self.get("dashboard:stats")

    def set_cached_stats(
        self, stats: Dict[str, int], ttl: Optional[int] = None
    ) -> bool:
        """Store dashboard statistics in Redis."""
        return self.set("dashboard:stats", stats, ttl=ttl)

    def invalidate_activity_cache(self, activity_id: Optional[str] = None) -> None:
        """
        Clear all relevant cached data following any insert, update, or delete.
        Invalidates:
            - dashboard:stats
            - all activities:list:* keys
            - activity:<activity_id> (if activity_id is provided)
        """
        try:
            client = self.get_client()

            keys_to_delete = ["dashboard:stats"]

            if activity_id:
                keys_to_delete.append(f"activity:{activity_id}")

            # Find all activity query keys
            try:
                matched_keys = client.keys("activities:*")
                if matched_keys:
                    keys_to_delete.extend(matched_keys)
            except Exception as err:
                logger.warning("Error fetching Redis keys matching pattern: %s", err)

            if keys_to_delete:
                client.delete(*keys_to_delete)
                logger.info("Invalidated Redis cache keys: %s", keys_to_delete)
        except (RedisError, Exception) as err:
            logger.warning("Failed to invalidate Redis cache: %s", err)


# Global singleton instance for application use
redis_cache = RedisCache()
