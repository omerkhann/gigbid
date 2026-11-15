"""Write the API's OpenAPI schema for the web client generator: python -m scripts.export_openapi"""

import json
from pathlib import Path

from apps.api.main import create_app

out = Path(__file__).resolve().parents[1] / "apps/web/openapi.json"
out.write_text(json.dumps(create_app(services=object()).openapi(), indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {out}")
