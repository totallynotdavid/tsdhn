import logging
from pathlib import Path
from typing import cast

import numpy as np
from orchestrator.core.config import EARTH_RADIUS, GRAVITY, MODEL_DIR
from orchestrator.models.schemas import (
    CalculationResponse,
    EarthquakeInput,
    TsunamiTravelResponse,
)
from orchestrator.utils.geo import (
    calculate_distance_to_coast,
    determine_epicenter_location,
    determine_tsunami_warning,
    format_arrival_time,
)
from scipy.interpolate import RegularGridInterpolator
from scipy.io import loadmat

logger = logging.getLogger(__name__)

# This constant is used in rectangle corner calculations
NM_CONVERSION = 60 * 1853  # Nautical miles to meters conversion


class TsunamiCalculator:
    _data_loaded: bool = False
    _static_loaded: bool = False
    xa: np.ndarray
    ya: np.ndarray
    vlon: np.ndarray | None = None
    vlat: np.ndarray | None = None
    bathymetry: np.ndarray | None = None
    bathy_interpolator: RegularGridInterpolator | None = None
    maper1: np.ndarray | None = None
    mechanism_data: np.ndarray | None = None
    ports: list[str] | None = None

    def __init__(self) -> None:
        """Initialize calculator with preloaded data"""
        self._ensure_data_loaded()

    @classmethod
    def _ensure_data_loaded(cls) -> None:
        """Lazy-load required data once"""
        if not cls._data_loaded:
            cls._load_geographic_data()
        if not cls._static_loaded:
            cls._load_static_files()

    @classmethod
    def _load_geographic_data(cls) -> None:
        try:
            # Load Pacific bathymetry matrix
            pacifico_path = MODEL_DIR / "pacifico.mat"
            pacifico = loadmat(pacifico_path)

            cls.xa = pacifico["xa"].flatten()
            cls.ya = pacifico["ya"].flatten()
            cls.bathymetry = pacifico["A"]

            # Adjust longitude values and validate orientation
            cls.vlon = cls.xa - 360
            cls.vlat = cls.ya
            if cls.vlat[0] > cls.vlat[-1]:
                cls.vlat = cls.vlat[::-1]
                cls.bathymetry = cls.bathymetry[::-1, :]

            # Create bathymetry interpolator
            cls.bathy_interpolator = RegularGridInterpolator(
                (cls.vlat, cls.vlon),
                cls.bathymetry,
                bounds_error=False,
                fill_value=None,
            )

            # Load coastal points data
            maper1_path = MODEL_DIR / "maper1.mat"
            cls.maper1 = loadmat(maper1_path)["A"]

            cls._data_loaded = True
        except Exception as e:
            logger.exception("Failed to load bathymetric data")
            raise RuntimeError("Bathymetric data initialization failed") from e

    @classmethod
    def _load_static_files(cls) -> None:
        try:
            # Load focal mechanism data
            mech_path = MODEL_DIR / "mecfoc.dat"
            cls.mechanism_data = np.loadtxt(mech_path)

            # Adjust longitude values
            cls.mechanism_data[:, 0] = np.where(
                cls.mechanism_data[:, 0] > 0,
                cls.mechanism_data[:, 0] - 360,
                cls.mechanism_data[:, 0],
            )

            # Load port locations
            puertos_path = MODEL_DIR / "puertos.txt"
            with open(puertos_path) as f:
                cls.ports = f.readlines()

            cls._static_loaded = True
        except Exception as e:
            logger.exception("Failed to load static files")
            raise RuntimeError("Static file initialization failed") from e

    def calculate_earthquake_parameters(
        self, data: EarthquakeInput, output_dir: Path | None = None
    ) -> CalculationResponse:
        """
        Calculate earthquake parameters and tsunami risk assessment.
        It also generates a hypo.dat file which will be used in the main simulation.
        """
        try:
            # Calculate rupture parameters
            L = 10 ** (0.55 * data.Mw - 2.19)  # Rupture length (km)
            W = 10 ** (0.31 * data.Mw - 0.63)  # Rupture width (km)
            M0 = 10 ** (1.5 * data.Mw + 9.1)  # Seismic moment (N*m)
            u = 4.5e10  # Rigidity (N/m^2)
            D = M0 / (u * (L * 1000) * (W * 1000))  # Dislocation (m)

            # Get focal mechanism parameters
            azimuth, dip = self._get_focal_mechanism(data.lon0, data.lat0)

            # Fault plane geometry
            rect_params, rect_corners = self._calculate_rectangle_parameters(
                L, W, data.lon0, data.lat0, azimuth, dip
            )

            if self.maper1 is None:
                raise RuntimeError("Coastal data not loaded")

            # Location analysis
            distance_to_coast = calculate_distance_to_coast(
                self.maper1[:, :2], data.lon0, data.lat0
            )

            if self.bathy_interpolator is None:
                raise RuntimeError("Bathymetry interpolator not loaded")

            # Get bathymetry at epicenter
            h0 = self.bathy_interpolator((data.lat0, data.lon0))

            # Determine location and warning
            location = determine_epicenter_location(h0, distance_to_coast)
            warning = determine_tsunami_warning(data.Mw, data.h, h0, distance_to_coast)

            # Generate hypo.dat file (for model execution)
            self._write_hypo_dat(data, output_dir or Path.cwd())

            return CalculationResponse(
                length=L,
                width=W,
                dislocation=D,
                seismic_moment=M0,
                tsunami_warning=warning,
                distance_to_coast=distance_to_coast,
                azimuth=azimuth,
                dip=dip,
                epicenter_location=location,
                rectangle_parameters=rect_params,
                rectangle_corners=rect_corners,
            )
        except Exception as e:
            logger.exception("Earthquake parameter calculation failed")
            raise RuntimeError("Earthquake calculation error") from e

    def calculate_tsunami_travel_times(
        self, data: EarthquakeInput
    ) -> TsunamiTravelResponse:
        """
        Calculate tsunami arrival times at monitored locations
        """
        try:
            if self.ports is None:
                raise RuntimeError("Port data not loaded")
            if data.hhmm is None:
                raise RuntimeError("hhmm must be provided")

            arrival_times: dict[str, str] = {}
            distances: dict[str, float] = {}
            time0 = float(data.hhmm[:2]) + float(data.hhmm[2:]) / 60  # Decimal hours

            for port in self.ports:
                if len(port) < 15:
                    continue

                parts = port.split()
                if len(parts) < 3:
                    logger.warning(f"Insufficient data in port line: '{port.strip()}'")
                    continue

                port_name = port[:15].strip()
                try:
                    port_lon = float(parts[0])
                    port_lat = float(parts[1])

                    distance, travel_time = self._calculate_travel_time(
                        data.lon0, data.lat0, port_lon, port_lat, time0
                    )

                    arrival_times[port_name] = format_arrival_time(
                        travel_time, cast(str, data.dia)
                    )
                    distances[port_name] = distance
                except ValueError, IndexError:
                    continue

            return TsunamiTravelResponse(
                arrival_times=arrival_times,
                distances=distances,
                epicenter_info={
                    "date": cast(str, data.dia),
                    "time": data.hhmm,
                    "latitude": f"{data.lat0:.2f}",
                    "longitude": f"{data.lon0:.2f}",
                    "depth": f"{data.h:.0f}",
                    "magnitude": f"{data.Mw:.1f}",
                },
            )
        except Exception as e:
            logger.exception("Travel time calculation failed")
            raise RuntimeError("Tsunami travel time error") from e

    def _get_focal_mechanism(self, lon0: float, lat0: float) -> tuple[float, float]:
        """
        Find closest focal mechanism parameters

        Args:
            lon0: Longitude of epicenter
            lat0: Latitude of epicenter

        Returns:
            Tuple of (azimuth, dip)
        """
        if self.mechanism_data is None:
            raise RuntimeError("Mechanism data not loaded")

        distances = np.sqrt(
            (self.mechanism_data[:, 0] - lon0) ** 2
            + (self.mechanism_data[:, 1] - lat0) ** 2
        )
        closest_idx = np.argmin(distances)
        return self.mechanism_data[closest_idx, 2], 18.0  # azimuth, dip

    def _calculate_rectangle_parameters(
        self, L: float, W: float, lon0: float, lat0: float, azimuth: float, dip: float
    ) -> tuple[dict[str, float], list[dict[str, float]]]:
        """
        Calculate fault plane geometry (corner points and parameters)

        Args:
            L: Rupture length in km.
            W: Rupture width in km.
            lon0: Epicenter longitude.
            lat0: Epicenter latitude.
            azimuth: Fault strike in degrees.
            dip: Dip angle in degrees (fixed at 18 in MATLAB).

        Returns:
            A tuple containing:
            - A dictionary of rectangle parameters:
              L1, W1, beta, alfa, h1, a1, b1, xo, yo.
            - A list of dictionaries for the rectangle corners
              (each with 'lon' and 'lat').
        """
        L1 = L * 1000  # Convert to meters
        W1 = W * 1000 * np.cos(np.deg2rad(dip))
        beta = np.degrees(np.arctan(W1 / L1))
        alfa = azimuth - 270
        h1 = np.hypot(L1, W1)

        # Calculate rectangle parameters
        params = {
            "L1": L1,
            "W1": W1,
            "beta": beta,
            "alfa": alfa,
            "h1": h1,
            "a1": 0.5 * h1 * np.sin(np.deg2rad(alfa + beta)) / 1000,  # in km
            "b1": 0.5 * h1 * np.cos(np.deg2rad(alfa + beta)) / 1000,  # in km
            "xo": lon0 + (0.5 * h1 * np.cos(np.deg2rad(alfa + beta)) / 1000) / 110,
            "yo": lat0 - (0.5 * h1 * np.sin(np.deg2rad(alfa + beta)) / 1000) / 110,
        }

        # Corner calculations
        angles = -np.radians([(azimuth - 90), azimuth])

        r = np.array([L1, W1]) / NM_CONVERSION

        sx = (
            r[0] * np.cos(angles[0]) * np.array([0, 1, 1, 0, 0])
            + r[1] * np.cos(angles[1]) * np.array([0, 0, 1, 1, 0])
        ) + params["xo"]

        sy = (
            r[0] * np.sin(angles[0]) * np.array([0, 1, 1, 0, 0])
            + r[1] * np.sin(angles[1]) * np.array([0, 0, 1, 1, 0])
        ) + params["yo"]

        corners = [{"lon": x, "lat": y} for x, y in zip(sx, sy, strict=False)]

        return params, corners

    def _calculate_travel_time(
        self, lon0: float, lat0: float, port_lon: float, port_lat: float, time0: float
    ) -> tuple[float, float]:
        """
        Travel time calculation between two given points

        Args:
            lon0:       Source longitude
            lat0:       Source latitude
            port_lon:   Destination longitude
            port_lat:   Destination latitude
            time0:      Initial time

        Returns:
            Tuple of (distance, travel_time)
        """
        # Convert to spherical coordinates
        t1 = np.pi / 2 - np.radians(lat0)
        f1 = np.radians(lon0)
        t2 = np.pi / 2 - np.radians(port_lat)
        f2 = np.radians(port_lon)

        # Great circle distance calculation (spherical law of cosines)
        cos_alpha = np.sin(t1) * np.sin(t2) * np.cos(f1 - f2) + np.cos(t1) * np.cos(t2)
        alpha = np.arccos(np.clip(cos_alpha, -1, 1))
        distance = EARTH_RADIUS * alpha

        # Travel time estimation based on distance and location
        if distance >= 750:
            travel_time = distance / 790 + 0.2
        elif not (-19 <= lat0 <= 0) and distance < 750:
            travel_time = distance / 700
        else:
            # Detailed path analysis
            n_points = 100
            delta = np.degrees(alpha) / n_points
            vu = np.array([port_lon - lon0, port_lat - lat0]) / distance * 110

            indices = np.arange(n_points + 1)[:, None]

            # Each row: P = P0 + (i * delta) * vu
            path_points = (
                np.array([lon0, lat0]) + indices * delta * vu
            )  # shape (n+1, 2)
            bath_points = path_points[:, [1, 0]]  # Swap to (lat, lon)

            if self.bathy_interpolator is None:
                raise RuntimeError("Bathymetry interpolator not loaded")

            # Bathymetry interpolation
            h = np.abs(self.bathy_interpolator(bath_points))
            v = np.sqrt(GRAVITY * h) * 3.6  # Velocity in km/h

            # Simpson's rule integration
            delta_dist = (alpha / n_points) * EARTH_RADIUS
            y = 1 / v
            integral = (
                delta_dist
                / 3
                * (y[0] + y[-1] + 4 * y[1:-1:2].sum() + 2 * y[2:-1:2].sum())
            )

            travel_time = 0.5 * integral

            # Empirical adjustments to travel time
            if travel_time > 3.0:
                travel_time = distance / 733 + 0.25
            elif 1.4 < travel_time < 3.0:
                travel_time = distance / 690 + 0.2

        return distance, travel_time + time0

    def _write_hypo_dat(self, data: EarthquakeInput, output_dir: Path) -> None:
        """Write earthquake parameters to hypo.dat"""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            hypo_path = output_dir / "hypo.dat"
            with hypo_path.open("w") as f:
                f.write(
                    "\n".join(
                        [
                            data.hhmm or "0000",
                            f"{data.lon0:.2f}",
                            f"{data.lat0:.2f}",
                            f"{data.h:.0f}",
                            f"{data.Mw:.1f}",
                        ]
                    )
                )
        except Exception as e:
            logger.exception("Failed to write hypo.dat")
            raise RuntimeError("Hypo.dat creation failed") from e
