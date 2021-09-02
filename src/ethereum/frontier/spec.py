"""
Ethereum Specification
^^^^^^^^^^^^^^^^^^^^^^

.. contents:: Table of Contents
    :backlinks: none
    :local:

Introduction
------------

Entry point for the Ethereum specification.
"""

from dataclasses import dataclass
from typing import List, Tuple

from ethereum.frontier.bloom import logs_bloom
from ethereum.genesis import MAINNET_GENESIS_CONFIG

from .. import crypto
from ..base_types import U256, Uint
from . import rlp, trie, vm
from .eth_types import (
    EMPTY_ACCOUNT,
    TX_BASE_COST,
    TX_DATA_COST_PER_NON_ZERO,
    TX_DATA_COST_PER_ZERO,
    Account,
    Address,
    Block,
    Bloom,
    Hash32,
    Header,
    Log,
    Receipt,
    Root,
    State,
    Transaction,
    add_ether,
    modify_state,
    move_ether,
)
from .vm.interpreter import process_call

BLOCK_REWARD = U256(5 * 10 ** 18)
GAS_LIMIT_ADJUSTMENT_FACTOR = 1024
GAS_LIMIT_MINIMUM = 5000
GENESIS_DIFFICULTY = Uint(131072)


@dataclass
class BlockChain:
    """
    History and current state of the block chain.
    """

    blocks: List[Block]
    state: State


def get_recent_block_hashes(
    chain: BlockChain, num_blocks: Uint
) -> List[Hash32]:
    """
    Obtain the list of hashes of the previous `num_blocks` blocks in the
    order of increasing block number.

    Parameters
    ----------
    chain :
        History and current state.
    num_blocks :
        Number of recent block hashes one wishes to obtain.

    Returns
    -------
    recent_block_hashes : `List[Hash32]`
        Hashes of the recent `num_blocks` blocks in order of increasing
        block number.
    """
    # TODO: This function has not been tested rigorously
    if len(chain.blocks) == 0 or num_blocks == 0:
        return []

    # We are computing the hash only for the most recent block and not for
    # the rest of the blocks as they have successors which have the hash of
    # the current block as parent hash.
    most_recent_block_hash = crypto.keccak256(rlp.encode(chain.blocks[-1]))
    recent_block_hashes = [most_recent_block_hash]

    # We consider only the last `num_blocks - 1` blocks as we already have
    # the most recent block hash computed and need only `num_blocks - 1` more
    # hashes.
    recent_blocks = chain.blocks[-(num_blocks - 1) :]

    for block in reversed(recent_blocks):
        prev_block_hash = block.header.parent_hash
        recent_block_hashes.append(prev_block_hash)

    recent_block_hashes.reverse()
    return list(recent_block_hashes)


def state_transition(chain: BlockChain, block: Block) -> None:
    """
    Attempts to apply a block to an existing block chain.

    Parameters
    ----------
    chain :
        History and current state.
    block :
        Block to apply to `chain`.
    """
    # if block.header.number == 0:
    #     # TODO: Validate the genesis block
    #     chain.blocks.append(block)
    #     return

    # if block.header.number == 0:
    #     validate_genesis_block(block)
    # else:
    #     parent_header = get_block_header_by_hash(block.header.parent_hash, chain)
    #     validate_header(block.header, parent_header)

    if block.header.number == 0:
        validate_genesis_header(block.header)
        apply_prealloc(chain.state, MAINNET_GENESIS_CONFIG.alloc)
    else:
        parent_header = get_block_header_by_hash(block.header.parent_hash, chain)
        validate_header(block.header, parent_header)

    (
        gas_used,
        transactions_root,
        receipt_root,
        block_logs_bloom,
        state,
    ) = apply_body(
        chain.state,
        get_recent_block_hashes(chain, Uint(256)),
        block.header.coinbase,
        block.header.number,
        block.header.gas_limit,
        block.header.timestamp,
        block.header.difficulty,
        block.transactions,
        block.ommers,
    )

    assert gas_used == block.header.gas_used
    validate_ommers(
        block.ommers, block.header.ommers_hash, block.header.number, chain
    )
    assert transactions_root == block.header.transactions_root
    assert receipt_root == block.header.receipt_root
    assert trie.root(trie.map_keys(state)) == block.header.state_root
    assert block_logs_bloom == block.header.bloom

    chain.blocks.append(block)


