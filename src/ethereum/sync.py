import json

from ethereum.frontier.eth_types import Block, Header
from ethereum.frontier.spec import BlockChain, state_transition
from ethereum.store.blocks import get_block
from ethereum.base_types import Uint


def block_sync():
    chain = BlockChain(
        blocks=[],
        state={},
    )

    for block_number in range(1000):
        print(f"Trying to mine block {block_number}")
        block = get_block(Uint(block_number))
        state_transition(chain, block)
        print(f"Mined block {block_number}")
        print()
