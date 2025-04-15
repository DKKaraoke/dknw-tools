from dataclasses import dataclass
from enum import IntEnum
import logging
from typing import ClassVar, Final

# Configure module logger
logger = logging.getLogger(__name__)


class DS2FTPCommandType(IntEnum):
    """DS2FTP Command Types enumeration."""

    NONE = -1
    DS2INFO = 0
    RTS = 1
    CTS = 2
    ERRORCTS = 0x80000002
    INVALID = -2


class FileMode(IntEnum):
    """File operation modes."""

    NONE = 0
    GET = 1
    PUT = 2


class ErrorCode(IntEnum):
    """Error codes for DS2FTP operations."""

    ERROR_FOPEN = 1
    ERROR_NETWORK = 2
    ERROR_TIMEOUT = 3
    ERROR_CHECKSUM = 4
    ERROR_UNKNOWN = 99


@dataclass(frozen=True)
class DS2FTPDS2INFO:
    """DS2FTP DS2INFO data structure."""

    ds2addr: int = 0  # 4 bytes
    ds2macaddr: bytes = b"\x00" * 6  # 6 bytes
    ds2serial: bytes = b"\x00" * 8  # 8 bytes
    throughput: int = 0  # 4 bytes
    tokenGroupNo: int = 0  # 4 bytes
    apEssid: bytes = b"\x00" * 32  # 32 bytes
    wlanType: int = 0  # 4 bytes


@dataclass(frozen=True)
class DS2FTPRTS:
    """DS2FTP RTS (Request To Send) data structure."""

    dirno: int = 0  # 4 bytes
    fileno: int = 0  # 4 bytes
    filesize: int = 0  # 4 bytes
    serial: int = 0  # 4 bytes


@dataclass
class DS2FTPCTS:
    """DS2FTP CTS (Clear To Send) data structure."""

    tsize: int = 0  # 4 bytes - total size
    fsize: int = 0  # 4 bytes - file size
    bsize: int = 0  # 4 bytes - block size


@dataclass
class DS2FTPERRCTS:
    """DS2FTP ERRORCTS data structure."""

    tsize: int = 0  # 4 bytes - total size
    fsize: int = 0  # 4 bytes - file size
    bsize: int = 0  # 4 bytes - block size
    error_msg: str = ""  # variable length


class DS2FTPProtocolError(Exception):
    """Exception raised for DS2FTP protocol errors."""

    pass


class DS2FTPChecksumError(DS2FTPProtocolError):
    """Exception raised for checksum validation failures."""

    pass


