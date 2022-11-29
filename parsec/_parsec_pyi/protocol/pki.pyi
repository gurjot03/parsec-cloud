# Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 (eventually AGPL-3.0) 2016-present Scille SAS
from parsec._parsec import EnrollmentID, DateTime

# Pki commands
class PkiEnrollmentAcceptReq:
    def __init__(
        self,
        accept_payload: bytes,
        accept_payload_signature: bytes,
        accepter_der_x509_certificate: bytes,
        enrollment_id: EnrollmentID,
        device_certificate: bytes,
        user_certificate: bytes,
        redacted_device_certificate: bytes,
        redacted_user_certificate: bytes,
    ) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def accept_payload(self) -> bytes: ...
    @property
    def accept_payload_signature(self) -> bytes: ...
    @property
    def accepter_der_x509_certificate(self) -> bytes: ...
    @property
    def enrollment_id(self) -> EnrollmentID: ...
    @property
    def device_certificate(self) -> bytes: ...
    @property
    def user_certificate(self) -> bytes: ...
    @property
    def redacted_device_certificate(self) -> bytes: ...
    @property
    def redacted_user_certificate(self) -> bytes: ...

class PkiEnrollmentAcceptRep: ...
class PkiEnrollmentAcceptRepOk(PkiEnrollmentAcceptRep): ...

class PkiEnrollmentAcceptRepNotAllowed(PkiEnrollmentAcceptRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentAcceptRepInvalidPayloadData(PkiEnrollmentAcceptRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentAcceptRepInvalidCertification(PkiEnrollmentAcceptRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentAcceptRepInvalidData(PkiEnrollmentAcceptRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentAcceptRepNotFound(PkiEnrollmentAcceptRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentAcceptRepNoLongerAvailable(PkiEnrollmentAcceptRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentAcceptRepAlreadyExists(PkiEnrollmentAcceptRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentAcceptRepActiveUsersLimitReached(PkiEnrollmentAcceptRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentInfoReq:
    def dump(self) -> bytes: ...
    @property
    def enrollment_id(self) -> EnrollmentID: ...

class PkiEnrollmentInfoRep: ...

class PkiEnrollmentInfoRepOk(PkiEnrollmentInfoRep):
    def __init__(self, info_status: PkiEnrollmentInfoStatus) -> None: ...
    @property
    def enrollment_status(self) -> PkiEnrollmentInfoStatus: ...
    @property
    def cancelled_on(self) -> DateTime: ...
    @property
    def rejected_on(self) -> DateTime: ...
    @property
    def accepted_on(self) -> DateTime: ...
    @property
    def accepter_der_x509_certificate(self) -> bytes: ...
    @property
    def accept_payload_signature(self) -> bytes: ...
    @property
    def accept_payload(self) -> bytes: ...

class PkiEnrollmentInfoRepNotFound(PkiEnrollmentInfoRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentInfoStatus:
    @classmethod
    def Submitted(cls, submitted_on: DateTime) -> PkiEnrollmentInfoStatus: ...
    @classmethod
    def Accepted(
        cls,
        submitted_on: DateTime,
        accepted_on: DateTime,
        accepter_der_x509_certificate: bytes,
        accept_payload_signature: bytes,
        accept_payload: bytes,
    ) -> PkiEnrollmentInfoStatus: ...
    @classmethod
    def Rejected(cls, submitted_on: DateTime, rejected_on: DateTime) -> PkiEnrollmentInfoStatus: ...
    @classmethod
    def Cancelled(
        cls, submitted_on: DateTime, rejected_on: DateTime
    ) -> PkiEnrollmentInfoStatus: ...
    def is_submitted(self) -> bool: ...
    def is_cancelled(self) -> bool: ...
    def is_accepted(self) -> bool: ...
    def is_rejected(self) -> bool: ...

class PkiEnrollmentListItem:
    def __init__(
        self,
        enrollment_id: EnrollmentID,
        submit_payload: bytes,
        submit_payload_signature: bytes,
        submitted_on: DateTime,
        submitter_der_x509_certificate: bytes,
    ) -> None: ...
    @property
    def enrollment_id(self) -> EnrollmentID: ...
    @property
    def submit_payload(self) -> bytes: ...
    @property
    def submit_payload_signature(self) -> bytes: ...
    @property
    def submitted_on(self) -> DateTime: ...
    @property
    def submitter_der_x509_certificate(self) -> bytes: ...

class PkiEnrollmentListReq:
    def __init__(self) -> None: ...
    def dump(self) -> bytes: ...

class PkiEnrollmentListRep: ...

class PkiEnrollmentListRepNotAllowed(PkiEnrollmentListRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentListRepOk(PkiEnrollmentListRep):
    def __init__(self, enrollments: list[PkiEnrollmentListItem]) -> None: ...
    @property
    def enrollments(self) -> list[PkiEnrollmentListItem]: ...

class PkiEnrollmentRejectReq:
    def __init__(self, enrollment_id: EnrollmentID) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def enrollment_id(self) -> EnrollmentID: ...

class PkiEnrollmentRejectRep: ...

class PkiEnrollmentRejectRepNotAllowed(PkiEnrollmentRejectRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentRejectRepNotFound(PkiEnrollmentRejectRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentRejectRepNoLongerAvailable(PkiEnrollmentRejectRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentRejectRepOk(PkiEnrollmentRejectRep): ...

class PkiEnrollmentAcceptRepUnknownStatus:
    def __init__(self, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentInfoRepUnknownStatus:
    def __init__(self, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentListRepUnknownStatus:
    def __init__(self, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentRejectRepUnknownStatus:
    def __init__(self, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentSubmitReq:
    def __init__(
        self,
        enrollment_id: EnrollmentID,
        force: bool,
        submitter_der_x509_certificate: bytes,
        submitter_der_x509_certificate_email: str | None,
        submit_payload_signature: bytes,
        submit_payload: bytes,
    ) -> None: ...
    def dump(self) -> bytes: ...
    @property
    def enrollment_id(self) -> EnrollmentID: ...
    @property
    def force(self) -> bool: ...
    @property
    def submitter_der_x509_certificate(self) -> bytes: ...
    @property
    def submitter_der_x509_certificate_email(self) -> str | None: ...
    @property
    def submit_payload_signature(self) -> bytes: ...
    @property
    def submit_payload(self) -> bytes: ...

class PkiEnrollmentSubmitRep: ...

class PkiEnrollmentSubmitRepAlreadySubmitted(PkiEnrollmentSubmitRep):
    def __init__(self, submitted_on: DateTime) -> None: ...
    @property
    def submitted_on(self) -> DateTime: ...

class PkiEnrollmentSubmitRepIdAlreadyUsed(PkiEnrollmentSubmitRep):
    def __init__(self) -> None: ...

class PkiEnrollmentSubmitRepEmailAlreadyUsed(PkiEnrollmentSubmitRep):
    def __init__(self) -> None: ...

class PkiEnrollmentSubmitRepAlreadyEnrolled(PkiEnrollmentSubmitRep):
    def __init__(self) -> None: ...

class PkiEnrollmentSubmitRepInvalidPayloadData(PkiEnrollmentSubmitRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def reason(self) -> str | None: ...

class PkiEnrollmentSubmitRepOk(PkiEnrollmentSubmitRep):
    def __init__(self, submitted_on: DateTime) -> None: ...
    @property
    def submitted_on(self) -> DateTime: ...

class PkiEnrollmentSubmitRepUnknownStatus(PkiEnrollmentSubmitRep):
    def __init__(self, reason: str | None) -> None: ...
    @property
    def status(self) -> str: ...
    @property
    def reason(self) -> str | None: ...
