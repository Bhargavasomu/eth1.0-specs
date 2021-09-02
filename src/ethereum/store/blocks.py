from typing import Any, Dict
import plyvel
import json
import requests
from copy import deepcopy

from ethereum.frontier.eth_types import Block, Uint
from ethereum.store.ommers import get_ommers_info
from ethereum.utils import hex_to_hash, json_to_block, json_to_header


blocks_store = plyvel.DB('blocksDB', create_if_missing=True, lru_cache_size=512)

def get_block(block_number: Uint) -> Block:
    block = load_block_from_store(block_number)
    if block is not None:
        return block

    block_json_data = fetch_block(block_number)
    ommer_hashes = [
        hex_to_hash(hex_hash)
        for hex_hash in block_json_data['uncles']
    ]
    ommers_info = get_ommers_info(block_number, ommer_hashes)

    ommers = []
    ommers_json_data = []
    for ommer_info in ommers_info:
        ommers.append(ommer_info.ommer)
        ommers_json_data.append(ommer_info.json_data)

    block = json_to_block(block_json_data, ommers)
    dump_block_to_store(block_number, block_json_data, ommers_json_data)

    return block


def load_block_from_store(block_number: Uint) -> Dict[Any, Any]:
    block_json_bytes = blocks_store.get(block_number.to_be_bytes(), default=None)
    if block_json_bytes is None:
        return None

    block_json = block_json_bytes.decode("utf-8")
    block_json_data = json.loads(block_json)
    ommers = [
        json_to_header(ommer_json)
        for ommer_json in block_json_data['ommers']
    ]

    return json_to_block(block_json_data, ommers)


def dump_block_to_store(block_number, raw_block_json_data, ommers_json_data) -> None:
    # raw_block_json_data doesn't have the ommers data, and hence it is
    # called as the raw block json data. TODO: Add this line to the docstring
    # of this function.
    block_json_data = deepcopy(raw_block_json_data)
    block_json_data['ommers'] = deepcopy(ommers_json_data)
    json_data_bytes = bytes(json.dumps(block_json_data), 'utf-8')
    blocks_store.put(block_number.to_be_bytes(), json_data_bytes)


def fetch_block(block_number: Uint):
    url = "https://mainnet.infura.io/v3/1619768b414344a987cbb8d14ca4f05c"
    headers = {"Content-Type": "application/json"}
    data = (
        '{{"jsonrpc": "2.0", "method": "eth_getBlockByNumber", '
        '"params": ["{}", true], "id": 1}}'
        .format(hex(block_number))
    )
    response = requests.post(url=url, headers=headers, data=data)
    assert response.status_code == 200

    return response.json()['result']


# 1. If present in cache, return the block
# 2. If not present in cache, check the store.
#     a) If present in the store, read from that. Set dirty = False
#     b) If not present in the store, fetch from infura. Set dirty = True
# 3. Add this to the cache next


# # 1. Check if the hash is present in the cache. If yes, return that value.
# # 2. If not in the cache, read from the database.
# #     a) If not present in the database, then fetch the data and store it in cache. If the cache is full, then flush to database.
# #     b) If present in the database, read from this and update the cache. Since this is an lru cache, the item being popped might be dirty, in which case the greedy choice is to flush all the diry items.
