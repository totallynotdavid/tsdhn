import datetime
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from core.executables import resolve

MONTH_MAP = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


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
    travel_times: list[float]
    max_heights: list[float]
    hours: list[int]
    minutes: list[int]


@dataclass
class DatetimeInfo:
    date_str: str
    time_str: str
    year_month_day: tuple[int, int, int]
    month_abbr: str


def generate_reports_wrapper(working_dir: Path) -> None:
    generate_reports(working_dir)

    subprocess.run(
        [
            str(resolve("typst")),
            "compile",
            "--root",
            str(working_dir),
            str(working_dir / "reporte.typ"),
            str(working_dir / "reporte.pdf"),
        ],
        cwd=working_dir,
        check=True,
    )

    (working_dir / "reporte.typ").unlink(missing_ok=True)


def generate_reports(working_dir: Path) -> None:
    coords = read_meca_dat(working_dir)
    ttt_data = read_ttt_max_dat(working_dir)
    datetime_info = get_current_datetime_info()

    context = build_template_context(coords, ttt_data, datetime_info)
    write_reporte_typ(context, working_dir)
    write_salida_txt(coords, ttt_data, datetime_info, working_dir)


def read_meca_dat(working_dir: Path) -> EarthquakeData:
    filepath = working_dir / "meca.dat"
    content = filepath.read_text(encoding="utf-8")
    tokens = content.split()

    if len(tokens) < 10:
        raise ValueError(
            f"Invalid meca.dat format - expected 10+ tokens, got {len(tokens)}"
        )

    values = tokens[:10]
    xep, yep, zep = map(float, values[:3])
    az, dip, rake = map(float, values[3:6])
    mw = float(values[6])
    t0 = values[9]

    if xep > 180.0:
        xep -= 360.0

    return EarthquakeData(
        longitude=xep,
        latitude=yep,
        depth=zep,
        azimuth=az,
        dip=dip,
        rake=rake,
        magnitude=mw,
        param1=int(values[7]),
        param2=int(values[8]),
        origin_time=t0,
    )


def read_ttt_max_dat(working_dir: Path) -> TsunamiTravelData:
    filepath = working_dir / "ttt_max.dat"
    lines = filepath.read_text(encoding="utf-8").splitlines()
    data = []

    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            data.append((float(parts[0]), float(parts[1])))

    if len(data) != 17:
        raise ValueError(f"Expected 17 entries in ttt_max.dat, got {len(data)}")

    ttt, max_vals = zip(*data, strict=False)
    hours = [int(t // 60) for t in ttt]
    minutes = [round(t % 60) for t in ttt]

    return TsunamiTravelData(
        travel_times=list(ttt), max_heights=list(max_vals), hours=hours, minutes=minutes
    )


def get_current_datetime_info() -> DatetimeInfo:
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    year_month_day = (now.year, now.month, now.day)
    return DatetimeInfo(
        date_str=date_str,
        time_str=time_str,
        year_month_day=year_month_day,
        month_abbr=MONTH_MAP[now.month],
    )


def build_template_context(
    coords: EarthquakeData,
    ttt_data: TsunamiTravelData,
    datetime_info: DatetimeInfo,
) -> dict[str, str]:
    return {
        "title": "REPORTE: ESTIMACIÓN DE PARÁMETROS DE TSUNAMI DE ORIGEN LEJANO",
        "author": "Cesar Jimenez",
        "date": (
            f"{datetime_info.year_month_day[2]} {datetime_info.month_abbr} "
            f"{datetime_info.year_month_day[0]}"
        ),
        "lat": f"{coords.latitude:.2f}",
        "lon": f"{coords.longitude:.2f}",
        "depth": f"{coords.depth:.1f}",
        "magnitude": f"{coords.magnitude:.1f}",
        "strike": f"{coords.azimuth:.1f}",
        "dip": f"{coords.dip:.1f}",
        "rake": f"{coords.rake:.1f}",
        "station1_name": "Talara",
        "station1_time": f"{ttt_data.hours[1]}:{ttt_data.minutes[1]:02d}",
        "station1_max": f"{ttt_data.max_heights[1]:.2f}",
        "station2_name": "Callao",
        "station2_time": f"{ttt_data.hours[8]}:{ttt_data.minutes[8]:02d}",
        "station2_max": f"{ttt_data.max_heights[8]:.2f}",
        "station3_name": "Matarani",
        "station3_time": f"{ttt_data.hours[14]}:{ttt_data.minutes[14]:02d}",
        "station3_max": f"{ttt_data.max_heights[14]:.2f}",
    }


def write_reporte_typ(context: dict[str, str], working_dir: Path) -> None:
    template = (
        files("core.modules.templates")
        .joinpath("reporte_template.typ")
        .read_text(encoding="utf-8")
    )
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"%%{key}%%", value)

    out_path = working_dir / "reporte.typ"
    out_path.write_text(rendered, encoding="utf-8")


def write_salida_txt(
    coords: EarthquakeData,
    ttt_data: TsunamiTravelData,
    datetime_info: DatetimeInfo,
    working_dir: Path,
) -> None:
    date_str, time_str = datetime_info.date_str, datetime_info.time_str
    year, _month, day = datetime_info.year_month_day
    mes = datetime_info.month_abbr

    stations = [
        ("Tumbes", "La Cruz", 0),
        ("Piura", "Talara", 1),
        ("Piura", "Paita", 2),
        ("Lambayeque", "Pimentel", 3),
        ("La_Libertad", "Salaverry", 4),
        ("Ancash", "Chimbote", 5),
        ("Ancash", "Huarmey", 6),
        ("Lima", "Huacho", 7),
        ("Lima", "Callao", 8),
        ("Lima", "Cerro Azul", 9),
        ("Ica", "Pisco", 10),
        ("Ica", "San Juan", 11),
        ("Arequipa", "Atico", 12),
        ("Arequipa", "Camana", 13),
        ("Arequipa", "Matarani", 14),
        ("Moquegua", "Ilo", 15),
        ("Chile", "Arica", 16),
    ]

    lines = [
        f"{'ESTIMACION DEL TIEMPO DE ARRIBO DE TSUNAMIS':^43}",
        f"{'Coordenadas del epicentro: ':26}",
        f"Fecha    = {day:2d} {mes} {year}",
        f"Hora     = {coords.origin_time}",
        f"Latitud  =  {coords.latitude:7.2f}",
        f"Longitud =  {coords.longitude:7.2f}",
        f"Profund  =  {coords.depth:5.1f} km",
        f"Magnitud =  {coords.magnitude:3.1f}",
        f"Tiempo actual: {date_str} {time_str}",
        f"{'Departamento Puertos    Hora_llegada  Hmax(m)  T_arribo':55}",
    ]

    for dept, port, idx in stations:
        h = ttt_data.hours[idx]
        m = ttt_data.minutes[idx]
        val = ttt_data.max_heights[idx]
        lines.append(f"{f'{dept} {port}':27}{h}:{m:02d}   {val:6.2f}     {h}:{m:02d}")

    lines.append("* La altura estimada NO considera la fase lunar ni oleaje anomalo")

    out_path = working_dir / "salida.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
