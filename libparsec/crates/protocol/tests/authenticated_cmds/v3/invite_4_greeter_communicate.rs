// Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 2016-present Scille SAS

// `allow-unwrap-in-test` don't behave as expected, see:
// https://github.com/rust-lang/rust-clippy/issues/11119
#![allow(clippy::unwrap_used)]

use libparsec_tests_lite::{hex, p_assert_eq};
use libparsec_types::InvitationToken;

use super::authenticated_cmds;

// Request

pub fn req() {
    // Generated from Python implementation (Parsec v2.6.0+dev)
    // Content:
    //   cmd: "invite_4_greeter_communicate"
    //   payload: hex!("666f6f626172")
    //   token: ext(2, hex!("d864b93ded264aae9ae583fd3d40c45a"))
    let raw = hex!(
        "83a3636d64bc696e766974655f345f677265657465725f636f6d6d756e6963617465a77061"
        "796c6f6164c406666f6f626172a5746f6b656ed802d864b93ded264aae9ae583fd3d40c45a"
    );

    let req = authenticated_cmds::invite_4_greeter_communicate::Req {
        token: InvitationToken::from_hex("d864b93ded264aae9ae583fd3d40c45a").unwrap(),
        payload: b"foobar".as_ref().into(),
    };

    let expected = authenticated_cmds::AnyCmdReq::Invite4GreeterCommunicate(req);

    let data = authenticated_cmds::AnyCmdReq::load(&raw).unwrap();

    p_assert_eq!(data, expected);

    // Also test serialization round trip
    let authenticated_cmds::AnyCmdReq::Invite4GreeterCommunicate(req2) = data else {
        unreachable!()
    };
    let raw2 = req2.dump().unwrap();

    let data2 = authenticated_cmds::AnyCmdReq::load(&raw2).unwrap();

    p_assert_eq!(data2, expected);
}

// Responses

pub fn rep_ok() {
    // Generated from Python implementation (Parsec v2.6.0+dev)
    // Content:
    //   payload: hex!("666f6f626172")
    //   status: "ok"
    let raw = hex!("82a77061796c6f6164c406666f6f626172a6737461747573a26f6b");
    let expected = authenticated_cmds::invite_4_greeter_communicate::Rep::Ok {
        payload: b"foobar".as_ref().into(),
    };

    rep_helper(&raw, expected);
}

pub fn rep_not_found() {
    // Generated from Python implementation (Parsec v2.6.0+dev)
    // Content:
    //   status: "not_found"
    let raw = hex!("81a6737461747573a96e6f745f666f756e64");
    let expected = authenticated_cmds::invite_4_greeter_communicate::Rep::NotFound;

    rep_helper(&raw, expected);
}

pub fn rep_already_deleted() {
    // Generated from Python implementation (Parsec v2.6.0+dev)
    // Content:
    //   status: "already_deleted"
    let raw = hex!("81a6737461747573af616c72656164795f64656c65746564");
    let expected = authenticated_cmds::invite_4_greeter_communicate::Rep::AlreadyDeleted;

    rep_helper(&raw, expected);
}

pub fn rep_invalid_state() {
    // Generated from Python implementation (Parsec v2.6.0+dev)
    // Content:
    //   status: "invalid_state"
    let raw = hex!("81a6737461747573ad696e76616c69645f7374617465");
    let expected = authenticated_cmds::invite_4_greeter_communicate::Rep::InvalidState;

    rep_helper(&raw, expected);
}

fn rep_helper(raw: &[u8], expected: authenticated_cmds::invite_4_greeter_communicate::Rep) {
    let data = authenticated_cmds::invite_4_greeter_communicate::Rep::load(raw).unwrap();

    p_assert_eq!(data, expected);

    // Also test serialization round trip
    let raw2 = data.dump().unwrap();
    let data2 = authenticated_cmds::invite_4_greeter_communicate::Rep::load(&raw2).unwrap();

    p_assert_eq!(data2, expected);
}
