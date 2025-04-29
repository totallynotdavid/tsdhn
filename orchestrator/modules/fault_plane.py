import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# Physical constants and conversion factors
EARTH_RADIUS = 6371.0  # km
DEG_TO_KM = 111.0  # Approximate conversion: 1 degree ~= 111 km
DEG_TO_RAD = np.pi / 180.0
RAD_TO_DEG = 180.0 / np.pi
RIGIDITY = 4.0e10  # N/m^2 - Average rigidity coefficient

# Fault scaling law coefficients (Papazachos 2004)
LENGTH_SCALE_A = 0.55
LENGTH_SCALE_B = -2.19
WIDTH_SCALE_A = 0.31
WIDTH_SCALE_B = -0.63
MOMENT_SCALE_A = 1.5
MOMENT_SCALE_B = 9.1

# Grid parameters
DEFAULT_NX = 2461
DEFAULT_NY = 2056

# Default minimum top-of-fault depth if calculated depth is negative
MIN_FAULT_DEPTH = 5000.0  # m

# Grid scaling factors based on magnitude threshold
SCALING_FACTOR_LARGE = 1.4  # for Mw > 8.0
SCALING_FACTOR_NORMAL = 2.8  # for Mw ≤ 8.0


class CalculationError(Exception):
    """Exception raised for errors during fault plane calculations."""


class ValidationError(Exception):
    """Exception raised for invalid inputs or data loading failures."""


class OutputStatus(Enum):
    """Status codes for calculation results."""

    SUCCESS = 0
    EPICENTER_OUTSIDE_GRID = 1
    INPUT_ERROR = 2
    CALCULATION_ERROR = 3
    OUTPUT_ERROR = 4


@dataclass
class CalculationResult:
    """Container for reporting calculation status and parameters."""

    status: OutputStatus
    message: str
    parameters: Optional[Dict[str, Any]] = None

    @property
    def success(self) -> bool:
        return self.status == OutputStatus.SUCCESS

    def __bool__(self) -> bool:
        return self.success


@dataclass
class HypocenterData:
    """Hypocentral parameters read from file."""

    time: str
    longitude: float
    latitude: float
    depth: float  # km
    magnitude: float

    @classmethod
    def from_file(cls, filename: Union[str, Path]) -> "HypocenterData":
        """Read time, lon/lat, depth (km), magnitude from first two lines."""
        filename = Path(filename)
        try:
            with open(filename, "r") as f:
                time = f.readline().strip()
                lon, lat, depth_km, mag = np.fromfile(f, sep=" ", count=4)
            # data[0]=lon, data[1]=lat, data[2]=depth(km), data[3]=mag
            return cls(time, float(lon), float(lat), float(depth_km), float(mag))
        except (IOError, ValueError) as e:
            raise ValidationError(f"Error reading hypocenter data: {e}") from e


@dataclass
class FocalMechanism:
    """Strike, dip, rake and location entries from a mechanism catalog."""

    longitude: float
    latitude: float
    strike: float
    dip: float
    rake: float

    @staticmethod
    def read_catalog(
        filename: Union[str, Path], max_rows: int = 310
    ) -> List["FocalMechanism"]:
        """Load up to max_rows of [lon, lat, strike, dip, rake] from text file."""
        filename = Path(filename)
        try:
            data = np.loadtxt(filename, max_rows=max_rows, usecols=range(5))
            return [FocalMechanism(*map(float, row)) for row in data]
        except (IOError, ValueError) as e:
            raise ValidationError(f"Error reading focal mechanism catalog: {e}") from e


