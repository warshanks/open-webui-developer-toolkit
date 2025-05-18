# redis.py

`backend/open_webui/utils/redis.py` collects helper functions for working with Redis.
It supports both direct connections and [Sentinel](https://redis.io/docs/interact/sentinel/) clusters.
These helpers are used by `AppConfig` when initialising the global cache.

## `parse_redis_service_url`

This function extracts connection info from a `redis://` URL. The return value
includes the optional username/password, the service name (or host), port and
selected database.

```python
config = parse_redis_service_url("redis://user:pass@redis-host:6380/0")
# {
#     "username": "user",
#     "password": "pass",
#     "service": "redis-host",
#     "port": 6380,
#     "db": 0,
# }
```

The service portion doubles as the Sentinel *master name* when Sentinel is used.

## `get_redis_connection`

Creates a `redis.Redis` connection. When Sentinel hosts are supplied it builds a
`redis.sentinel.Sentinel` instance and obtains the master connection:

```python
sentinel = redis.sentinel.Sentinel(
    redis_sentinels,
    port=cfg["port"],
    db=cfg["db"],
    username=cfg["username"],
    password=cfg["password"],
    decode_responses=True,
)
return sentinel.master_for(cfg["service"])
```

If no sentinel hosts are provided it falls back to `redis.Redis.from_url`.

## Environment helpers

`get_sentinels_from_env` turns comma separated hostnames and a port number into
the list of `(host, port)` tuples expected by `Sentinel`. `get_sentinel_url_from_env`
constructs a usable `redis+sentinel://` URL from the same data.

```python
hosts = get_sentinels_from_env("s1.example.com,s2.example.com", "26379")
url = get_sentinel_url_from_env(
    "redis://user:pass@mymaster/0",
    "s1.example.com,s2.example.com",
    "26379",
)
```

These helpers normalise environment configuration before it reaches `redis-py`.

