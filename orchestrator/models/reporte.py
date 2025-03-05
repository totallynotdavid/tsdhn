from dataclasses import dataclass
from typing import List


@dataclass
class EarthquakeData:
    longitude: float
    latitude: float
    depth: float
    azimuth: float
    dip: float
    rake: float
    magnitude: float
    param1: int
    param2: int
    origin_time: str


@dataclass
class TsunamiTravelData:
    travel_times: List[float]
    max_heights: List[float]
    hours: List[int]
    minutes: List[int]


@dataclass
class DatetimeInfo:
    date_str: str
    time_str: str
    year_month_day: tuple[int, int, int]
    month_abbr: str
