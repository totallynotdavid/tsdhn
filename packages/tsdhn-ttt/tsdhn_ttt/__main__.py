"""Command line: `tsdhn-ttt cortado.i2 -E-78.8/-12.0 -Tttt.b`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from tsdhn_ttt import read_bathymetry, travel_times, write_travel_times


def _epicenter(text: str) -> tuple[float, float]:
    lon, separator, lat = text.partition("/")
    if not separator:
        msg = f"expected LON/LAT, got {text!r}"
        raise argparse.ArgumentTypeError(msg)
    try:
        return float(lon), float(lat)
    except ValueError:
        msg = f"expected LON/LAT in degrees, got {text!r}"
        raise argparse.ArgumentTypeError(msg) from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tsdhn-ttt",
        description=(
            "Compute tsunami travel times in hours from one epicenter. "
            "Write the epicenter as -E-78.8/-12.0 when the longitude is negative."
        ),
    )
    parser.add_argument("grid", type=Path, help="bathymetry, GMT native 16-bit grid")
    parser.add_argument(
        "-E", "--epicenter", type=_epicenter, required=True, metavar="LON/LAT"
    )
    parser.add_argument(
        "-T", "--output", type=Path, required=True, help="travel-time grid to write"
    )
    args = parser.parse_args(argv)
    lon, lat = args.epicenter
    bathymetry = read_bathymetry(args.grid)
    try:
        result = travel_times(bathymetry, lon, lat)
    except ValueError as error:
        print(f"tsdhn-ttt: {error}", file=sys.stderr)
        return 1
    write_travel_times(
        args.output,
        bathymetry,
        result.hours,
        args.epicenter,
        result.source_slope_s_per_km,
    )
    print(
        f"tsdhn-ttt: maximum travel time {result.maximum_hours:.2f} h, "
        f"{result.unreached} water nodes not reached",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
