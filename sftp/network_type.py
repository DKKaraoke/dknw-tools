from enum import IntEnum


class NetworkType(IntEnum):
    """Network Type"""

    BB = 0x00
    NB = 0x01  # Add CRC for NB network type