def validate_header(header: Header, parent_header: Header) -> None:
    """
    Verifies a block header.

    Parameters
    ----------
    header :
        Header to check for correctness.
    parent_header :
        Parent Header of the header to check for correctness
    """
    # TODO: get rid of the comment below once
    #  check_proof_of_work is implemented
    # assert check_proof_of_work(header)
    assert header.difficulty == calculate_block_difficulty(
        header.number,
        header.timestamp,
        parent_header.timestamp,
        parent_header.difficulty,
    )

    # TODO: Check why all the blocks have the same gas limit as 5k instead of 125k
    assert check_gas_limit(header.gas_limit, parent_header.gas_limit)
    assert header.timestamp > parent_header.timestamp
    assert header.number == parent_header.number + 1
    assert len(header.extra_data) <= 32


def validate_genesis_header(genesis_header: Header):
    assert genesis_header.parent_hash == b'\x00' * 32
    assert genesis_header.coinbase == b'\x00' * 20
    assert genesis_header.difficulty == MAINNET_GENESIS_CONFIG.difficulty
    assert genesis_header.number == 0
    assert genesis_header.gas_limit == MAINNET_GENESIS_CONFIG.gas_limit
    assert genesis_header.gas_used == 0
    assert genesis_header.timestamp == MAINNET_GENESIS_CONFIG.timestamp
    assert genesis_header.extra_data == MAINNET_GENESIS_CONFIG.extra_data
    assert genesis_header.mix_digest == b'\x00' * 32
    assert genesis_header.nonce == MAINNET_GENESIS_CONFIG.nonce


def apply_prealloc(state, alloc_data):
    for address, account in alloc_data.items():
        assert len(account.keys()) == 1
        add_ether(state, address, account['balance'])



# GENESIS_BLOCK = Block(
#     header=Header(
#         parent_hash=(b'\x00' * 32),
#         ommers_hash=crypto.keccak256(rlp.encode([])),
#         coinbase=(b'\x00' * 20),
#         state_root='?'
#         transactions_root='?',
#         receipt_root='?',
#         bloom=(b'\x00' * 256),
#         difficulty=GENESIS_DIFFICULTY,
#         number=Uint(0),
#         gas_limit='?',
#         gas_used=Uint(0),
#         timestamp='?',
#         extra_data='?',
#         mix_digest=(b'\x00' * 32),
#         nonce='?',
#     ),
#     transactions=[],
#     ommers=[],
# )


ZERO_ADDRESS = b'\x00' * 20


def apply_body(
    state: State,
    block_hashes: List[Hash32],
    coinbase: Address,
    block_number: Uint,
    block_gas_limit: Uint,
    block_time: U256,
    block_difficulty: Uint,
    transactions: Tuple[Transaction, ...],
    ommers: Tuple[Header, ...],
) -> Tuple[Uint, Root, Root, Bloom, State]:
    """
    Executes a block.

    Parameters
    ----------
    state :
        Current account state.
    block_hashes :
        List of hashes of the previous 256 blocks in the order of
        increasing block number.
    coinbase :
        Address of account which receives block reward and transaction fees.
    block_number :
        Position of the block within the chain.
    block_gas_limit :
        Initial amount of gas available for execution in this block.
    block_time :
        Time the block was produced, measured in seconds since the epoch.
    block_difficulty :
        Difficulty of the block.
    transactions :
        Transactions included in the block.
    ommers :
        Headers of ancestor blocks which are not direct parents (formerly
        uncles.)

    Returns
    -------
    gas_available : `eth1spec.base_types.Uint`
        Remaining gas after all transactions have been executed.
    transactions_root : `eth1spec.eth_types.Root`
        Trie root of all the transactions in the block.
    receipt_root : `eth1spec.eth_types.Root`
        Trie root of all the receipts in the block.
    block_logs_bloom : `Bloom`
        Logs bloom of all the logs included in all the transactions of the
        block.
    state : `eth1spec.eth_types.State`
        State after all transactions have been executed.
    """
    gas_available = block_gas_limit
    receipts = []
    block_logs = ()

    for tx in transactions:
        assert tx.gas <= gas_available
        sender_address = recover_sender(tx)

        env = vm.Environment(
            caller=sender_address,
            origin=sender_address,
            block_hashes=block_hashes,
            coinbase=coinbase,
            number=block_number,
            gas_limit=block_gas_limit,
            gas_price=tx.gas_price,
            time=block_time,
            difficulty=block_difficulty,
            state=state,
        )

        gas_used, logs = process_transaction(env, tx)
        gas_available -= gas_used

        receipts.append(
            Receipt(
                post_state=Root(trie.root(trie.map_keys(state))),
                cumulative_gas_used=(block_gas_limit - gas_available),
                bloom=logs_bloom(logs),
                logs=logs,
            )
        )

    if block_number != 0:
        pay_rewards(state, block_number, coinbase, ommers)

    gas_remaining = block_gas_limit - gas_available

    receipts_map = {
        bytes(rlp.encode(Uint(k))): v for (k, v) in enumerate(receipts)
    }
    receipt_root = trie.root(trie.map_keys(receipts_map, secured=False))

    transactions_map = {
        bytes(rlp.encode(Uint(idx))): tx
        for (idx, tx) in enumerate(transactions)
    }
    transactions_root = trie.root(
        trie.map_keys(transactions_map, secured=False)
    )

    block_logs_bloom = logs_bloom(block_logs)

    return (
        gas_remaining,
        transactions_root,
        receipt_root,
        block_logs_bloom,
        state,
    )


