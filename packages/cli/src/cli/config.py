import json

from cli.constants import CONFIG_FILE, DEFAULT_CONFIG, JOB_ID_FILE
from cli.ui import SimpleUI


class ConfigManager:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.job_id_file = JOB_ID_FILE

    def load_config(self) -> dict:
        try:
            if self.config_file.exists():
                with self.config_file.open("r", encoding="utf-8") as f:
                    return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception as e:
            SimpleUI.show_error(f"Error cargando configuración: {e!s}")
        return DEFAULT_CONFIG

    def save_config(self, config: dict) -> None:
        try:
            with self.config_file.open("w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            SimpleUI.show_success(f"Los parámetros se guardaron en: {self.config_file}")
        except Exception as e:
            SimpleUI.show_error(f"Error guardando configuración: {e!s}")

    def save_job_id(self, job_id: str) -> None:
        try:
            self.job_id_file.write_text(job_id)
            SimpleUI.show_success(f"ID de simulación: {job_id}")
        except Exception as e:
            SimpleUI.show_error(f"Error guardando ID: {e!s}")

    def load_last_job_id(self) -> str | None:
        try:
            return (
                self.job_id_file.read_text().strip()
                if self.job_id_file.exists()
                else None
            )
        except Exception as e:
            SimpleUI.show_error(f"Error leyendo ID: {e!s}")
            return None
