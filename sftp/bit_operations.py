from collections.abc import Iterable
from typing import Final

__BIT_COUNT_TABLE = [bin(i).count("1") for i in range(256)]

__NIBBLE_HIGH: Final[int] = 0xF0
__NIBBLE_LOW: Final[int] = 0x0F
__PAIR_HIGH: Final[int] = 0xCC
__PAIR_LOW: Final[int] = 0x33
__ODD_BITS: Final[int] = 0xAA
__EVEN_BITS: Final[int] = 0x55


def get_bit(data: bytes | bytearray | Iterable[int], pos: int) -> int:
    data = bytearray(data)

    if pos < 0:
        pos = pos + 7

    byte_index = pos >> 3
    bit_pos = pos & 7
    return (data[byte_index] << bit_pos) & 0x80


def count_set_bits(data: bytes | bytearray | Iterable[int]) -> int:
    data = bytearray(data)

    return sum(__BIT_COUNT_TABLE[byte] for byte in data)


def reverse_bits(buffer: bytes | bytearray | Iterable[int]) -> bytearray:
    """Reverse the bits in each byte of the input buffer.

    This function reverses the bits in each byte using an optimized algorithm
    that performs the reversal in three steps using masks and shifts.

    Args:
        buffer: Input bytes, bytearray, or iterable of integers

    Returns:
        A new bytes object with all bits reversed

    Example:
        >>> reverse_bits(b'\\x0F')  # 0000 1111 -> 1111 0000
        b'\\xF0'
        >>> reverse_bits(b'\\xAA')  # 1010 1010 -> 0101 0101
        b'\\x55'

    Note:
        The algorithm uses the following steps for each byte:
        1. Swap nibbles (4 bits)
        2. Swap pairs of bits
        3. Swap adjacent bits
    """
    # Pre-allocate bytearray for better performance
    result = bytearray(len(buffer))

    for i, value in enumerate(buffer):
        # Step 1: Swap nibbles (4 bits)
        value = ((value & __NIBBLE_HIGH) >> 4) | ((value & __NIBBLE_LOW) << 4)

        # Step 2: Swap pairs of bits
        value = ((value & __PAIR_HIGH) >> 2) | ((value & __PAIR_LOW) << 2)

        # Step 3: Swap adjacent bits
        value = ((value & __ODD_BITS) >> 1) | ((value & __EVEN_BITS) << 1)

        result[i] = value

    return result


def rotate_bits(data: bytearray, count: int):
    n_bits = len(data) * 8
    result = bytearray(len(data))
    for i in range(len(result)):
        mask = 0x80
        for _ in range(8):
            bit = get_bit(data, count)
            if bit != 0:
                result[i] |= mask
            mask >>= 1
            count = (count + 1) % n_bits

    return result
