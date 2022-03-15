// Parsec Cloud (https://parsec.cloud) Copyright (c) BSLv1.1 (eventually AGPLv3) 2016-2021 Scille SAS

use hex_literal::hex;
use rstest::rstest;

use parsec_api_protocol::*;

#[rstest]
fn serde_block_create_req() {
    // Generated from Python implementation (Parsec v2.6.0+dev)
    // Content:
    //   block: hex!("666f6f626172")
    //   block_id: ext(2, hex!("57c629b69d6c4abbaf651cafa46dbc93"))
    //   cmd: "block_create"
    //   realm_id: ext(2, hex!("1d3353157d7d4e95ad2fdea7b3bd19c5"))
    let data = hex!(
        "84a5626c6f636bc406666f6f626172a8626c6f636b5f6964d80257c629b69d6c4abbaf651c"
        "afa46dbc93a3636d64ac626c6f636b5f637265617465a87265616c6d5f6964d8021d335315"
        "7d7d4e95ad2fdea7b3bd19c5"
    );

    let expected = Cmd {
        cmd: "block_create",
        req: BlockCreateReq {
            block_id: "57c629b69d6c4abbaf651cafa46dbc93".parse().unwrap(),
            realm_id: "1d3353157d7d4e95ad2fdea7b3bd19c5".parse().unwrap(),
            block: b"foobar".to_vec(),
        },
    };

    let schema = Cmd::loads(&data);

    assert_eq!(schema, expected);

    // Also test serialization round trip
    let data2 = Authenticated::dumps(&expected.req).unwrap();
    let schema2 = Cmd::loads(&data2);
    assert_eq!(schema2, expected);
}

#[rstest]
#[case::ok(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "ok"
        &hex!(
            "81a6737461747573a26f6b"
        )[..],
        BlockCreateRep::Ok
    )
)]
#[case::already_exists(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "already_exists"
        &hex!(
            "81a6737461747573ae616c72656164795f657869737473"
        )[..],
        BlockCreateRep::AlreadyExists
    )
)]
#[case::not_found(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "not_found"
        &hex!(
            "81a6737461747573a96e6f745f666f756e64"
        )[..],
        BlockCreateRep::NotFound
    )
)]
#[case::timeout(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "timeout"
        &hex!(
            "81a6737461747573a774696d656f7574"
        )[..],
        BlockCreateRep::Timeout
    )
)]
#[case::not_allowed(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "not_allowed"
        &hex!(
            "81a6737461747573ab6e6f745f616c6c6f776564"
        )[..],
        BlockCreateRep::NotAllowed
    )
)]
#[case::in_maintenance(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "in_maintenance"
        &hex!(
            "81a6737461747573ae696e5f6d61696e74656e616e6365"
        )[..],
        BlockCreateRep::InMaintenance
    )
)]
fn serde_block_create_rep(#[case] data_expected: (&[u8], BlockCreateRep)) {
    let (data, expected) = data_expected;

    let schema = BlockCreateRep::load(&data).unwrap();

    assert_eq!(schema, expected);

    // Also test serialization round trip
    let data2 = schema.dump();
    let schema2 = BlockCreateRep::load(&data2).unwrap();
    assert_eq!(schema2, expected);
}

#[rstest]
fn serde_block_read_req() {
    // Generated from Python implementation (Parsec v2.6.0+dev)
    // Content:
    //   block_id: ext(2, hex!("57c629b69d6c4abbaf651cafa46dbc93"))
    //   cmd: "block_read"
    let data = hex!(
        "82a8626c6f636b5f6964d80257c629b69d6c4abbaf651cafa46dbc93a3636d64aa626c6f63"
        "6b5f72656164"
    );

    let expected = Cmd {
        cmd: "block_read",
        req: BlockReadReq {
            block_id: "57c629b69d6c4abbaf651cafa46dbc93".parse().unwrap(),
        },
    };

    let schema = Cmd::loads(&data);

    assert_eq!(schema, expected);

    // Also test serialization round trip
    let data2 = Authenticated::dumps(&expected.req).unwrap();
    let schema2 = Cmd::loads(&data2);
    assert_eq!(schema2, expected);
}

#[rstest]
#[case::ok(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   block: hex!("666f6f626172")
        //   status: "ok"
        &hex!(
            "82a5626c6f636bc406666f6f626172a6737461747573a26f6b"
        )[..],
        BlockReadRep::Ok {
            block: b"foobar".to_vec(),
        }
    )
)]
#[case::not_found(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "not_found"
        &hex!(
            "81a6737461747573a96e6f745f666f756e64"
        )[..],
        BlockReadRep::NotFound
    )
)]
#[case::timeout(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "timeout"
        &hex!(
            "81a6737461747573a774696d656f7574"
        )[..],
        BlockReadRep::Timeout
    )
)]
#[case::not_allowed(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "not_allowed"
        &hex!(
            "81a6737461747573ab6e6f745f616c6c6f776564"
        )[..],
        BlockReadRep::NotAllowed
    )
)]
#[case::in_maintenance(
    (
        // Generated from Python implementation (Parsec v2.6.0+dev)
        // Content:
        //   status: "in_maintenance"
        &hex!(
            "81a6737461747573ae696e5f6d61696e74656e616e6365"
        )[..],
        BlockReadRep::InMaintenance
    )
)]
fn serde_block_read_rep(#[case] data_expected: (&[u8], BlockReadRep)) {
    let (data, expected) = data_expected;

    let schema = BlockReadRep::load(&data).unwrap();

    assert_eq!(schema, expected);

    // Also test serialization round trip
    let data2 = schema.dump();
    let schema2 = BlockReadRep::load(&data2).unwrap();
    assert_eq!(schema2, expected);
}
