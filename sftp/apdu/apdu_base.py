from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BufferedReader, BufferedWriter, BytesIO
import os

from . import ApduType


@dataclass
class ApduBase(ABC):
    """APDU Base Class"""

    @staticmethod
    def _read_common(stream: BufferedReader) -> tuple[ApduType, bytes]:
        """Read Common Part

        Args:
            stream (BufferedReader): Input stream

        Returns:
            tuple[ApduType, bytes]: ApduType and Payload
        """
        buffer = stream.read(4)
        if len(buffer) < 4:
            stream.seek(-len(buffer), os.SEEK_CUR)
            raise ValueError("Reached to End of File.")
        apdu_type = ApduType(int.from_bytes(buffer[0:2], "big"))
        size = int.from_bytes(buffer[2:4], "big")
        payload = stream.read(size)
        return apdu_type, payload

    @abstractmethod
    def _apdu_type(self) -> ApduType:
        """APDU Type

        Returns:
            ApduType: APDU Type
        """
        pass

    @abstractmethod
    def _payload_buffer(self) -> bytes:
        """Payload Buffer

        Returns:
            bytes: Payload Buffer
        """
        pass

    def write(self, stream: BufferedWriter) -> None:
        """Write

        Args:
            stream (BufferedWriter): Output stream
        """
        payload_buffer = self._payload_buffer()

        stream.write(self._apdu_type().value.to_bytes(2, "big"))
        stream.write(len(payload_buffer).to_bytes(2, "big"))
        stream.write(payload_buffer)

    def to_bytes(self) -> bytes:
        """To bytes

        Returns:
            bytes: This instance as bytes
        """
        stream = BytesIO()
        self.write(stream)
        stream.seek(0)
        return stream.read()
