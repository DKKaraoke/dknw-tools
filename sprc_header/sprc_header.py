from dataclasses import dataclass
from io import BufferedReader, BufferedWriter
from typing import Self

from fastcrc import crc16


@dataclass
class SprcHeader:
    """SPRC Header"""

    __MAGIC_BYTES = b"SPRC"

    revision: int
    crc_value: int
    force_flag: int
    unknown_0: bytes

    @staticmethod
    def has_sprc_header(stream: BufferedReader) -> bool:
        """Check SPRC header existance in a stream.

        Args:
            stream (BufferedReader): Source

        Returns:
            bool: True if source has SPRC header, else False
        """
        position = stream.tell()
        buffer = stream.read(16)
        stream.seek(position)
        if len(buffer) < 16:
            return False
        magic_bytes = buffer[0:4]
        if magic_bytes != SprcHeader.__MAGIC_BYTES:
            return False
        return True

    @classmethod
    def read(cls, stream: BufferedReader) -> Self:
        """Read from a stream.

        Args:
            stream (BufferedReader): Source

        Returns:
            Self: Instance of this class
        """
        buffer = stream.read(16)
        if len(buffer) < 16:
            raise ValueError(f"Too less read bytes.")

        magic_bytes = buffer[0:4]
        if magic_bytes != SprcHeader.__MAGIC_BYTES:
            raise ValueError(f"Invalid magic_bytes. magic_bytes={magic_bytes}")
        revision = int.from_bytes(buffer[4:6], "big")
        crc_value = int.from_bytes(buffer[6:8], "big")
        force_flag = buffer[8]
        unknown_0 = buffer[9:16]

        return cls(revision, crc_value, force_flag, unknown_0)

    def validate_crc(self, data: bytes | BufferedReader) -> bool:
        """Validate data with CRC value.

        Args:
            stream (bytes | BufferedReader): Data bytes or stream

        Returns:
            bool: True if data is valid, else False
        """
        if isinstance(data, BufferedReader):
            # Skip SPRC header
            data.seek(16)
            buffer = data.read()
            data.seek(16)
            data = buffer

        return crc16.genibus(data) == self.crc_value

    def write(self, stream: BufferedWriter) -> None:
        """Write to a stream.

        Args:
            stream (BufferedWriter): Destination
        """
        stream.write(SprcHeader.__MAGIC_BYTES)
        stream.write(self.revision.to_bytes(2, "big"))
        stream.write(self.crc_value.to_bytes(2, "big"))
        stream.write(self.force_flag.to_bytes())
        stream.write(self.unknown_0)
