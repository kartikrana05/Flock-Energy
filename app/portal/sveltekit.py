class PageDataError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"{status}: {message}")


def resolve_leaf_data(payload: dict) -> dict:
    """Decode a SvelteKit `__data.json` response.

    The leaf (last) node holds the actual page data, encoded in devalue's
    flat reference format: `data` is a flat array where object/array values
    hold integer indices pointing at other array slots instead of nesting
    directly, and primitives (str/int/bool/None) are returned as-is.
    """
    leaf = payload["nodes"][-1]
    if leaf["type"] == "error":
        raise PageDataError(leaf.get("status", 500), leaf["error"].get("message", "unknown error"))

    arr = leaf["data"]

    def resolve(i, cache):
        if i in cache:
            return cache[i]
        value = arr[i]
        if isinstance(value, dict):
            result = {}
            cache[i] = result
            for key, ref in value.items():
                result[key] = resolve(ref, cache)
            return result
        if isinstance(value, list):
            result = []
            cache[i] = result
            for ref in value:
                result.append(resolve(ref, cache))
            return result
        return value

    return resolve(0, {})