class BathymetryGrid:
    """Stores grid coordinates and provides nearest-point lookup."""

    def __init__(
        self, x_file: Union[str, Path], y_file: Union[str, Path], nx: int, ny: int
    ):
        self.nx = nx
        self.ny = ny
        self._load_grid(x_file, y_file)

    def _load_grid(self, x_file: Union[str, Path], y_file: Union[str, Path]) -> None:
        """Load 1D coordinate arrays and compute min/max bounds."""
        try:
            self.x_coords = np.loadtxt(Path(x_file), max_rows=self.nx)
            self.y_coords = np.loadtxt(Path(y_file), max_rows=self.ny)
            if len(self.x_coords) < self.nx:
                raise ValidationError(
                    f"X-grid incomplete: expected {self.nx}, got {len(self.x_coords)}"
                )
            if len(self.y_coords) < self.ny:
                raise ValidationError(
                    f"Y-grid incomplete: expected {self.ny}, got {len(self.y_coords)}"
                )

            # Precompute bounds
            self.x_min, self.x_max = self.x_coords.min(), self.x_coords.max()
            self.y_min, self.y_max = self.y_coords.min(), self.y_coords.max()
        except (IOError, ValueError) as e:
            raise ValidationError(f"Error loading bathymetry grid: {e}") from e

    def find_nearest_point(self, x: np.float32, y: np.float32) -> Tuple[int, int]:
        """
        Return 1-based (i, j) indices of grid points nearest to (x, y).
        Matches Fortran MINLOC behavior.
        """
        dx = np.abs(self.x_coords - x)
        dy = np.abs(self.y_coords - y)
        return int(dx.argmin()) + 1, int(dy.argmin()) + 1

    def is_within_grid(self, x: float, y: float) -> bool:
        """Check whether (x, y) falls inside the precomputed [min, max] bounds."""
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


