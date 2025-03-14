from dataclasses import dataclass
from io import BufferedReader
from typing import Self

from bitstring import BitStream, pack

from . import MessageType, MessageBase


@dataclass
class GetTerminalTypeResponse(MessageBase):
    protocol_version: int
    model_id: str
    model_sub_id: str
    serial: str
    software_version: str
    bb_index: int
    printer_version: str

    @classmethod
    def read(cls, stream: BufferedReader) -> Self:
        """Read

        Args:
            stream (BufferedReader): Input stream

        Returns:
            Self: GetTerminalTypeResponse
        """

        message_type, payload = MessageBase._read_common(stream)

        if message_type != MessageType.GET_TERMINAL_TYPE_RESPONSE:
            raise ValueError("Message type mismatch.")

        stream = BitStream(payload)
        protocol_version = stream.read("uintbe:32")
        model_id = stream.read("bytes:2").decode("ascii")
        model_sub_id = stream.read("bytes:2").decode("ascii")
        serial = stream.read("bytes:8").decode("ascii")
        software_version = stream.read("bytes:8").decode("ascii")
        bb_index = stream.read("uintbe:16")
        # Reserved
        stream.read("bytes:2")
        printer_version = stream.read("bytes:4").decode("ascii")
        # Reserved
        stream.read("bytes:4")

        return cls(
            protocol_version,
            model_id,
            model_sub_id,
            serial,
            software_version,
            bb_index,
            printer_version,
        )

    def _message_type(self) -> MessageType:
        return MessageType.GET_TERMINAL_TYPE_RESPONSE

    def _payload_buffer(self) -> bytes:
        """Payload Buffer

        Returns:
            bytes: Payload Buffer
        """

        return pack(
            "uintbe:32, bytes:2, bytes:2, bytes:8, bytes:8, uintbe:16, pad:16, bytes:4, uintbe:32",
            self.protocol_version,
            self.model_id.encode("ascii"),
            self.model_sub_id.encode("ascii"),
            self.serial.encode("ascii"),
            self.software_version.encode("ascii"),
            self.bb_index,
            self.printer_version.encode("ascii"),
        ).tobytes()
