from dataclasses import dataclass
from io import BufferedReader, BufferedWriter
from typing import Self

from . import ApduItemType


@dataclass
class ApduItem:
    """APDU Item"""

    type: ApduItemType
    data: bytes

    @classmethod
    def read(cls, stream: BufferedReader) -> Self:
        """Read APDU Item from stream"""
        buffer = stream.read(4)
        if len(buffer) < 4:
            raise ValueError("Invalid item header")

        item_type = ApduItemType(int.from_bytes(buffer[0:2], "big"))
        item_len = int.from_bytes(buffer[2:4], "big")

        data = stream.read(item_len)
        if len(data) < item_len:
            raise ValueError("Invalid item data length")

        return cls(item_type, data)

    def write(self, stream: BufferedWriter) -> None:
        """Write APDU Item to stream"""
        stream.write(self.type.value.to_bytes(2, "big"))
        stream.write(len(self.data).to_bytes(2, "big"))
        stream.write(self.data)
