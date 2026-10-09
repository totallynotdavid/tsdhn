assert_storage_objects() {
    local simulation_id="$1"

    docker compose exec -T api uv run --no-dev python - "$simulation_id" <<'PY'
import os
import sys

from minio import Minio

simulation_id = sys.argv[1]
client = Minio(
    os.environ["TSDHN_S3_ENDPOINT"],
    access_key=os.environ["TSDHN_S3_ACCESS_KEY"],
    secret_key=os.environ["TSDHN_S3_SECRET_KEY"],
    secure=False,
)
for suffix in ("metadata.json", "outputs/calculation.json", "outputs/travel_times.csv"):
    object_name = f"simulations/{simulation_id}/{suffix}"
    client.stat_object(os.environ["TSDHN_S3_BUCKET"], object_name)
    print(f"found {object_name}")
PY
}