class FaultPlaneCalculator:
    """Orchestrates loading data, computing fault parameters, and writing outputs."""

    def __init__(self):
        self.logger = logger

        # placeholders for inputs and results
        self.hypo: Optional[HypocenterData] = None
        self.catalog: Optional[List[FocalMechanism]] = None
        self.grid: Optional[BathymetryGrid] = None
        self.mechanism: Optional[FocalMechanism] = None
        self.fault_length: Optional[np.float32] = None
        self.fault_width: Optional[np.float32] = None
        self.slip: Optional[np.float32] = None
        self.seismic_moment: Optional[np.float32] = None
        self.fault_top_depth: Optional[np.float32] = None
        self.I0 = self.J0 = self.IDS = self.IDE = self.JDS = self.JDE = None
        self.fault_center_x = self.fault_center_y = None

    def load_data(
        self,
        hypo_file: Union[str, Path],
        mech_file: Union[str, Path],
        bathy_x: Union[str, Path],
        bathy_y: Union[str, Path],
        nx: int = DEFAULT_NX,
        ny: int = DEFAULT_NY,
    ) -> bool:
        """Load hypocenter, mechanism catalog, and bathymetry grid."""
        try:
            self.logger.info("Loading input data")
            self.hypo = HypocenterData.from_file(hypo_file)
            self.catalog = FocalMechanism.read_catalog(mech_file)
            self.grid = BathymetryGrid(bathy_x, bathy_y, nx, ny)

            # normalize negative longitudes to [0,360)
            if self.hypo.longitude < 0.0:
                self.hypo.longitude += 360.0
                self.logger.info(f"Longitude normalized to {self.hypo.longitude}")

            self.logger.info(f"Loaded {len(self.catalog)} focal mechanisms")
            return True
        except ValidationError as e:
            self.logger.error(f"Data loading failed: {e}")
            raise

    def calculate_fault_parameters(self) -> None:
        """
        Compute fault length, width, seismic moment, and slip using:
        - log10(L) = a * Mw + b  -> L [km] -> meters
        - log10(W) = a * Mw + b
        - M0 = 10^(1.5 * Mw + 9.1)  [N*m]
        - slip = M0 / (μ * L * W)
        """
        if not self.hypo:
            raise CalculationError("Hypocentral data not loaded")

        Mw = np.float32(self.hypo.magnitude)
        self.logger.info(f"Calculating scaling-law parameters for Mw={Mw}")

        # fault length and width (m)
        logL = LENGTH_SCALE_A * Mw + LENGTH_SCALE_B
        self.fault_length = (10.0**logL).astype(np.float32) * 1e3
        logW = WIDTH_SCALE_A * Mw + WIDTH_SCALE_B
        self.fault_width = (10.0**logW).astype(np.float32) * 1e3

        # seismic moment M0 [N*m]
        logM0 = MOMENT_SCALE_A * Mw + MOMENT_SCALE_B
        self.seismic_moment = (10.0**logM0).astype(np.float32)

        # slip [m] = M0 / (rigidity * area)
        area = self.fault_length * self.fault_width
        if area == 0:
            raise CalculationError("Computed fault area is zero")
        self.slip = self.seismic_moment / (RIGIDITY * area)

        self.logger.info(
            f"Length={self.fault_length:.1f}m, "
            f"Width={self.fault_width:.1f}m, "
            f"Slip={self.slip:.4f}m"
        )

    def select_focal_mechanism(self) -> FocalMechanism:
        """Pick the catalog entry closest by (lon, lat) to the hypocenter."""
        if not self.hypo or not self.catalog:
            raise CalculationError("Inputs not fully loaded for mechanism selection")

        hypo_lon = np.float32(self.hypo.longitude)
        hypo_lat = np.float32(self.hypo.latitude)
        self.logger.info(f"Selecting focal mechanism near ({hypo_lon}, {hypo_lat})")

        min_dist = np.inf
        best = None

        # find closest mechanism by squared distance
        for mech in self.catalog:
            lon = np.float32(mech.longitude) % 360.0
            lat = np.float32(mech.latitude)
            d2 = (lon - hypo_lon) ** 2 + (lat - hypo_lat) ** 2
            if d2 < min_dist:
                min_dist, best = d2, mech

        if best is None:
            raise CalculationError("No focal mechanism found")
        # enforce rake = 90°
        self.mechanism = FocalMechanism(
            best.longitude, best.latitude, best.strike, best.dip, 90.0
        )
        self.logger.info(
            f"Selected mech: strike={self.mechanism.strike}, dip={self.mechanism.dip}"
        )
        return self.mechanism

    def calculate_fault_geometry(self) -> np.float32:
        """
        Determine fault plane center and top depth:
        - project width onto horizontal: W * cos(dip)
        - compute offsets (a, b) using strike and dip geometry
        - find grid indices (I0, J0)
        - depth_term = (delta_x * cos(strike) + delta_y * sin(strike))* tan(dip)
        - top depth = hypo_depth - depth_term (clamped ≥ MIN_FAULT_DEPTH)
        """
        if not all(
            [self.mechanism, self.fault_length, self.fault_width, self.hypo, self.grid]
        ):
            raise CalculationError("Prerequisites missing for geometry calc")

        strike_rad = np.float32(self.mechanism.strike) * DEG_TO_RAD
        dip_rad = np.float32(self.mechanism.dip) * DEG_TO_RAD
        cos_dip, tan_dip = np.cos(dip_rad), np.tan(dip_rad)

        # horizontal projection of width
        w_proj = self.fault_width * cos_dip
        # geometry hypotenuse
        h = np.hypot(self.fault_length, w_proj)
        beta = np.arctan(w_proj / self.fault_length)  # rad

        # offsets in km (converted from m via /1000)
        angle = (self.mechanism.strike - 270.0) * DEG_TO_RAD + beta

        # Calculate a and b offsets in km
        a_km = 0.5 * h * np.sin(angle) / 1000.0
        b_km = 0.5 * h * np.cos(angle) / 1000.0

        # Calculate fault center coordinates (xo, yo in the original implementation)
        # xo = xep + b / 111.0; yo = yep - a / 111.0
        lon0 = self.hypo.longitude + b_km / DEG_TO_KM
        lat0 = self.hypo.latitude - a_km / DEG_TO_KM
        self.fault_center_x, self.fault_center_y = np.float32(lon0), np.float32(lat0)
        self.I0, self.J0 = self.grid.find_nearest_point(
            self.fault_center_x, self.fault_center_y
        )

        # compute top-of-fault depth [m]
        delta_x = (self.hypo.longitude - lon0) * DEG_TO_KM
        delta_y = (self.hypo.latitude - lat0) * DEG_TO_KM

        # Calculate depth term
        # h = zep - (delta_x*cos(-Az*pi/180.0)
        #     + delta_y*sin(-Az*pi/180.0))*tan(echado*pi/180.0)
        depth_term = (
            delta_x * np.cos(-strike_rad) + delta_y * np.sin(-strike_rad)
        ) * tan_dip
        depth_km = np.float32(self.hypo.depth) - depth_term
        depth_m = depth_km * 1000.0
        if depth_m < 0:
            self.fault_top_depth = MIN_FAULT_DEPTH
        else:
            self.fault_top_depth = depth_m

        self.logger.info(
            f"Fault center ({lon0:.4f}, {lat0:.4f}), "
            f"top depth {self.fault_top_depth:.1f}m"
        )
        return self.fault_top_depth

    def calculate_deformation_grid(self) -> Tuple[int, int, int, int]:
        """
        Determine computational window:
        - offset = scale * (length_km) / DEG_TO_KM
        - truncate to int for Fortran-like behavior
        - find nearest grid indices for boundary coords
        """
        if not all([self.hypo, self.fault_length, self.grid]):
            raise CalculationError("Missing data for deformation grid")

        Mw = np.float32(self.hypo.magnitude)
        length_km = self.fault_length / 1000.0
        scale = SCALING_FACTOR_LARGE if Mw > 8.0 else SCALING_FACTOR_NORMAL

        # Calculate coordinate offset in degrees
        offset_deg = (scale * length_km) / DEG_TO_KM

        lon0, lat0 = self.hypo.longitude, self.hypo.latitude

        # Calculate boundary coordinates
        ids_f, ide_f = lon0 - offset_deg, lon0 + offset_deg
        jds_f, jde_f = lat0 - offset_deg, lat0 + offset_deg

        # truncate toward zero (replicate Fortran implicit behavior)
        ids_i = int(ids_f)
        ide_i = int(ide_f)
        jds_i = int(jds_f)
        jde_i = int(jde_f)

        # find nearest grid indices (1-based)
        self.IDS = self.grid.find_nearest_point(np.float32(ids_i), np.float32(0.0))[0]
        self.IDE = self.grid.find_nearest_point(np.float32(ide_i), np.float32(0.0))[0]
        self.JDS = self.grid.find_nearest_point(np.float32(0.0), np.float32(jds_i))[1]
        self.JDE = self.grid.find_nearest_point(np.float32(0.0), np.float32(jde_i))[1]

        self.logger.info(
            f"Deformation grid IDS={self.IDS}, IDE={self.IDE}, "
            f"JDS={self.JDS}, JDE={self.JDE}"
        )
        return self.IDS, self.IDE, self.JDS, self.JDE

    def write_output_files(
        self,
        output_dir: Union[str, Path, None] = None,
        pfalla_file: str = "pfalla.inp",
        xyo_file: str = "xyo.dat",
        meca_file: str = "meca.dat",
    ) -> bool:
        """
        Generate Fortran-style input files:
        - pfalla.inp: I0, J0, slip, length, width, strike, dip, rake, depth
        - xyo.dat: IDS, IDE, JDS, JDE, nx, ny
        - meca.dat: lon, lat, depth, strike, dip, rake, Mw, flags, time
        """
        try:
            required = [
                self.I0,
                self.J0,
                self.IDS,
                self.IDE,
                self.JDS,
                self.JDE,
                self.slip,
                self.fault_length,
                self.fault_width,
                self.mechanism,
                self.fault_top_depth,
                self.hypo,
            ]
            if any(v is None for v in required):
                missing = [
                    name
                    for name, v in zip(
                        [
                            "I0",
                            "J0",
                            "IDS",
                            "IDE",
                            "JDS",
                            "JDE",
                            "slip",
                            "fault_length",
                            "fault_width",
                            "mechanism",
                            "fault_top_depth",
                            "hypo",
                        ],
                        required,
                        strict=False,
                    )
                    if v is None
                ]
                raise CalculationError(f"Missing values: {', '.join(missing)}")

            out = Path(output_dir) if output_dir else Path(".")
            out.mkdir(parents=True, exist_ok=True)

            # pfalla.inp - fault parameters
            pf = (
                f"{self.I0} {self.J0} {self.slip:.7f} "
                f"{self.fault_length:.1f} {self.fault_width:.1f} "
                f"{self.mechanism.strike:.1f} {self.mechanism.dip:.1f} "
                f"{self.mechanism.rake:.1f} {self.fault_top_depth:.4f}"
            )
            (out / pfalla_file).write_text(pf + "\n")

            # xyo.dat - grid bounds
            xy = (
                f"{self.IDS} {self.IDE} {self.JDS} {self.JDE} "
                f"{self.grid.nx} {self.grid.ny}"
            )
            (out / xyo_file).write_text(xy + "\n")

            # meca.dat - mechanism data
            h = self.hypo
            m = self.mechanism
            meca = (
                f"{h.longitude:7.2f}{h.latitude:7.2f}{h.depth:7.2f}"
                f"{m.strike:7.2f}{m.dip:7.2f}{m.rake:7.2f}"
                f"{h.magnitude:7.2f} 0 0 {h.time}"
            )
            (out / meca_file).write_text(meca + "\n")

            self.logger.info(f"Wrote output files into {out.resolve()}")
            return True
        except (IOError, CalculationError) as e:
            self.logger.error(f"Error writing files: {e}")
            raise

    def validate_inputs(self) -> bool:
        """Ensure hypocenter is inside the computational grid."""
        if not self.hypo:
            raise ValidationError("Hypocentral data not loaded")
        if not self.grid:
            raise ValidationError("Bathymetry grid not loaded")
        if not self.grid.is_within_grid(self.hypo.longitude, self.hypo.latitude):
            raise ValidationError("Epicenter is outside computational grid")
        return True

    def get_results_dict(self) -> Dict[str, Any]:
        """Package all key results into a serializable dict."""
        return {
            "I0": self.I0,
            "J0": self.J0,
            "IDS": self.IDS,
            "IDE": self.IDE,
            "JDS": self.JDS,
            "JDE": self.JDE,
            "slip": self.slip,
            "fault_length": self.fault_length,
            "fault_width": self.fault_width,
            "fault_top_depth": self.fault_top_depth,
            "fault_center": (self.fault_center_x, self.fault_center_y),
            "mechanism": {
                "strike": self.mechanism.strike if self.mechanism else None,
                "dip": self.mechanism.dip if self.mechanism else None,
                "rake": self.mechanism.rake if self.mechanism else None,
            },
            "hypocenter": {
                "time": self.hypo.time,
                "longitude": self.hypo.longitude,
                "latitude": self.hypo.latitude,
                "depth_km": self.hypo.depth,
                "magnitude": self.hypo.magnitude,
            },
        }

    def run(
        self,
        hypo_file: Union[str, Path],
        mech_file: Union[str, Path],
        bathy_x: Union[str, Path],
        bathy_y: Union[str, Path],
        nx: int = DEFAULT_NX,
        ny: int = DEFAULT_NY,
        output_dir: Union[str, Path, None] = None,
        pfalla_file: str = "pfalla.inp",
        xyo_file: str = "xyo.dat",
        meca_file: str = "meca.dat",
    ) -> CalculationResult:
        """Execute full workflow: load, validate, compute, and write outputs."""
        self.logger.info("Starting fault plane calculation")
        # reinitialize internal state
        self.__init__()

        try:
            self.load_data(hypo_file, mech_file, bathy_x, bathy_y, nx, ny)
            self.validate_inputs()
            self.select_focal_mechanism()
            self.calculate_fault_parameters()
            self.calculate_fault_geometry()
            self.calculate_deformation_grid()
            self.write_output_files(output_dir, pfalla_file, xyo_file, meca_file)

            self.logger.info("Calculation completed successfully")
            return CalculationResult(
                status=OutputStatus.SUCCESS,
                message="Calculation completed successfully",
                parameters=self.get_results_dict(),
            )

        except ValidationError as e:
            code = (
                OutputStatus.EPICENTER_OUTSIDE_GRID
                if "outside computational grid" in str(e)
                else OutputStatus.INPUT_ERROR
            )
            self.logger.error(f"Validation failed: {e}")
            return CalculationResult(status=code, message=str(e))

        except CalculationError as e:
            self.logger.error(f"Calculation error: {e}")
            return CalculationResult(
                status=OutputStatus.CALCULATION_ERROR, message=str(e)
            )

        except IOError as e:
            self.logger.error(f"I/O error: {e}")
            return CalculationResult(status=OutputStatus.OUTPUT_ERROR, message=str(e))

        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return CalculationResult(
                status=OutputStatus.CALCULATION_ERROR, message=f"Unexpected error: {e}"
            )
