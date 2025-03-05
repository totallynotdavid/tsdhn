import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.io import loadmat

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

logger = logging.getLogger(__name__)

# Define a constant for converting rupture dimensions to nautical miles
# This constant is used in rectangle corner calculations
NM_CONVERSION = 60 * 1853  # Nautical miles to meters conversion


class TsunamiCalculator:
    def __init__(self):
        """Initialize with preloaded data and configuration"""
        self.data_path = MODEL_DIR
        self.g = GRAVITY
        self.R = EARTH_RADIUS
        self._load_data()
        self._load_static_files()

    def _load_data(self):
        """Load bathymetry and geographic data"""
        try:
            # Load Pacific bathymetry data
            pacifico_path = self.data_path / "pacifico.mat"
            pacifico = loadmat(pacifico_path)

            self.xa = pacifico["xa"].flatten()
            self.ya = pacifico["ya"].flatten()
            self.bathymetry = pacifico["A"]

            # Adjust longitude values
            self.vlon = self.xa - 360
            self.vlat = self.ya

            # Ensure correct latitude orientation
            if self.vlat[0] > self.vlat[-1]:
                self.vlat = self.vlat[::-1]
                self.bathymetry = self.bathymetry[::-1, :]

            # Create interpolator for bathymetry data
            self.bathy_interpolator = RegularGridInterpolator(
                (self.vlat, self.vlon),
                self.bathymetry,
                bounds_error=False,
                fill_value=None,
            )

            # Load coastal points data
            maper1_path = self.data_path / "maper1.mat"
            maper1 = loadmat(maper1_path)
            self.maper1 = maper1["A"]

        except Exception as e:
            logger.exception("Data loading failed")
            raise RuntimeError("Failed to initialize geographic data") from e

    def _load_static_files(self):
        """
        Preload static files that are reused on every calculation:
        - Focal mechanism file (mecfoc.dat)
        - Ports file (puertos.txt)
        """
        try:
            # Load focal mechanisms
            mech_path = self.data_path / "mecfoc.dat"
            self.mechanism_data = np.loadtxt(mech_path)
            self.mechanism_data[:, 0] = np.where(
                self.mechanism_data[:, 0] > 0,
                self.mechanism_data[:, 0] - 360,
                self.mechanism_data[:, 0],
            )

            # Load port locations
            puertos_path = self.data_path / "puertos.txt"
            with open(puertos_path, "r") as f:
                self.ports = f.readlines()

        except Exception as e:
            logger.exception("Static file loading failed")
            raise RuntimeError("Failed to load static files") from e

    def calculate_earthquake_parameters(
        self, data: EarthquakeInput, output_dir: Optional[Path] = None
    ) -> CalculationResponse:
        """
        Calculate earthquake parameters, assess tsunami risk and generate hypo.dat
        """
        try:
            # Rupture parameter calculations
            L = 10 ** (0.55 * data.Mw - 2.19)  # Length (km)
            W = 10 ** (0.31 * data.Mw - 0.63)  # Width (km)
            M0 = 10 ** (1.5 * data.Mw + 9.1)  # Seismic moment (N*m)
            u = 4.5e10  # Rigidity (N/m^2)
            D = M0 / (u * (L * 1000) * (W * 1000))  # Dislocation (m)

            # Focal mechanism parameters
            azimuth, dip = self._get_focal_mechanism(data.lon0, data.lat0)

            # Fault plane geometry
            rect_params, rect_corners = self._calculate_rectangle_parameters(
                L, W, data.lon0, data.lat0, azimuth, dip
            )

            # Location analysis
            distance_to_coast = calculate_distance_to_coast(
                self.maper1[:, :2], data.lon0, data.lat0
            )

            # Get bathymetry at epicenter
            h0 = self.bathy_interpolator((data.lat0, data.lon0))

            # Determine location and warning
            location = determine_epicenter_location(h0, distance_to_coast)
            warning = determine_tsunami_warning(data.Mw, data.h, h0, distance_to_coast)

            # Write hypo.dat file (for model execution)
            self._write_hypo_dat(data, output_dir or self.data_path)

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
        Calculate tsunami arrival times at monitored locations.
        """
        try:
            arrival_times = {}
            distances = {}
            time0 = float(data.hhmm[:2]) + float(data.hhmm[2:]) / 60

            for port in self.ports:
                if len(port) < 15:
                    continue

                parts = port.split()
                if len(parts) < 3:
                    logger.warning(f"Insufficient data in port line: '{port.strip()}'")
                    continue  # Skip invalid entries

                port_name = port[:15].strip()
                try:
                    port_lon = float(parts[0])
                    port_lat = float(parts[1])

                    distance, travel_time = self._calculate_travel_time(
                        data.lon0, data.lat0, port_lon, port_lat, time0
                    )

                    arrival_times[port_name] = format_arrival_time(
                        travel_time, data.dia
                    )
                    distances[port_name] = distance
                except (ValueError, IndexError):
                    continue

            return TsunamiTravelResponse(
                arrival_times=arrival_times,
                distances=distances,
                epicenter_info={
                    "date": data.dia,
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

    def _get_focal_mechanism(self, lon0: float, lat0: float) -> Tuple[float, float]:
        """
        Find closest focal mechanism parameters

        Args:
            lon0: Longitude of epicenter
            lat0: Latitude of epicenter

        Returns:
            Tuple of (azimuth, dip)
        """
        distances = np.sqrt(
            (self.mechanism_data[:, 0] - lon0) ** 2
            + (self.mechanism_data[:, 1] - lat0) ** 2
        )
        closest_idx = np.argmin(distances)
        return self.mechanism_data[closest_idx, 2], 18.0  # azimuth, dip

    def _calculate_rectangle_parameters(
        self, L: float, W: float, lon0: float, lat0: float, azimuth: float, dip: float
    ) -> Tuple[Dict[str, float], List[Dict[str, float]]]:
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
        h1 = np.sqrt(L1**2 + W1**2)
        a1 = 0.5 * h1 * np.sin(np.deg2rad(alfa + beta)) / 1000  # in km
        b1 = 0.5 * h1 * np.cos(np.deg2rad(alfa + beta)) / 1000  # in km
        xo = lon0 + b1 / 110
        yo = lat0 - a1 / 110

        # Rectangle corner calculations
        a1_prime = -np.radians(azimuth - 90)
        a2_prime = -np.radians(azimuth)
        r1 = L1 / NM_CONVERSION
        r2 = W1 / NM_CONVERSION

        sx = (
            np.array(
                [
                    0,
                    r1 * np.cos(a1_prime),
                    r1 * np.cos(a1_prime) + r2 * np.cos(a2_prime),
                    r2 * np.cos(a2_prime),
                    0,
                ]
            )
            + xo
        )

        sy = (
            np.array(
                [
                    0,
                    r1 * np.sin(a1_prime),
                    r1 * np.sin(a1_prime) + r2 * np.sin(a2_prime),
                    r2 * np.sin(a2_prime),
                    0,
                ]
            )
            + yo
        )

        return (
            {
                "L1": L1,
                "W1": W1,
                "beta": beta,
                "alfa": alfa,
                "h1": h1,
                "a1": a1,
                "b1": b1,
                "xo": xo,
                "yo": yo,
            },
            [{"lon": lon, "lat": lat} for lon, lat in zip(sx, sy, strict=False)],
        )

    def _calculate_travel_time(
        self, lon0: float, lat0: float, port_lon: float, port_lat: float, time0: float
    ) -> Tuple[float, float]:
        """
        Calculate tsunami travel time between two points

        Args:
            lon0: Source longitude
            lat0: Source latitude
            port_lon: Destination longitude
            port_lat: Destination latitude
            time0: Initial time

        Returns:
            Tuple of (distance, travel_time)
        """
        # Spherical coordinates conversion
        t1 = np.pi / 2 - np.radians(lat0)
        f1 = np.radians(lon0)
        t2 = np.pi / 2 - np.radians(port_lat)
        f2 = np.radians(port_lon)

        # Great circle distance calculation using spherical law of cosines
        cosen = np.sin(t1) * np.sin(t2) * np.cos(f1 - f2) + np.cos(t1) * np.cos(t2)
        alfa = np.arccos(cosen)
        distance = self.R * alfa

        # Travel time estimation based on distance and location
        if distance >= 750:
            travel_time = distance / 790 + 0.2
        elif not (-19 <= lat0 <= 0) and distance < 750:
            travel_time = distance / 700
        else:
            travel_time = self._calculate_detailed_travel_time(
                lon0, lat0, port_lon, port_lat, distance, alfa
            )

        return distance, travel_time + time0

    def _calculate_detailed_travel_time(
        self,
        lon0: float,
        lat0: float,
        port_lon: float,
        port_lat: float,
        distance: float,
        alfa: float,
    ) -> float:
        """
        Calculate detailed bathymetry-based travel time calculation

        Args:
            lon0: Source longitude
            lat0: Source latitude
            port_lon: Destination longitude
            port_lat: Destination latitude
            distance: Great circle distance
            alfa: Angular distance

        Returns:
            Calculated travel time
        """
        # Compute unit velocity vector
        # (direction scaled to 110 for geographic conversion)
        vu = np.array([port_lon - lon0, port_lat - lat0]) / distance * 110
        n = 100
        delta = (alfa * 180 / np.pi) / n  # step size in degrees

        # Generate path points
        indices = np.arange(0, n + 1).reshape(-1, 1)  # shape (n+1, 1)
        # Each row: P = P0 + (i * delta) * vu
        positions = np.array([lon0, lat0]) + indices * delta * vu  # shape (n+1, 2)
        points = positions[:, [1, 0]]  # Swap to (lat, lon)

        # Bathymetry interpolation
        h = np.abs(self.bathy_interpolator(points))
        v = np.sqrt(self.g * h) * 3.6  # Velocity in km/h

        # Simpson's rule integration
        delta_distance = (alfa / n) * self.R
        y = 1 / v
        integral = (delta_distance / 3) * (
            y[0] + y[-1] + 4 * np.sum(y[1:-1:2]) + 2 * np.sum(y[2:-1:2])
        )

        travel_time = 0.50 * integral

        # Empirical corrections
        if travel_time > 3.0:
            return distance / 733 + 0.25
        if 1.4 < travel_time < 3.0:
            return distance / 690 + 0.2
        return travel_time

    def _write_hypo_dat(self, data: EarthquakeInput, output_dir: Optional[Path] = None):
        """
        Write earthquake parameters to hypo.dat to specified directory
        """
        output_dir = output_dir or self.data_path
        try:
            hypo_path = output_dir / "hypo.dat"
            with open(hypo_path, "w") as f:
                f.writelines(
                    [
                        f"{data.hhmm}\n",
                        f"{data.lon0:.2f}\n",
                        f"{data.lat0:.2f}\n",
                        f"{data.h:.0f}\n",
                        f"{data.Mw:.1f}\n",
                    ]
                )
        except Exception as e:
            logger.exception("Failed to write hypo.dat")
            raise RuntimeError("Hypo.dat creation failed") from e
