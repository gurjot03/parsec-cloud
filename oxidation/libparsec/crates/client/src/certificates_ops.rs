// Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 (eventually AGPL-3.0) 2016-present Scille SAS

#![allow(dead_code)]

use std::{path::Path, sync::Arc};

use libparsec_client_connection::{AuthenticatedCmds, CommandError};
use libparsec_platform_storage2::certificates::{CertificatesStorage, GetCertificateError};
use libparsec_protocol::authenticated_cmds;
use libparsec_types::prelude::*;

use crate::event_bus::EventBus;

pub type DynError = Box<dyn std::error::Error + Send + Sync>;

pub enum Author {
    OrganizationBootstrap,
    Device(DeviceID),
}

pub struct UserInfo {
    author: Author,
    created_on: DateTime,
    revoked_on: Option<DateTime>,
    profile: UserProfile,
}

#[derive(Debug, thiserror::Error)]
pub struct TodoError(&'static str);

#[derive(Debug, thiserror::Error)]
pub enum SecureLoadError {
    #[error("Server not currently available")]
    Offline,
    #[error("Corrupted data: {0}")]
    CorruptedData(DataError),
}

#[derive(Debug)]
pub struct CertificatesOps {
    device: Arc<LocalDevice>,
    event_bus: EventBus,
    cmds: Arc<AuthenticatedCmds>,
    storage: CertificatesStorage,
}

#[derive(Debug, thiserror::Error)]
pub enum AddNewCertficateError {
    #[error("Invalid certificate: {0}")]
    InvalidCertificate
    #[error("Internal error: {0}")]
    Internal(DynError),
    #[error("Server returned an error: {0}")]
    ServerCmd(CommandError),
    #[error("Cannot communicate with the server")]
    Offline,
}

impl CertificatesOps {
    pub async fn new(
        data_base_dir: &Path,
        device: Arc<LocalDevice>,
        event_bus: EventBus,
        cmds: Arc<AuthenticatedCmds>,
    ) -> Result<Self, DynError> {
        let storage = CertificatesStorage::start(data_base_dir, device.clone()).await?;
        Ok(Self {
            device,
            event_bus,
            cmds,
            storage,
        })
    }

    pub async fn stop(&self) {
        self.storage.stop().await;
    }

    async fn get_device_certificate(
        &self,
        device_id: &DeviceID,
    ) -> Result<Option<Arc<DeviceCertificate>>, TodoError> {
        match self.storage.get_device_certificate(device_id).await {
            Err(err) => Err(TodoError(
                "Internal error while trying to retrieve certificate from local database",
            )),
            Ok(Some(certif)) => Ok(certif),
            Ok(None) => {
                self.fetch_new_certificates_from_server()
                    .await
                    .map_err(|err| err.into())?;
                match self
                    .storage
                    .get_device_certificate(device_id)
                    .await
                    .map_err(|err| TodoError(TodoError("Internal error while trying to retrieve certificate from local database")))?
                {
                    Some(certif) => Ok(certif),
                    None => Err(TodoError("We looked everywhere, this certificate doesn't exist !")),
                }
            }
        }
    }

    // pub async fn secure_load_user_manifest(
    //     &self,
    //     blob: &[u8],
    //     expected_id: EntryID,
    //     expected_author: &DeviceID,
    //     expected_timestamp: DateTime,
    //     expected_version: Option<VersionInt>,
    // ) -> Result<Arc<UserManifest>, SecureLoadError> {
    //     let expected_author = self.get_device_certificate(expected_author).await?;

    //     let user_manifest = UserManifest::decrypt_verify_and_load(
    //         blob,
    //         &self.device.user_manifest_key,
    //         &expected_author.verify_key,
    //         &expected_author.device_id,
    //         expected_timestamp,
    //         Some(expected_id),
    //         expected_version,
    //     )
    //     .map_err(SecureLoadError::CorruptedData)?;

    //     // No rules to enforce: only the user can access it own user manifest, and this
    //     // access is total and forever

    //     Ok(Arc::new(user_manifest))
    // }

    pub async fn fetch_new_certificates_from_server(&self) -> Result<(), TodoError> {
        let last_timestamp = self
            .storage
            .get_last_certificate_timestamp()
            .await
            .map_err(|_| TodoError("Internal error while trying to compute last certificate timestamp from local database"))?;
        let request = authenticated_cmds::latest::certificate_get::Req {
            // Note this is `None` if our local storage is empty, meaning we want to fetch everything !
            created_after: last_timestamp,
        };
        match self.cmds.send(request).await {
            Ok(authenticated_cmds::latest::certificate_get::Rep::Ok { certificates }) => {
                for certificate in certificates {
                    // TODO: error handling
                    self.add_new_certificate(certificate).await.unwrap();
                }
                Ok(())
            }
            Ok(authenticated_cmds::latest::certificate_get::Rep::UnknownStatus { .. }) => {
                todo!()
            }
            Err(CommandError::NoResponse(_)) => {
                Err(CertificatesOpsRetreiveNewCertificatesFromServerError::Offline)
            }
            Err(err) => Err(CertificatesOpsRetreiveNewCertificatesFromServerError::ServerCmd(err)),
        }
    }

    pub async fn add_new_certificate(
        &self,
        certificate: Bytes,
    ) -> Result<(), AddNewCertficateError> {
        match AnyCertificate::unsecure_load(certificate)? {
            UnsecureAnyCertificate::User(unsecure) => {
                // TODO: actually do the certificate verification !
                let validated = unsecure
                    .skip_validation(UnsecureSkipValidationReason::TodoValidationNotYetImplemented);
                // TODO: error handling
                self.storage
                    .add_new_user_certificate(Arc::new(validated), certificate)
                    .await
                    .unwrap();
            }
            UnsecureAnyCertificate::Device(unsecure) => {
                // TODO: actually do the certificate verification !
                let validated = unsecure
                    .skip_validation(UnsecureSkipValidationReason::TodoValidationNotYetImplemented);
                // TODO: error handling
                self.storage
                    .add_new_device_certificate(Arc::new(validated), certificate)
                    .await
                    .unwrap();
            }
            UnsecureAnyCertificate::RevokedUser(unsecure) => {
                // TODO: actually do the certificate verification !
                let validated = unsecure
                    .skip_validation(UnsecureSkipValidationReason::TodoValidationNotYetImplemented);
                // TODO: error handling
                self.storage
                    .add_new_revoked_user_certificate(Arc::new(validated), certificate)
                    .await
                    .unwrap();
            }
            UnsecureAnyCertificate::RealmRole(unsecure) => {
                // TODO: actually do the certificate verification !
                let validated = unsecure
                    .skip_validation(UnsecureSkipValidationReason::TodoValidationNotYetImplemented);
                // TODO: error handling
                self.storage
                    .add_new_realm_role_certificate(Arc::new(validated), certificate)
                    .await
                    .unwrap();
            }
        }
        Ok(())
    }
}
