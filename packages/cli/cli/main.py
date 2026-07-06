import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from core import EarthquakeInput
from core.calculator import TsunamiCalculator
from core.config import MASTER_PIPELINE
from core.simulation import run_simulation

app = typer.Typer(
    add_completion=False,
    help="Cliente de investigación TSDHN: corre simulaciones de tsunami localmente.",
)
console = Console()

MwOpt = Annotated[float, typer.Option("--mw", help="Magnitud (Mw).")]
DepthOpt = Annotated[float, typer.Option("--depth", "-h", help="Profundidad (km).")]
LatOpt = Annotated[float, typer.Option("--lat", help="Latitud del epicentro.")]
LonOpt = Annotated[float, typer.Option("--lon", help="Longitud del epicentro.")]
TimeOpt = Annotated[str, typer.Option("--time", help="Hora del evento (HHMM, UTC).")]
DayOpt = Annotated[str, typer.Option("--day", help="Día del mes del evento.")]


def _build_input(
    mw: float, depth: float, lat: float, lon: float, hhmm: str, dia: str
) -> EarthquakeInput:
    return EarthquakeInput(Mw=mw, h=depth, lat0=lat, lon0=lon, hhmm=hhmm, dia=dia)


def _calculation_table(calc: dict[str, object]) -> Table:
    table = Table(title="Parámetros de la fuente sísmica", show_header=False)
    rows = {
        "Longitud de ruptura (km)": f"{calc['length']:.2f}",
        "Ancho de ruptura (km)": f"{calc['width']:.2f}",
        "Dislocación (m)": f"{calc['dislocation']:.3f}",
        "Momento sísmico (N·m)": f"{calc['seismic_moment']:.3e}",
        "Azimut (°)": f"{calc['azimuth']:.1f}",
        "Buzamiento (°)": f"{calc['dip']:.1f}",
        "Distancia a la costa (km)": f"{calc['distance_to_coast']:.1f}",
        "Ubicación del epicentro": str(calc["epicenter_location"]),
        "Alerta de tsunami": str(calc["tsunami_warning"]),
    }
    for label, value in rows.items():
        table.add_row(label, value)
    return table


@app.command()
def calc(
    mw: MwOpt = 9.0,
    depth: DepthOpt = 12.0,
    lat: LatOpt = -20.5,
    lon: LonOpt = -70.5,
    time: TimeOpt = "0000",
    day: DayOpt = "23",
) -> None:
    """Vista previa: parámetros de la fuente y tiempos de arribo (sin simular)."""
    data = _build_input(mw, depth, lat, lon, time, day)
    calculator = TsunamiCalculator()
    # The preview writes hypo.dat, but previews must not mutate the working tree.
    with tempfile.TemporaryDirectory() as tmp:
        calculation = calculator.calculate_earthquake_parameters(data, Path(tmp))
    travel = calculator.calculate_tsunami_travel_times(data)

    console.print(_calculation_table(calculation.model_dump()))

    arrivals = Table(title="Tiempos de arribo del tsunami")
    arrivals.add_column("Puerto")
    arrivals.add_column("Arribo")
    arrivals.add_column("Distancia (km)", justify="right")
    distances = travel.distances
    for port, eta in travel.arrival_times.items():
        arrivals.add_row(port, eta, f"{distances.get(port, 0.0):.1f}")
    console.print(arrivals)


@app.command()
def run(
    mw: MwOpt = 9.0,
    depth: DepthOpt = 12.0,
    lat: LatOpt = -20.5,
    lon: LonOpt = -70.5,
    time: TimeOpt = "0000",
    day: DayOpt = "23",
    skip: Annotated[
        list[str] | None,
        typer.Option("--skip", help="Paso del pipeline a omitir (repetible)."),
    ] = None,
    work_dir: Annotated[
        Path | None,
        typer.Option(
            "--work-dir", help="Directorio de trabajo (por defecto jobs/<ts>)."
        ),
    ] = None,
    keep: Annotated[
        bool,
        typer.Option("--keep/--no-keep", help="Conservar el directorio si falla."),
    ] = True,
) -> None:
    """Corre el pipeline completo localmente (puede tardar ~1 hora)."""
    data = _build_input(mw, depth, lat, lon, time, day)
    skip_steps = skip or []
    if work_dir is None:
        work_dir = Path("jobs") / datetime.now().strftime("%Y%m%d-%H%M%S")

    console.print(
        Panel.fit(
            f"Mw={mw}  h={depth} km  lat={lat}  lon={lon}  {time} UTC día {day}\n"
            f"Directorio: [bold]{work_dir}[/bold]"
            + (f"\nOmitiendo: {', '.join(skip_steps)}" if skip_steps else ""),
            title="Simulación TSDHN",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Iniciando…", total=None)

        def on_progress(message: str, details: dict[str, object]) -> None:
            if "step_index" in details:
                message = (
                    f"[{details['step_index']}/{details['total_steps']}] {message}"
                )
            progress.update(task, description=message)

        try:
            result = run_simulation(
                data, work_dir, skip_steps=skip_steps, on_progress=on_progress
            )
        except ValueError as e:
            progress.stop()
            console.print(f"[red]Parámetros inválidos:[/red] {e}")
            raise typer.Exit(code=2) from e
        except Exception as e:
            progress.stop()
            if not keep and work_dir.exists():
                import shutil

                shutil.rmtree(work_dir, ignore_errors=True)
            console.print(f"[red]La simulación falló:[/red] {e}")
            console.print(f"Revise el directorio de trabajo: [bold]{work_dir}[/bold]")
            raise typer.Exit(code=1) from e

    console.print(_calculation_table(result.calculation.model_dump()))
    console.print("[green]✓ Simulación completa.[/green]")
    console.print(f"Reporte: [bold]{result.report_path}[/bold]")


@app.command()
def steps() -> None:
    """Lista los pasos del pipeline (útil para --skip)."""
    for step in MASTER_PIPELINE:
        console.print(f"• {step.name}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
