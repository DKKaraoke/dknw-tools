from dataclasses import dataclass
from io import BufferedReader, BufferedWriter, BytesIO
import os
from typing import Self
import zlib

from .apdu import ApduType, ApduBase, GenericApdu, FDataApdu
from .network_type import NetworkType

@dataclass
class Nsdu:
    """NSDU (Network Service Data Unit) Class"""

    apdu: ApduBase
    network: NetworkType = NetworkType.BB

    @classmethod
    def read(cls, stream: BufferedReader) -> Self:
        """Read NSDU from stream

        Args:
            stream (BufferedReader): Input stream

        Returns:
            Self: NSDU instance

        Raises:
            ValueError: If invalid format or checksum error
        """
        # Check STX
        stx = stream.read(1)
        if not stx or stx[0] != 0x02:
            raise ValueError("Invalid STX")

        # Read APDU length
        length_bytes = stream.read(2)
        if len(length_bytes) < 2:
            raise ValueError("Failed to read length")
        apdu_len = int.from_bytes(length_bytes, "big")

        # Read APDU data
        apdu_data = stream.read(apdu_len)
        if len(apdu_data) < apdu_len:
            raise ValueError("Failed to read APDU data")

        # Determine network type and verify CRC
        try:
            crc_bytes = stream.read(2)
            if len(crc_bytes) == 2:
                # Verify CRC
                expected_crc = int.from_bytes(crc_bytes, "big")
                actual_crc = zlib.crc32(length_bytes + apdu_data) & 0xFFFF
                if expected_crc != actual_crc:
                    raise ValueError("CRC mismatch")
                network = NetworkType.NB
            else:
                network = NetworkType.BB
                stream.seek(-len(crc_bytes), os.SEEK_CUR)
        except:
            network = NetworkType.BB
            stream.seek(-2, os.SEEK_CUR)

        # Check ETX
        etx = stream.read(1)
        if not etx or etx[0] != 0x03:
            raise ValueError("Invalid ETX")

        # Restore APDU
        apdu_stream = BytesIO(apdu_data)
        try:
            if apdu_data[0:2] == ApduType.F_DATA.value.to_bytes(2, "big"):
                apdu = FDataApdu.read(apdu_stream)
            else:
                apdu = GenericApdu.read(apdu_stream)
        except ValueError as e:
            raise ValueError(f"Failed to read APDU: {e}")

        return cls(apdu, network)

    def write(self, stream: BufferedWriter) -> None:
        """Write NSDU to stream

        Args:
            stream (BufferedWriter): Output stream

        Raises:
            ValueError: If APDU is too large
        """
        # Get APDU data first
        apdu_data = self.apdu.to_bytes()
        apdu_len = len(apdu_data)

        # Write STX
        stream.write(b"\x02")

        # Write APDU length
        stream.write(apdu_len.to_bytes(2, "big"))

        # Write APDU data
        stream.write(apdu_data)

        # Write CRC for NB network
        if self.network == NetworkType.NB:
            # Calculate CRC-16 (Length + Data)
            crc = zlib.crc32(apdu_len.to_bytes(2, "big") + apdu_data) & 0xFFFF
            stream.write(crc.to_bytes(2, "big"))

        # Write ETX
        stream.write(b"\x03")

    def to_bytes(self) -> bytes:
        """Convert NSDU to bytes

        Returns:
            bytes: NSDU as bytes
        """
        stream = BytesIO()
        self.write(stream)
        stream.seek(0)
        return stream.read()
