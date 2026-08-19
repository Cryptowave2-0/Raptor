import os
from dotenv import dotenv_values

_env = dotenv_values(".env")

def _get(key: str, required: bool = True) -> str:
    """Get a value from the .env file or the environment variables, raising an error if required and not found."""
    value = _env.get(key) or os.environ.get(key, "")
    if required and not value:
        raise RuntimeError(f"environment variable not set : {key}")
    return value