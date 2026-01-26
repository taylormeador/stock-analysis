import time
import logging
import os

import redis

logger = logging.getLogger(__name__)

lua_script = """
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window_start = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            local window_seconds = tonumber(ARGV[4])
            
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
            local count = redis.call('ZCARD', key)
            
            if count < max_requests then
                redis.call('ZADD', key, now, tostring(now))
                redis.call('EXPIRE', key, window_seconds + 10)
                return 1
            end
            
            return 0
        """


class DistributedRateLimiter:
    """
    Rate limiter that works across multiple Celery workers using Redis.
    Uses a sliding window approach with sorted sets.
    """

    def __init__(self, name: str, max_requests: int, window_seconds: int):
        self.name = name
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.redis_client = redis.from_url(os.getenv("REDIS_URL"))
        self.key = f"rate_limit:{name}"
        self.lua_script = self.redis_client.register_script(lua_script)

    def acquire(self) -> bool:
        """
        Block until permission to make a request is granted.
        """
        while True:
            current_time = time.time()
            window_start = current_time - self.window_seconds

            # Try to acquire
            result = self.lua_script(
                keys=[self.key],
                args=[
                    current_time,
                    window_start,
                    self.max_requests,
                    self.window_seconds,
                ],
            )

            if result == 1:
                return True

            time.sleep(1)
