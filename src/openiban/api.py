"""Public read-only HTTP API. Imports and activation are local CLI operations."""

from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from openiban import __version__
from openiban.directory_storage import lookup_directory
from openiban.storage import build_engine, lookup
from openiban.validation import COUNTRIES, validate_iban


class ValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    iban: str = Field(
        strict=True,
        min_length=1,
        max_length=128,
        description="IBAN; spaces and lowercase ASCII letters are allowed.",
    )


class Checks(BaseModel):
    format: bool | None
    checksum: bool | None


class DatasetInfo(BaseModel):
    version: str
    sha256: str
    valid_from: date
    valid_until: date
    status: Literal["current", "expired", "not_yet_valid"]
    source: str
    source_url: str
    imported_at: str


class BankInfo(BaseModel):
    bank_code: str
    name: str
    postal_code: str
    city: str
    bic: str | None
    deletion_announced: bool
    successor_bank_code: str | None


class ValidationResponse(BaseModel):
    normalized_iban: str
    country_supported: bool
    iban_valid: bool | None = Field(
        description="Country format and IBAN checksum; does not verify account existence."
    )
    reason: Literal[
        "valid", "invalid_characters", "invalid_format", "invalid_checksum", "unsupported_country"
    ]
    checks: Checks
    bank_lookup_status: Literal[
        "not_checked", "unavailable", "stale", "found", "not_found", "deleted"
    ]
    bank_code_valid: bool | None = Field(
        description="Bank identifier in the current active dataset; null means not verifiable."
    )
    bank: BankInfo | None = None
    data: DatasetInfo | None = None


class RequestBoundary:
    """Bound bodies before JSON parsing, including requests without Content-Length."""

    def __init__(self, app, max_bytes: int = 4096):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def no_cache(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store")
                ]
            await send(message)

        # Never accept IBANs as query parameters, even on documentation/health routes.
        if scope.get("query_string"):
            return await JSONResponse({"detail": "Query parameters are not supported."}, 400)(
                scope, receive, no_cache
            )
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                return await JSONResponse({"detail": "Request too large."}, 413)(
                    scope, receive, no_cache
                )
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, no_cache)


def create_app(engine: Engine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = engine if engine is not None else build_engine()
        yield
        if engine is None:
            app.state.engine.dispose()

    app = FastAPI(
        title="OpenIBAN.eu",
        version=__version__,
        lifespan=lifespan,
        description=(
            "European IBANs: format, MOD-97 and local official bank directories. "
            "Does not verify account existence, account holders or domestic account checksums."
        ),
    )
    app.add_middleware(RequestBoundary)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _exc: RequestValidationError):
        # FastAPI's default validation details can echo sensitive input.
        return JSONResponse({"detail": "Expected a JSON object with iban (1–128 characters)."}, 422)

    @app.get("/health/live", tags=["Operations"])
    def live():
        return {"status": "ok"}

    @app.get(
        "/health/ready",
        tags=["Operations"],
        responses={503: {"description": "Bank data not ready"}},
    )
    def ready(request: Request):
        try:
            info, _ = lookup(request.app.state.engine, None)
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, 503)
        if info is None or info["status"] != "current":
            return JSONResponse({"status": "no_current_dataset"}, 503)
        return {"status": "ready", "data_version": info["version"]}

    @app.get("/v1/countries", tags=["IBAN"])
    def countries():
        return {
            "countries": [
                {"code": code, "iban_length": spec[0], "bank_lookup_supported": True}
                for code, spec in COUNTRIES.items()
            ]
        }

    @app.post(
        "/v1/validate",
        response_model=ValidationResponse,
        tags=["IBAN"],
        responses={413: {"description": "Request too large"}},
    )
    def validate(payload: ValidationRequest, request: Request):
        result = validate_iban(payload.iban)
        response = ValidationResponse(
            normalized_iban=result.normalized,
            country_supported=result.country_supported,
            iban_valid=result.iban_valid,
            reason=result.reason,
            checks=Checks(format=result.format_valid, checksum=result.checksum_valid),
            bank_lookup_status="not_checked",
            bank_code_valid=None,
        )
        if not result.iban_valid:
            return response
        try:
            country = result.normalized[:2]
            code = result.normalized[4 : 4 + COUNTRIES[country][2]]
            if country == "DE":
                info, bank = lookup(request.app.state.engine, code)
            else:
                info, bank = lookup_directory(request.app.state.engine, country, code)
        except SQLAlchemyError:
            response.bank_lookup_status = "unavailable"
            return response
        if info is None:
            response.bank_lookup_status = "unavailable"
            return response
        response.data = DatasetInfo(**info)
        if info["status"] != "current":
            response.bank_lookup_status = "stale"
            return response
        if bank is None:
            response.bank_lookup_status = "not_found"
            response.bank_code_valid = False
        elif bank["change_flag"] == "D":
            response.bank_lookup_status = "deleted"
            response.bank_code_valid = False
        else:
            response.bank_lookup_status = "found"
            response.bank_code_valid = True
            response.bank = BankInfo(**bank)
        return response

    return app


app = create_app()
