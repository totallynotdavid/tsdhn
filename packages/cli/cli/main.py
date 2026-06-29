import argparse
import asyncio

from cli.config import ConfigManager
from cli.core import JobMonitor, SimulationManager
from cli.ui import SimpleUI


async def main(args: argparse.Namespace) -> None:
    config = ConfigManager().load_config()
    sim = SimulationManager(config, dev_mode=args.dev)
    job_id = await sim.full_test_flow()
    if job_id:
        monitor = JobMonitor(config, job_id)
        await monitor.monitor_job()
    else:
        SimpleUI.show_error("La simulación no pudo ser iniciada.")
    SimpleUI.print_exit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI de Orchestrator-TSDHN")
    parser.add_argument("--dev", action="store_true", help="Enable developer mode")
    args = parser.parse_args()
    asyncio.run(main(args))
