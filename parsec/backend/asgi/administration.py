# Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 (eventually AGPL-3.0) 2016-present Scille SAS
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable, NoReturn, Dict, Tuple, TypeVar
from typing_extensions import ParamSpec
import csv
from io import StringIO
from functools import wraps
from parsec.serde.serializer import JSONSerializer
from quart import current_app, Response, Blueprint, abort, request, jsonify, make_response, g

from parsec._parsec import DateTime
from parsec.serde import SerdeValidationError, SerdePackingError
from parsec.api.protocol import OrganizationID, UserProfile
from parsec.api.rest import (
    organization_config_rep_serializer,
    organization_create_req_serializer,
    organization_create_rep_serializer,
    organization_update_req_serializer,
    organization_stats_rep_serializer,
    server_stats_rep_serializer,
)
from parsec.backend.organization import (
    OrganizationAlreadyExistsError,
    OrganizationNotFoundError,
    OrganizationStats,
    generate_bootstrap_token,
)

if TYPE_CHECKING:
    from parsec.backend.app import BackendApp

T = TypeVar("T")
P = ParamSpec("P")

administration_bp = Blueprint("administration_api", __name__)


def _convert_server_stats_results_as_csv(stats: Dict[OrganizationID, OrganizationStats]) -> str:
    # Use `newline=""` to let the CSV writer handles the newlines
    with StringIO(newline="") as memory_file:
        writer = csv.writer(memory_file)
        # Header
        writer.writerow(
            [
                "organization_id",
                "data_size",
                "metadata_size",
                "realms",
                "active_users",
                "admin_users_active",
                "admin_users_revoked",
                "standard_users_active",
                "standard_users_revoked",
                "outsider_users_active",
                "outsider_users_revoked",
            ]
        )

        def _find_profile_counts(profile: UserProfile) -> Tuple[int, int]:
            detail = next(x for x in org_stats.users_per_profile_detail if x.profile == profile)
            return (detail.active, detail.revoked)

        for organization_id, org_stats in stats.items():
            csv_row = [
                organization_id.str,
                org_stats.data_size,
                org_stats.metadata_size,
                org_stats.realms,
                org_stats.active_users,
                *_find_profile_counts(UserProfile.ADMIN),
                *_find_profile_counts(UserProfile.STANDARD),
                *_find_profile_counts(UserProfile.OUTSIDER),
            ]
            writer.writerow(csv_row)

        return memory_file.getvalue()