def validate_ommers(ommers, expected_ommers_hash, block_number, chain) -> None:
    assert len(ommers) <= 2
    assert crypto.keccak256(rlp.encode(ommers)) == expected_ommers_hash
    for ommer in ommers:
        # Ommer age with respect to the current block. For example, an age of
        # 1 indicates that the ommer is a sibling of previous block.
        ommer_age = block_number - ommer.number
        assert 1 <= ommer_age <= 6
        # Canonical equivalent block for the ommer block
        equivalent_canonical_block = chain.blocks[len(chain.blocks) - ommer_age]
        # TODO: We get the hash along with the block, need to store it
        # somewhere instead of computing it every time.
        ommer_hash = crypto.keccak256(rlp.encode(ommer))
        assert ommer_hash != crypto.keccak256(
            rlp.encode(equivalent_canonical_block.header)
        )
        assert (
            ommer.parent_hash == equivalent_canonical_block.header.parent_hash
        )


def pay_rewards(state, block_number, coinbase, ommers) -> None:
    miner_reward = BLOCK_REWARD + ((BLOCK_REWARD * len(ommers)) // 32)
    add_ether(state, coinbase, miner_reward)

    for ommer in ommers:
        # Ommer age with respect to the current block.
        ommer_age = block_number - ommer.number
        ommer_miner_reward = BLOCK_REWARD - ((BLOCK_REWARD * ommer_age) // 8)
        add_ether(state, ommer.coinbase, ommer_miner_reward)


def compute_ommers_hash(block: Block) -> Hash32:
    """
    Compute hash of ommers list for a block
    """
    return crypto.keccak256(rlp.encode(block.ommers))


def process_transaction(
    env: vm.Environment, tx: Transaction
) -> Tuple[U256, Tuple[Log, ...]]:
    """
    Execute a transaction against the provided environment.

    Parameters
    ----------
    env :
        Environment for the Ethereum Virtual Machine.
    tx :
        Transaction to execute.

    Returns
    -------
    gas_left : `eth1spec.base_types.U256`
        Remaining gas after execution.
    logs : `Tuple[eth1spec.eth_types.Log, ...]`
        Logs generated during execution.
    """
    assert validate_transaction(tx, env)

    sender = env.origin

    gas = tx.gas - calculate_intrinsic_cost(tx)

    if tx.to is None:
        raise NotImplementedError()  # TODO

    gas_left, logs = process_call(
        sender, tx.to, tx.data, tx.value, gas, Uint(0), env
    )

    gas_used = tx.gas - gas_left
    move_ether(env.state, sender, env.coinbase, gas_used * tx.gas_price)

    def increment_nonce(sender: Account) -> None:
        sender.nonce += 1

    modify_state(env.state, sender, increment_nonce)

    return (gas_used, logs)


def validate_transaction(tx: Transaction, env: vm.Environment) -> bool:
    """
    Verifies a transaction.

    Parameters
    ----------
    tx :
        Transaction to validate.
    env :
        Environment for the Ethereum Virtual Machine.

    Returns
    -------
    verified : `bool`
        True if the transaction can be executed, or False otherwise.
    """
    sender = env.origin

    return (
        # TODO: What if the sender is not yet present in the state
        env.state[sender].nonce == tx.nonce
        and calculate_intrinsic_cost(tx) <= tx.gas
        and env.state[sender].balance >= tx.gas * tx.gas_price
    )


def calculate_intrinsic_cost(tx: Transaction) -> Uint:
    """
    Calculates the intrinsic cost of the transaction that is charged before
    execution is instantiated.

    Parameters
    ----------
    tx :
        Transaction to compute the intrinsic cost of.

    Returns
    -------
    verified : `eth1spec.base_types.Uint`
        The intrinsic cost of the transaction.
    """
    data_cost = 0

    for byte in tx.data:
        if byte == 0:
            data_cost += TX_DATA_COST_PER_ZERO
        else:
            data_cost += TX_DATA_COST_PER_NON_ZERO

    return Uint(TX_BASE_COST + data_cost)


def recover_sender(tx: Transaction) -> Address:
    """
    Extracts the sender address from a transaction.

    Parameters
    ----------
    tx :
        Transaction of interest.

    Returns
    -------
    sender : `eth1spec.eth_types.Address`
        The address of the account that signed the transaction.
    """
    v, r, s = tx.v, tx.r, tx.s

    #  if v > 28:
    #      v = v - (chain_id*2+8)

    secp256k1n = (
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
    )

    assert v == 27 or v == 28
    assert 0 < r < secp256k1n
    assert 0 < s < secp256k1n

    # TODO: this causes error starting in block 46169 (or 46170?)
    # assert 0 < s_int and s_int < (secp256k1n//2+1)

    public_key = crypto.secp256k1_recover(r, s, v - 27, signing_hash(tx))
    return Address(crypto.keccak256(public_key)[12:32])


def signing_hash(tx: Transaction) -> Hash32:
    """
    Compute the hash of a transaction used in the signature.

    Parameters
    ----------
    tx :
        Transaction of interest.

    Returns
    -------
    hash : `eth1spec.eth_types.Hash32`
        Hash of the transaction.
    """
    return crypto.keccak256(
        rlp.encode(
            (
                tx.nonce,
                tx.gas_price,
                tx.gas,
                tx.to,
                tx.value,
                tx.data,
            )
        )
    )


def compute_header_hash(header: Header) -> Hash32:
    """
    Computes the hash of a block header.

    Parameters
    ----------
    header :
        Header of interest.

    Returns
    -------
    hash : `ethereum.eth_types.Hash32`
        Hash of the header.
    """
    return crypto.keccak256(rlp.encode(header))


def get_block_header_by_hash(hash: Hash32, chain: BlockChain) -> Header:
    """
    Fetches the block header with the corresponding hash.

    Parameters
    ----------
    hash :
        Hash of the header of interest.

    chain :
        History and current state.

    Returns
    -------
    Header : `ethereum.eth_types.Header`
        Block header found by its hash.
    """
    for block in chain.blocks:
        if compute_header_hash(block.header) == hash:
            return block.header
    else:
        raise ValueError(f"Could not find header with hash={hash.hex()}")


def check_proof_of_work(header: Header) -> bool:
    """
    Validates the Proof of Work constraints.

    Parameters
    ----------
    header :
        Header of interest.

    Returns
    -------
    check : `bool`
        True if Proof of Work constraints are satisfied, False otherwise.
    """
    # TODO: Implement this method once proof of work
    #  algorithm is implemented
    #  https://github.com/ethereum/eth1.0-specs/issues/238
    raise NotImplementedError


def check_gas_limit(gas_limit: Uint, parent_gas_limit: Uint) -> bool:
    """
    Validates the gas limit for a block.

    Parameters
    ----------
    gas_limit :
        Gas limit to validate.

    parent_gas_limit :
        Gas limit of the parent block.

    Returns
    -------
    check : `bool`
        True if gas limit constraints are satisfied, False otherwise.
    """
    max_adjustment_delta = parent_gas_limit // GAS_LIMIT_ADJUSTMENT_FACTOR
    if gas_limit >= parent_gas_limit + max_adjustment_delta:
        return False
    if gas_limit <= parent_gas_limit - max_adjustment_delta:
        return False
    if gas_limit < GAS_LIMIT_MINIMUM:
        return False

    return True


def calculate_block_difficulty(
    number: Uint,
    timestamp: U256,
    parent_timestamp: U256,
    parent_difficulty: Uint,
) -> Uint:
    """
    Computes difficulty of a block using its header and parent header.
    Parameters
    ----------
    number :
        Block number of the block
    timestamp :
        Timestmap of the block
    parent_timestamp :
        Timestanp of the parent block
    parent_difficulty :
        difficulty of the parent block
    Returns
    ------
    difficulty : `ethereum.base_types.Uint`
        Computed difficulty for a block.
    """
    max_adjustment_delta = parent_difficulty // Uint(2048)
    if number == 0:
        return GENESIS_DIFFICULTY
    elif timestamp < parent_timestamp + 13:
        return parent_difficulty + max_adjustment_delta
    else:  # timestamp >= parent_timestamp + 13
        return max(
            GENESIS_DIFFICULTY,
            parent_difficulty - max_adjustment_delta,
        )


def print_state(state: State) -> None:
    """
    Pretty prints the state.

    Parameters
    ----------
    state :
        Ethereum state.
    """
    nice = {}
    for (address, account) in state.items():
        nice[address.hex()] = {
            "nonce": account.nonce,
            "balance": account.balance,
            "code": account.code.hex(),
            "storage": {},
        }

        for (k, v) in account.storage.items():
            nice[address.hex()]["storage"][k.hex()] = hex(v)  # type: ignore

    print(nice)
