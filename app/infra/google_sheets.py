"""Read-only Google Sheets client. Never writes. Credentials stay on disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
_VALUES_URL = "https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_a1}"


class SheetsReader(Protocol):
    def fetch_values(self, spreadsheet_id: str, range_a1: str) -> list[list[str]]: ...


class FixtureSheetsReader:
    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch_values(self, spreadsheet_id: str, range_a1: str) -> list[list[str]]:
        del spreadsheet_id, range_a1
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        headers = [str(cell) for cell in payload["headers"]]
        rows = [[str(cell) for cell in row] for row in payload["rows"]]
        return [headers, *rows]


class GoogleSheetsReadonlyClient:
    """Service-account client. Scope is spreadsheets.readonly only."""

    def __init__(self, credentials_file: str) -> None:
        path = Path(credentials_file)
        if not path.is_file():
            raise ValueError("GOOGLE_SHEETS_CREDENTIALS_FILE no existe")
        self._credentials_file = path

    def fetch_values(self, spreadsheet_id: str, range_a1: str) -> list[list[str]]:
        token = self._access_token()
        url = _VALUES_URL.format(
            spreadsheet_id=quote(spreadsheet_id, safe=""),
            range_a1=quote(range_a1, safe="!'"),
        )
        request = Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ValueError("No se pudo leer la hoja de cálculo") from exc
        except URLError as exc:
            raise ValueError("No se pudo leer la hoja de cálculo") from exc
        values = payload.get("values") or []
        return [[str(cell) for cell in row] for row in values]

    def _access_token(self) -> str:
        try:
            from google.auth.transport.requests import Request as GoogleRequest
            from google.oauth2 import service_account
        except ImportError as exc:
            raise ValueError("Falta el paquete google-auth para EVENT_FORM_SOURCE=sheets") from exc

        credentials = service_account.Credentials.from_service_account_file(
            str(self._credentials_file),
            scopes=[SHEETS_READONLY_SCOPE],
        )
        credentials.refresh(GoogleRequest())
        token = credentials.token
        if not token:
            raise ValueError("No se pudo autenticar contra Google Sheets")
        return str(token)
