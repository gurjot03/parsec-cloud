// Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 (eventually AGPL-3.0) 2016-present Scille SAS

use thiserror::Error;

#[derive(Error, Debug, PartialEq, Eq)]
pub enum CryptoError {
    #[error("Unsupported algorithm")]
    Algorithm,
    #[error("Invalid signature")]
    Signature,
    #[error("Signature was forged or corrupt")]
    SignatureVerification,
    #[error("Invalid data size")]
    DataSize,
    #[error("Decryption error")]
    Decryption,
    #[error("Invalid key size")]
    KeySize,
    #[error("The nonce must be exactly 24 bytes long")]
    Nonce,
    #[error("Invalid SequesterPrivateKeyDer {0}")]
    SequesterPrivateKeyDer(rsa::pkcs8::Error),
    #[error("Invalid SequesterPublicKeyDer {0}")]
    SequesterPublicKeyDer(rsa::pkcs8::spki::Error),
}

pub type CryptoResult<T> = Result<T, CryptoError>;