class DS2FTPCommand:
    """DS2FTP Command Class for parsing and creating protocol commands."""

    # Protocol Constants
    DS2_HEADER: Final[bytes] = b"DS2\x00"  # 4 bytes header
    DS2FTP_CMD: ClassVar[list[int]] = [0, 1, 2, 3, 0x80000002]  # Command IDs
    DS2FTP_CMD_LENGTH: ClassVar[list[int]] = [
        0,
        0x4C,
        0x1C,
        0x18,
        0x18,
    ]  # Command lengths

    def __init__(self) -> None:
        """Initialize DS2FTP command."""
        self.cmdid: DS2FTPCommandType = DS2FTPCommandType.NONE
        self.length: int = 0
        self.data: bytearray = bytearray()

        # Command-specific data structures
        self.ds2ftp_ds2info: DS2FTPDS2INFO | None = None
        self.ds2ftp_rts: DS2FTPRTS | None = None
        self.ds2ftp_cts: DS2FTPCTS | None = None
        self.ds2ftp_errcts: DS2FTPERRCTS | None = None

    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        """
        Calculate checksum for byte data.

        Args:
            data: Byte data to calculate checksum for

        Returns:
            32-bit checksum value
        """
        # Get data length
        length = len(data)

        # Initialize sum
        sum_value = 0

        # Process 4 bytes at a time
        for i in range(0, length // 4):
            value = int.from_bytes(data[i * 4 : i * 4 + 4], byteorder="big")
            sum_value = (sum_value + value) & 0xFFFFFFFF  # Limit to 32 bits

        # Process remaining bytes
        remaining_bytes = length % 4
        if remaining_bytes:
            # Add padding for remaining bytes
            remaining_data = data[length - remaining_bytes :] + bytes(
                [0] * (4 - remaining_bytes)
            )
            value = int.from_bytes(remaining_data, byteorder="big")
            sum_value = (sum_value + value) & 0xFFFFFFFF

        # Checksum is bit-wise NOT of the sum
        return ~sum_value & 0xFFFFFFFF

    def parse_rx_buffer(self, buffer: bytes, length: int) -> DS2FTPCommandType:
        """
        Parse received buffer into command structure.

        Args:
            buffer: Received data buffer
            length: Length of data in buffer

        Returns:
            Parsed command type
        """
        if self.cmdid != DS2FTPCommandType.NONE:
            logger.error("Command already set")
            return DS2FTPCommandType.NONE

        # Clear and set data
        self.data = bytearray(buffer[:length])
        self.length = length

        # Parse header
        if length < 8:  # Minimum size: DS2 header(4 bytes) + command(4 bytes)
            logger.error("Buffer too small")
            return DS2FTPCommandType.NONE

        # Extract opcode (big endian)
        opcode = int.from_bytes(buffer[4:8], "big")
        self.cmdid = DS2FTPCommandType.NONE

        # Find command
        for i, cmd_id in enumerate(self.DS2FTP_CMD):
            if cmd_id == opcode:
                try:
                    self.cmdid = DS2FTPCommandType(cmd_id)
                    break
                except ValueError:
                    # Handle special value (0x80000002)
                    if cmd_id == 0x80000002:
                        self.cmdid = DS2FTPCommandType.ERRORCTS
                        break

        if self.cmdid == DS2FTPCommandType.NONE:
            logger.error("Invalid command ERROR")
            return DS2FTPCommandType.NONE

        # Validate length and checksum
        if self.confirm_length() and (
            self.cmdid == DS2FTPCommandType.ERRORCTS or self.confirm_checksum()
        ):
            # Parse command-specific data
            if self.cmdid == DS2FTPCommandType.DS2INFO:
                logger.debug("Receive DS2INFO")
                self.parse_ds2info(buffer)
            elif self.cmdid == DS2FTPCommandType.RTS:
                logger.debug("Receive RTS")
                self.parse_rts(buffer)
            elif self.cmdid == DS2FTPCommandType.CTS:
                logger.debug("Receive CTS")
                self.parse_cts(buffer)
            elif self.cmdid == DS2FTPCommandType.ERRORCTS:
                self.parse_errorcts(buffer)
            else:
                logger.error("Undefined command ERROR")
        else:
            logger.error("Command confirm ERROR")
            self.cmdid = DS2FTPCommandType.NONE

        return self.cmdid

    def confirm_length(self) -> bool:
        """Confirm if command length is valid."""
        cmd_index = 0

        if self.cmdid == DS2FTPCommandType.DS2INFO:
            cmd_index = 1
        elif self.cmdid == DS2FTPCommandType.RTS:
            cmd_index = 2
        elif self.cmdid == DS2FTPCommandType.CTS:
            cmd_index = 3
        elif self.cmdid == DS2FTPCommandType.ERRORCTS:
            cmd_index = 4
            return True  # ERRORCTS has variable length
        else:
            logger.error("Cannot confirm length: Undefined command")
            return False

        expected_length = self.DS2FTP_CMD_LENGTH[cmd_index]

        if self.length != expected_length:
            logger.error(f"ConfirmLength Error: {self.cmdid}")
            return False
        return True

    def confirm_checksum(self) -> bool:
        """Confirm if checksum is valid."""
        if self.length < 4:
            return False

        # Data without checksum
        data_without_checksum = bytes(self.data[:-4])

        # Calculate checksum
        calculated_checksum = self._calculate_checksum(data_without_checksum)

        # Get checksum from last 4 bytes
        received_checksum = int.from_bytes(self.data[-4:], byteorder="big")

        if calculated_checksum != received_checksum:
            logger.error(
                f"Checksum Error: calculated=0x{calculated_checksum:08x}, received=0x{received_checksum:08x}"
            )
            return False

        return True

    def parse_ds2info(self, buffer: bytes) -> bool:
        """Parse DS2INFO command data."""
        cmd_index = 1  # DS2INFO
        if len(buffer) < self.DS2FTP_CMD_LENGTH[cmd_index]:
            return False

        self.ds2ftp_ds2info = DS2FTPDS2INFO(
            ds2addr=int.from_bytes(buffer[8:12], "big"),
            ds2macaddr=buffer[12:18],
            ds2serial=buffer[20:28],
            throughput=int.from_bytes(buffer[28:32], "big"),
            tokenGroupNo=int.from_bytes(buffer[32:36], "big"),
            apEssid=buffer[36:68],
            wlanType=int.from_bytes(buffer[68:72], "big"),
        )

        return True

    def parse_rts(self, buffer: bytes) -> bool:
        """Parse RTS command data."""
        cmd_index = 2  # RTS
        if len(buffer) < self.DS2FTP_CMD_LENGTH[cmd_index]:
            return False

        self.ds2ftp_rts = DS2FTPRTS(
            dirno=int.from_bytes(buffer[8:12], "big"),
            fileno=int.from_bytes(buffer[12:16], "big"),
            filesize=int.from_bytes(buffer[16:20], "big"),
            serial=int.from_bytes(buffer[20:24], "big"),
        )

        return True

    def parse_cts(self, buffer: bytes) -> bool:
        """Parse CTS command data."""
        cmd_index = 3  # CTS
        if len(buffer) < self.DS2FTP_CMD_LENGTH[cmd_index]:
            return False

        self.ds2ftp_cts = DS2FTPCTS(
            tsize=int.from_bytes(buffer[8:12], "big"),
            fsize=int.from_bytes(buffer[12:16], "big"),
            bsize=int.from_bytes(buffer[16:20], "big"),
        )

        return True

    def parse_errorcts(self, buffer: bytes) -> bool:
        """Parse ERRORCTS command data."""
        cmd_index = 4  # ERRORCTS
        if len(buffer) < self.DS2FTP_CMD_LENGTH[cmd_index]:
            return False

        self.ds2ftp_errcts = DS2FTPERRCTS(
            tsize=int.from_bytes(buffer[8:12], "big"),
            fsize=int.from_bytes(buffer[12:16], "big"),
            bsize=int.from_bytes(buffer[16:20], "big"),
        )

        # Parse error message (variable length)
        if len(buffer) > 24:
            # Read until null byte or newline
            error_bytes = buffer[24:]
            try:
                end_index = error_bytes.index(b"\n")
                self.ds2ftp_errcts.error_msg = error_bytes[:end_index].decode("utf-8")
            except ValueError:
                # If no newline found, read all
                self.ds2ftp_errcts.error_msg = error_bytes.decode(
                    "utf-8", errors="ignore"
                )

        return True

    def make_ds2info(self) -> bytes:
        """Create DS2INFO command."""
        raise NotImplementedError("DS2INFO creation not implemented")

    def make_rts(
        self, dirno: int, fileno: int, filesize: int = 0, serial: int = 0
    ) -> bytes:
        """Create RTS command."""
        # RTS command index and length
        cmd_index = 2  # RTS
        length = self.DS2FTP_CMD_LENGTH[cmd_index]

        # Prepare buffer
        buffer = bytearray(length)

        # DS2 header
        buffer[0:4] = self.DS2_HEADER

        # Command type
        buffer[4:8] = DS2FTPCommandType.RTS.value.to_bytes(4, "big")

        # Data fields
        buffer[8:12] = dirno.to_bytes(4, "big")
        buffer[12:16] = fileno.to_bytes(4, "big")
        buffer[16:20] = filesize.to_bytes(4, "big")
        buffer[20:24] = serial.to_bytes(4, "big")

        # Calculate checksum
        checksum = self._calculate_checksum(buffer[:-4])

        # Set checksum
        buffer[-4:] = checksum.to_bytes(4, "big")

        return bytes(buffer)

    def make_cts(self, tsize: int, fsize: int, bsize: int) -> bytes:
        """Create CTS command."""
        # CTS command index and length
        cmd_index = 3  # CTS
        length = self.DS2FTP_CMD_LENGTH[cmd_index]

        # Prepare buffer
        buffer = bytearray(length)

        # DS2 header
        buffer[0:4] = self.DS2_HEADER

        # Command type
        buffer[4:8] = DS2FTPCommandType.CTS.value.to_bytes(4, "big")

        # Data fields
        buffer[8:12] = tsize.to_bytes(4, "big")
        buffer[12:16] = fsize.to_bytes(4, "big")
        buffer[16:20] = bsize.to_bytes(4, "big")

        # Calculate checksum
        checksum = self._calculate_checksum(buffer[:-4])

        # Set checksum
        buffer[-4:] = checksum.to_bytes(4, "big")

        return bytes(buffer)

    def make_errorcts(
        self, tsize: int, fsize: int, bsize: int, error_msg: str = ""
    ) -> bytes:
        """Create ERRORCTS command."""
        # ERRORCTS command index and length
        cmd_index = 4  # ERRORCTS
        min_length = self.DS2FTP_CMD_LENGTH[cmd_index]

        # Adjust length for error message
        msg_bytes = error_msg.encode("utf-8") + b"\n" if error_msg else b""
        length = min_length + len(msg_bytes)

        # Align length to 4-byte boundary
        if length % 4 != 0:
            padding = 4 - (length % 4)
            length += padding

        # Prepare buffer
        buffer = bytearray(length)

        # DS2 header
        buffer[0:4] = self.DS2_HEADER

        # Command type
        buffer[4:8] = DS2FTPCommandType.ERRORCTS.value.to_bytes(4, "big")

        # Data fields
        buffer[8:12] = tsize.to_bytes(4, "big")
        buffer[12:16] = fsize.to_bytes(4, "big")
        buffer[16:20] = bsize.to_bytes(4, "big")

        # Add error message if present
        if msg_bytes:
            buffer[24 : 24 + len(msg_bytes)] = msg_bytes

        # Calculate checksum
        checksum = self._calculate_checksum(buffer[:-4])

        # Set checksum
        buffer[-4:] = checksum.to_bytes(4, "big")

        return bytes(buffer)

    def get_rts(self) -> DS2FTPRTS | None:
        """Get RTS data."""
        return self.ds2ftp_rts

    def get_cts(self) -> DS2FTPCTS | None:
        """Get CTS data."""
        return self.ds2ftp_cts

    def get_ds2info(self) -> DS2FTPDS2INFO | None:
        """Get DS2INFO data."""
        return self.ds2ftp_ds2info

    def get_errorcts(self) -> DS2FTPERRCTS | None:
        """Get ERRORCTS data."""
        return self.ds2ftp_errcts
