from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BufferedReader, BufferedWriter, BytesIO
import os

from . import MessageType


@dataclass
class MessageBase(ABC):
    """Chunk Base Class"""

    @staticmethod
    def _read_common(stream: BufferedReader) -> tuple[MessageType, bytes]:
        """Read Common Part

        Args:
            stream (BufferedReader): Input stream

        Returns:
            tuple[MessageType, bytes]: MessageType and Payload
        """

        buffer = stream.read(4)
        if len(buffer) < 4:
            stream.seek(-len(buffer), os.SEEK_CUR)
            raise ValueError("Reached to End of File.")
        message_type = MessageType(int.from_bytes(buffer[0:2], "big"))
        size = int.from_bytes(buffer[2:4], "big")
        payload = stream.read(size)
        return message_type, payload

    @abstractmethod
    def _message_type(self) -> MessageType:
        """Message Type

        Returns:
            MessageType: Message Type
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
            stream (BufferedReader): Output stream
        """

        payload_buffer = self._payload_buffer()

        stream.write(self._message_type().value.to_bytes(2, "big"))
        stream.write(len(payload_buffer).to_bytes(2, "big"))
        stream.write(payload_buffer)

    def to_bytes(self) -> bytes:
        """To bytes

        Returns:
            bytes: This instance as a bytes
        """

        stream = BytesIO()
        self.write(stream)
        stream.seek(0)
        return stream.read()
