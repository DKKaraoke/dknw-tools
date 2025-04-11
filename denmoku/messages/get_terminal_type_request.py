from dataclasses import dataclass
from io import BufferedReader
from typing import Self

from bitstring import BitStream, pack

from . import MessageBase, MessageType

@dataclass
class GetTerminalTypeRequest(MessageBase):
    denmoku_serial: str

    @classmethod
    def read(cls, stream: BufferedReader) -> Self:
        """Read

        Args:
            stream (BufferedReader): Input stream

        Returns:
            Self: GetTerminalTypeResponse
        """

        message_type, payload = MessageBase._read_common(stream)

        if message_type != MessageType.GET_TERMINAL_TYPE_REQUEST:
            raise ValueError("Message type mismatch.")

        stream = BitStream(payload)
        denmoku_serial = stream.read("bytes:8").decode("ascii")

        return cls(denmoku_serial)

    def _message_type(self) -> MessageType:
        return MessageType.GET_TERMINAL_TYPE_REQUEST

    def _payload_buffer(self) -> bytes:
        return pack(
            "bytes:8",
            self.denmoku_serial.encode("ascii"),
        ).tobytes()
