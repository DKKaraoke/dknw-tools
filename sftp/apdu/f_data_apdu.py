from dataclasses import dataclass
from io import BufferedReader
from typing import Self

from . import ApduType, ApduBase


@dataclass
class FDataApdu(ApduBase):
    """F_Data APDU"""

    data: bytes

    @classmethod
    def read(cls, stream: BufferedReader) -> Self:
        """Read

        Args:
            stream (BufferedReader): Input stream

        Returns:
            Self: F_Data APDU
        """
        apdu_type, payload = ApduBase._read_common(stream)
        if apdu_type != ApduType.F_DATA:
            raise ValueError(f"Invalid APDU Type: {apdu_type}")
        return cls(payload)

    def _apdu_type(self) -> ApduType:
        return ApduType.F_DATA

    def _payload_buffer(self) -> bytes:
        return self.data
