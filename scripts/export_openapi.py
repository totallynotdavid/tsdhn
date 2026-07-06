"""
Print the FastAPI OpenAPI schema to stdout without starting a server.
Used by `scripts/gen-client.ts` to regenerate the typed TS client hermetically
(no running backend or compute worker).
"""

import json

from api.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), indent=2))
