from pathlib import Path

import pytest

from tsdhn.calculator import TsunamiCalculator, parse_port_line
from tsdhn.domain import CalculationResponse, EarthquakeInput


@pytest.fixture(scope="module")
def calculator() -> TsunamiCalculator:
    model_dir = Path(__file__).resolve().parents[3] / "model"
    return TsunamiCalculator(model_dir)


@pytest.fixture(scope="module")
def input_data() -> EarthquakeInput:
    return EarthquakeInput(
        Mw=9.0, h=12.0, lat0=56.0, lon0=-156.0, hhmm="0000", dia="23"
    )


expected_basic = {
    "length": 575.439937,  # L (km)
    "width": 144.543977,  # W (km)
    "seismic_moment": 3.981072e22,  # M0 (N*m)
    "dislocation": 10.636224,  # D (m)
    "azimuth": 247.0,  # Focal mechanism strike (deg)
    "dip": 18.0,  # Dip (deg)
    "distance_to_coast": 10439.472791,  # (km)
}

expected_rect_params = {
    "L1": 575439.937337,  # in m
    "W1": 137469.491288,  # in m
    "beta": 13.435833,  # in degrees
    "alfa": -23.0,  # in degrees
    "h1": 591632.472501,  # in m
    "a1": -49.150481,  # in km
    "b1": 291.704432,  # in km
    "xo": -153.348142,  # longitude
    "yo": 56.446823,  # latitude
}

expected_corners = [
    (-153.348142, 56.446823),
    (-158.112445, 54.424496),
    (-158.595568, 55.562662),
    (-153.831264, 57.584989),
    (-153.348142, 56.446823),
]


@pytest.fixture(scope="module")
def calc_result(
    calculator: TsunamiCalculator, input_data: EarthquakeInput
) -> CalculationResponse:
    return calculator.calculate_earthquake_parameters(input_data)


@pytest.mark.parametrize("param,expected", list(expected_basic.items()))
def test_basic_parameters(
    calc_result: CalculationResponse, param: str, expected: float
) -> None:
    value = getattr(calc_result, param)
    assert value == pytest.approx(expected, rel=1e-6), f"Mismatch in {param}"


@pytest.mark.parametrize("param,expected", list(expected_rect_params.items()))
def test_rectangle_parameters(
    calc_result: CalculationResponse, param: str, expected: float
) -> None:
    rect_params = calc_result.rectangle_parameters
    assert rect_params[param] == pytest.approx(expected, rel=1e-6), (
        f"Mismatch in rectangle parameter: {param}"
    )


@pytest.mark.parametrize("idx,expected_corner", list(enumerate(expected_corners)))
def test_rectangle_corners(
    calc_result: CalculationResponse, idx: int, expected_corner: tuple[float, float]
) -> None:
    computed_corner = calc_result.rectangle_corners[idx]
    assert computed_corner["lon"] == pytest.approx(expected_corner[0], rel=1e-6), (
        f"Corner {idx} longitude mismatch"
    )
    assert computed_corner["lat"] == pytest.approx(expected_corner[1], rel=1e-6), (
        f"Corner {idx} latitude mismatch"
    )


def test_focal_mechanism(calc_result: CalculationResponse) -> None:
    # The nearest-mechanism lookup should stay stable for this epicenter.
    assert calc_result.azimuth == pytest.approx(expected_basic["azimuth"], rel=1e-6)
    assert calc_result.dip == pytest.approx(expected_basic["dip"], rel=1e-6)


def test_port_line_parsing_uses_semantic_name() -> None:
    port = parse_port_line(" -77.1667  -12.06888  % Callao       C")

    assert port is not None
    assert port.name == "Callao"
    assert port.lon == pytest.approx(-77.1667)
    assert port.lat == pytest.approx(-12.06888)


def test_tsunami_travel_times_are_keyed_by_port_name(
    calculator: TsunamiCalculator,
) -> None:
    travel = calculator.calculate_tsunami_travel_times(
        EarthquakeInput(Mw=8.8, h=20, lat0=-12.0, lon0=-77.0, hhmm="1234", dia="05")
    )

    assert "Callao" in travel.arrival_times
    assert not any(name.startswith("-") for name in travel.arrival_times)


if __name__ == "__main__":
    pytest.main([__file__])
