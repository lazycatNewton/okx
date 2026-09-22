"""K 线最新缓存的原子更新：旧周期/未闭合版本不得把最新快照回退。"""

import json

from okx_backend.cache import get_redis

_SET_LATEST = """
local previous = redis.call('GET', KEYS[1])
if previous then
    local old = cjson.decode(previous)
    local new = cjson.decode(ARGV[1])
    if tonumber(old.ts) > tonumber(new.ts) then return 0 end
    if tonumber(old.ts) == tonumber(new.ts) and old.confirm == '1' and new.confirm ~= '1'
    then return 0 end
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', 120)
return 1
"""


async def cache_latest_candle(key: str, data: dict) -> bool:
    return bool(await get_redis().eval(_SET_LATEST, 1, key, json.dumps(data)))
