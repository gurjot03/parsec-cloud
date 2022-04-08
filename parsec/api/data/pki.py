# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2016-2021 Scille SAS

import attr
from typing import Dict, Any, Optional

from parsec.crypto import PublicKey, VerifyKey
from parsec.serde import BaseSchema, fields, post_load
from parsec.api.protocol import (
    DeviceID,
    DeviceIDField,
    HumanHandle,
    HumanHandleField,
    DeviceLabel,
    DeviceLabelField,
)
from parsec.api.data.base import BaseAPIData
from parsec.api.data.certif import UserProfile, UserProfileField


@attr.s(slots=True, frozen=True, auto_attribs=True, kw_only=True, eq=False)
class PkiEnrollmentSubmitPayload(BaseAPIData):
    class SCHEMA_CLS(BaseSchema):
        type = fields.CheckedConstant("pki_enrollment_submit_payload", required=True)
        verify_key = fields.VerifyKey(required=True)
        public_key = fields.PublicKey(required=True)
        requested_device_label = DeviceLabelField(required=True)
        # No requested human handle given the accepter should use instead the
        # information from the submitter's X509 certificate

        @post_load
        def make_obj(self, data: Dict[str, Any]) -> "PkiEnrollmentSubmitPayload":
            data.pop("type")
            return PkiEnrollmentSubmitPayload(**data)

    verify_key: VerifyKey
    public_key: PublicKey
    requested_device_label: DeviceLabel


@attr.s(slots=True, frozen=True, auto_attribs=True, kw_only=True, eq=False)
class PkiEnrollmentAcceptPayload(BaseAPIData):
    class SCHEMA_CLS(BaseSchema):
        type = fields.CheckedConstant("pki_enrollment_answer_payload", required=True)
        device_id = DeviceIDField(required=True)
        device_label = DeviceLabelField(allow_none=True, missing=None)
        human_handle = HumanHandleField(allow_none=True, missing=None)
        profile = UserProfileField(required=True)
        root_verify_key = fields.VerifyKey(required=True)

        @post_load
        def make_obj(self, data: Dict[str, Any]) -> "PkiEnrollmentAcceptPayload":
            data.pop("type")
            return PkiEnrollmentAcceptPayload(**data)

    device_id: DeviceID
    device_label: Optional[DeviceLabel]
    human_handle: Optional[HumanHandle]
    profile: UserProfile
    root_verify_key: VerifyKey