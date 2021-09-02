from collections import deque, OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from ethereum.base_types import Uint
from ethereum.frontier.eth_types import Hash32, Header
import requests

from ethereum.utils import json_to_header


@dataclass
class OmmerInfo:
    json_data: Dict[Any, Any]
    ommer: Header


ommer_store: Dict[Hash32, OmmerInfo] = OrderedDict()


def get_ommers_info(block_number: Uint, ommer_hashes: Tuple[Hash32, ...]) -> List[OmmerInfo]:
    if not ommer_hashes:
        return []

    ommers_info = []

    for ommer_index, ommer_hash in enumerate(ommer_hashes):
        if ommer_hash not in ommer_store:
            remove_unnecessary_ommers(block_number)
            ommer_json_data = fetch_ommer(block_number, ommer_index)
            ommer_data = json_to_header(ommer_json_data)
            ommer_store[ommer_hash] = OmmerInfo(
                json_data=ommer_json_data,
                ommer=ommer_data
            )

        ommers_info.append(ommer_store[ommer_hash])

    return ommers_info


def fetch_ommer(block_number: Uint, ommer_index: int) -> Dict[Any, Any]:
    url = "https://mainnet.infura.io/v3/1619768b414344a987cbb8d14ca4f05c"
    headers = {"Content-Type": "application/json"}
    data = (
        '{{"jsonrpc": "2.0", "method": "eth_getUncleByBlockNumberAndIndex", '
        '"params": ["{}", "{}"], "id": 1}}'
        .format(hex(block_number), hex(ommer_index))
    )
    response = requests.post(url=url, headers=headers, data=data)
    assert response.status_code == 200

    return response.json()['result']


def remove_unnecessary_ommers(current_block_number):
    if current_block_number <= 6:
        # No ommers to remove
        return

    # The minimum block number to be held by a valid ommer block for the
    # current block
    min_valid_ommer_number = current_block_number - 6

    global ommer_store
    ommer_store = OrderedDict()

    # TODO: Removing the list below raises an error "RuntimeError: OrderedDict mutated during iteration"
    #  Hence add test cases for this.
    for ommer_info in list(ommer_store.values()):
        if ommer_info.ommer.number < min_valid_ommer_number:
            ommer_store.popitem()
        else:
            break