def administration_authenticated(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        authorization = request.headers.get("Authorization")
        if authorization != f"Bearer {g.backend.config.administration_token}":
            await json_abort({"error": "not_allowed"}, 403)
        return await fn(*args, **kwargs)

    return wrapper


async def json_abort(data: dict[str, Any], status: int) -> NoReturn:
    response = await make_response(jsonify(data), status)
    abort(response)


async def load_req_data(req_serializer: JSONSerializer) -> dict[str, Any]:
    raw = await request.get_data()
    try:
        return req_serializer.loads(raw)  # type: ignore[arg-type]
    except SerdeValidationError as exc:
        await json_abort({"error": "bad_data", "reason": exc.errors}, 400)
    except SerdePackingError:
        await json_abort({"error": "bad_data", "reason": "Invalid JSON"}, 400)


def make_rep_response(
    rep_serializer: JSONSerializer, data: dict[str, Any], **kwargs: Any
) -> Response:
    return current_app.response_class(
        rep_serializer.dumps(data), content_type=current_app.config["JSONIFY_MIMETYPE"], **kwargs
    )


@administration_bp.route("/administration/organizations", methods=["POST"])
@administration_authenticated
async def administration_create_organizations() -> Response:  # type: ignore[misc]
    backend: "BackendApp" = current_app.backend  # type: ignore[attr-defined]
    data = await load_req_data(organization_create_req_serializer)

    organization_id = data.pop("organization_id")
    bootstrap_token = generate_bootstrap_token()
    try:
        await backend.organization.create(
            id=organization_id, bootstrap_token=bootstrap_token, created_on=DateTime.now(), **data
        )
    except OrganizationAlreadyExistsError:
        await json_abort({"error": "already_exists"}, 400)

    return make_rep_response(
        organization_create_rep_serializer, data={"bootstrap_token": bootstrap_token}, status=200
    )


@administration_bp.route(
    "/administration/organizations/<raw_organization_id>", methods=["GET", "PATCH"]
)
@administration_authenticated
async def administration_organization_item(raw_organization_id: str) -> Response:  # type: ignore[misc]
    backend: "BackendApp" = g.backend
    try:
        organization_id = OrganizationID(raw_organization_id)
    except ValueError:
        await json_abort({"error": "not_found"}, 404)
    # Check whether the organization actually exists
    try:
        organization = await backend.organization.get(id=organization_id)
    except OrganizationNotFoundError:
        await json_abort({"error": "not_found"}, 404)

    if request.method == "GET":

        return make_rep_response(
            organization_config_rep_serializer,
            data={
                "is_bootstrapped": organization.is_bootstrapped(),
                "is_expired": organization.is_expired,
                "user_profile_outsider_allowed": organization.user_profile_outsider_allowed,
                "active_users_limit": organization.active_users_limit,
            },
            status=200,
        )

    else:
        assert request.method == "PATCH"

        data = await load_req_data(organization_update_req_serializer)

        try:
            await backend.organization.update(id=organization_id, **data)
        except OrganizationNotFoundError:
            await json_abort({"error": "not_found"}, 404)

        return make_rep_response(organization_config_rep_serializer, data={}, status=200)


@administration_bp.route(
    "/administration/organizations/<raw_organization_id>/stats", methods=["GET"]
)
@administration_authenticated
async def administration_organization_stat(raw_organization_id: str) -> Response:  # type: ignore[misc]
    backend: "BackendApp" = g.backend
    try:
        organization_id = OrganizationID(raw_organization_id)
    except ValueError:
        await json_abort({"error": "not_found"}, 404)

    try:
        stats = await backend.organization.stats(id=organization_id)
    except OrganizationNotFoundError:
        await json_abort({"error": "not_found"}, 404)

    return make_rep_response(
        organization_stats_rep_serializer,
        data={
            "status": "ok",
            "realms": stats.realms,
            "data_size": stats.data_size,
            "metadata_size": stats.metadata_size,
            "users": stats.users,
            "active_users": stats.active_users,
            "users_per_profile_detail": stats.users_per_profile_detail,
        },
        status=200,
    )


@administration_bp.route("/administration/stats", methods=["GET"])
@administration_authenticated
async def administration_server_stats():
    backend: "BackendApp" = g.backend

    if request.args.get("format") not in ("csv", "json"):
        return await json_abort(
            {
                "error": "bad_data",
                "reason": f"Missing/invalid mandatory query argument `format` (expected `csv` or `json`)",
            },
            400,
        )

    try:
        raw_at = request.args.get("at")
        at = DateTime.from_rfc3339(raw_at) if raw_at else None
        server_stats = await backend.organization.server_stats(at=at)
    except ValueError:
        return await json_abort(
            {
                "error": "bad_data",
                "reason": "Invalid `at` query argument (expected RFC3339 datetime)",
            },
            400,
        )

    if request.args["format"] == "csv":
        csv_data = _convert_server_stats_results_as_csv(server_stats)
        return current_app.response_class(
            csv_data,
            content_type="text/csv",
            status=200,
        )

    else:
        return make_rep_response(
            server_stats_rep_serializer,
            data={
                "stats": [
                    {
                        "organization_id": organization_id.str,
                        "data_size": org_stats.data_size,
                        "metadata_size": org_stats.metadata_size,
                        "realms": org_stats.realms,
                        "active_users": org_stats.active_users,
                        "users_per_profile_detail": org_stats.users_per_profile_detail,
                    }
                    for organization_id, org_stats in server_stats.items()
                ]
            },
            status=200,
        )
