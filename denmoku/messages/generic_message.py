from dataclasses import dataclass
from io import BufferedReader
from typing import Self

from . import MessageType, MessageBase


@dataclass
class GenericMessage(MessageBase):
    """Generic Message"""

    payload: bytes

    @classmethod
    def read(cls, stream: BufferedReader) -> Self:
        """Read

        Args:
            stream (BufferedReader): Input stream

        Returns:
            Self: Generic Message
        """

        message_type, payload = MessageBase._read_common(stream)
        return cls(message_type, payload)

    def _message_type(self) -> MessageType:
        return MessageType.UNDEFINED

    def _payload_buffer(self) -> bytes:
        return self.payload
