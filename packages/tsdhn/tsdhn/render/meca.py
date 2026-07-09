from pathlib import Path
from typing import TypedDict


class MecaSpec(TypedDict):
    longitude: float
    latitude: float
    depth: float
    strike: float
    dip: float
    rake: float
    magnitude: float
    plot_longitude: float
    plot_latitude: float
    event_name: str


def read_meca_spec(meca_file: Path) -> MecaSpec:
    with meca_file.open("r") as f:
        line = f.readline().strip()
    values = line.split()
    if len(values) != 10:
        raise ValueError(f"Meca file {meca_file} does not contain exactly 10 values.")

    spec: MecaSpec = {
        "longitude": float(values[0]),
        "latitude": float(values[1]),
        "depth": float(values[2]),
        "strike": float(values[3]),
        "dip": float(values[4]),
        "rake": float(values[5]),
        "magnitude": float(values[6]),
        "plot_longitude": float(values[7]),
        "plot_latitude": float(values[8]),
        "event_name": f"s{values[9]}" if not values[9].startswith("s") else values[9],
    }
    return spec
