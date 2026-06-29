from typing import Any, cast

import aiohttp

from cli.constants import DEFAULT_TIMEOUTS
from cli.ui import SimpleUI


class APIClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> APIClient:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit_per_host=5, force_close=True),
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        if self._session is None:
            raise RuntimeError("API client session not initialized")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        timeout = kwargs.pop("timeout", DEFAULT_TIMEOUTS.get(endpoint, 30))
        try:
            async with self._session.request(
                method, url, timeout=aiohttp.ClientTimeout(total=timeout), **kwargs
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return await response.json()
                if "text/" in content_type:
                    return await response.text()
                return await response.read()
        except aiohttp.ClientResponseError as e:
            SimpleUI.show_error(f"Error HTTP {e.status}: {e.message}")
            raise
        except TimeoutError:
            SimpleUI.show_error("Tiempo de espera agotado")
            raise
        except BrokenPipeError as e:
            SimpleUI.show_error(f"Error de conexión: {e!s}")
            raise
        except aiohttp.ClientError as e:
            SimpleUI.show_error(f"Error de conexión: {e!s}")
            raise

    async def check_connection(self) -> bool:
        try:
            await self._request("GET", "health")
            return True
        except Exception:
            return False

    async def call_endpoint(
        self, endpoint: str, data: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        result: Any = await self._request("POST", endpoint, json=data, **kwargs)
        return cast(dict[str, Any], result)

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        result: Any = await self._request("GET", f"job-status/{job_id}")
        return cast(dict[str, Any], result)

    async def download_report(self, job_id: str) -> bytes:
        result: Any = await self._request("GET", f"job-result/{job_id}")
        return cast(bytes, result)
