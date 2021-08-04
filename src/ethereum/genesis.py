"""
Genesis Config Related Functionalities
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

..contents:: Table of Contents
    :backlinks: none
    :local:

Introduction
------------

Functionalities to load the genesis configs and the configurations for
different chains.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from ethereum.base_types import U256, Bytes, Bytes8, Uint, slotted_freezable
from ethereum.frontier.eth_types import Address

from .utils import (
    hex_to_address,
    hex_to_bytes,
    hex_to_bytes8,
    hex_to_u256,
    hex_to_uint,
)


@slotted_freezable
@dataclass
class GenesisConfig:
    """
    Genesis Config has the alloc data for the pre-sale of ether and some
    fields of the genesis block.
    """

    difficulty: Uint
    extra_data: Bytes
    gas_limit: Uint
    nonce: Bytes8
    timestamp: U256
    alloc: Dict[Address, Dict[str, U256]]


def load_genesis_config(genesis_file: str) -> GenesisConfig:
    """
    Obtain the genesis config, which includes the alloc data, based on the
    given genesis json file.

    Parameters
    ----------
    genesis_file :
        The json file which contains the parameters for the genesis block
        and the alloc data.

    Returns
    -------
    genesis_config : `GenesisConfig`
        The genesis config obtained from the json genesis file.
    """
    with open(genesis_file, "r") as genesis_file_handler:
        genesis_data = json.load(genesis_file_handler)

    alloc_data = {
        hex_to_address(address): {"balance": hex_to_u256(account["balance"])}
        for address, account in genesis_data["alloc"].items()
    }

    return GenesisConfig(
        difficulty=hex_to_uint(genesis_data["difficulty"]),
        extra_data=hex_to_bytes(genesis_data["extraData"]),
        gas_limit=hex_to_uint(genesis_data["gasLimit"]),
        nonce=hex_to_bytes8(genesis_data["nonce"]),
        timestamp=hex_to_u256(genesis_data["timestamp"]),
        alloc=alloc_data,
    )


ASSETS_DIR = Path(__file__).parent / "assets"

MAINNET_GENESIS_CONFIG = load_genesis_config(f"{ASSETS_DIR}/mainnet.json")
