from typing import Any, List, Sequence, cast

import pytest

from ethereum.base_types import U256, Bytes
from ethereum.frontier import rlp
from ethereum.genesis import MAINNET_GENESIS_CONFIG
from ethereum.utils import to_valid_address


@pytest.fixture
def mainnet_alloc_rlp_encoding() -> bytes:
    with open("src/ethereum/assets/mainnet_genesis_alloc_rlp.hex") as fp:
        rlp_encoding_hex = fp.readline()

    return bytes.fromhex(rlp_encoding_hex)


def test_mainnet_alloc_rlp_encoding(mainnet_alloc_rlp_encoding: bytes) -> None:
    # Test RLP encoding of alloc is expected hex value
    alloc_rlp_encoding = rlp.encode(
        [
            [U256.from_be_bytes(address), acc["balance"]]
            for address, acc in MAINNET_GENESIS_CONFIG.alloc.items()
        ]
    )

    assert alloc_rlp_encoding == mainnet_alloc_rlp_encoding


def test_rlp_decode_mainnet_alloc_rlp_encoding(
    mainnet_alloc_rlp_encoding: bytes,
) -> None:
    # Test RLP decoding of the hex is the expected alloc
    decoded_alloc = cast(
        List[List[Bytes]], rlp.decode(mainnet_alloc_rlp_encoding)
    )
    obtained_alloc = {
        to_valid_address(addr): {"balance": U256.from_be_bytes(balance)}
        for (addr, balance) in decoded_alloc
    }

    assert obtained_alloc == MAINNET_GENESIS_CONFIG.alloc


def test_mainnet_genesis_config() -> None:
    # Test that mainnet genesis parameters are as expected
    assert MAINNET_GENESIS_CONFIG.difficulty == int("400000000", 16)
    assert MAINNET_GENESIS_CONFIG.extra_data == bytes.fromhex(
        "11bbe8db4e347b4e8c937c1c8370e4b5ed33adb3db69cbdb7a38e1e50b1b82fa"
    )
    assert MAINNET_GENESIS_CONFIG.gas_limit == 5000
    assert MAINNET_GENESIS_CONFIG.nonce == b"\x00\x00\x00\x00\x00\x00\x00\x42"
    assert MAINNET_GENESIS_CONFIG.timestamp == 0
