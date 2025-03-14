import asyncio
import logging
from dataclasses import dataclass
from io import BytesIO
from os import path
from typing import Self

from .file_operation_type import FileOperationType
from .unicrypt import Unicrypt

from .apdu import ApduType, ApduBase, ApduItemType, ApduItem, GenericApdu, FDataApdu
from .network_type import NetworkType
from .nsdu import Nsdu


logger = logging.getLogger(__name__)


@dataclass
class SftpConfig:
    """SFTP client configuration"""

    host: str
    port: int
    timeout: float = 5.0
    network: NetworkType = NetworkType.BB


class SftpClient:
    """Async SFTP client implementation"""

    __DATA_CHUNK_SIZE = 0xFF8

    def __init__(self, config: SftpConfig) -> None:
        self._config = config
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        logger.debug("Initializing SFTP client: %s:%d", config.host, config.port)

    async def connect(self) -> None:
        """Establish connection to SFTP server"""
        logger.info(
            "Attempting to connect to server: %s:%d",
            self._config.host,
            self._config.port,
        )
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._config.host, self._config.port),
                timeout=self._config.timeout,
            )
            logger.debug("TCP connection established")
        except asyncio.TimeoutError:
            logger.error(
                "Connection timeout: %s:%d", self._config.host, self._config.port
            )
            raise ConnectionError(
                f"Connection timeout to {self._config.host}:{self._config.port}"
            )
        except OSError as e:
            logger.error("Failed to connect: %s", str(e))
            raise ConnectionError(f"Failed to connect: {str(e)}")

        # A_CONNECT
        logger.debug("Sending A_CONNECT")
        _, response = await self.send_and_receive(
            GenericApdu(
                ApduType.A_CONNECT,
                [
                    ApduItem(ApduItemType.SYSTEM_ID, b"DKNW10"),
                    ApduItem(ApduItemType.PROTOCOL_ID, b"SFTP11"),
                    ApduItem(ApduItemType.CLIENT_SIDE, b"\x00\x00"),
                    ApduItem(ApduItemType.JOB_ID, b"\x01\x10"),
                ],
            )
        )
        if not isinstance(response, GenericApdu) or response.type != ApduType.A_AUTHENT:
            logger.error("A_AUTHENT response not received")
            raise ValueError("A_AUTHENT not responded.")

        auth_challenge = response.get_item(ApduItemType.AUTH_REQ)
        if auth_challenge is None:
            logger.error("Invalid A_AUTHENT")
            raise ValueError("Invalid A_AUTHENT.")
        auth_response = Unicrypt().encrypt(auth_challenge)

        # A_AUTHENT_RSP
        logger.debug("Sending A_AUTHENT_RSP")
        _, response = await self.send_and_receive(
            GenericApdu(
                ApduType.A_AUTHENT_RSP, [ApduItem(ApduItemType.AUTH_RES, auth_response)]
            )
        )
        if not isinstance(response, GenericApdu) or response.type != ApduType.A_ACCEPT:
            logger.error("A_ACCEPT response not received")
            raise ValueError("A_ACCEPT not responded.")

        logger.info("Authentication successful, connection established")

    async def disconnect(self) -> None:
        """Close connection to SFTP server"""
        if self._writer:
            logger.info("Disconnecting from server")
            # A_RELEASE
            _, response = await self.send_and_receive(
                GenericApdu(ApduType.A_RELEASE, [])
            )
            if (
                not isinstance(response, GenericApdu)
                or response.type != ApduType.A_SYNC
            ):
                logger.error("A_SYNC response not received")
                raise ValueError("A_SYNC not responded.")

            try:
                self._writer.close()
                await self._writer.wait_closed()
                logger.debug("Connection closed")
            finally:
                self._writer = None
                self._reader = None

    async def send(self, apdu: ApduBase) -> bool:
        """Send APDU to the server

        Args:
            apdu: APDU to send

        Returns:
            Success flag indicating if the send operation was successful
        """
        if not self._writer:
            logger.error("Attempted to send while not connected")
            raise ConnectionError("Not connected")

        try:
            # Create and send NSDU
            nsdu = Nsdu(apdu=apdu)
            self._writer.write(nsdu.to_bytes())
            await self._writer.drain()
            if isinstance(apdu, GenericApdu):
                logger.debug("Sent APDU: %s", apdu.type.name)
            elif isinstance(apdu, FDataApdu):
                logger.debug("Sent APDU: F_DATA")
            else:
                logger.debug("Sent APDU: UNKNOWN")
            return True
        except (asyncio.TimeoutError, OSError) as e:
            logger.error("Failed to send data: %s", str(e))
            raise ConnectionError(f"Failed to send data: {str(e)}")

    async def receive(self) -> tuple[bool, ApduBase | None]:
        """Receive APDU response from the server

        Returns:
            Tuple containing:
            - Success flag
            - Received APDU if successful, None otherwise
        """
        if not self._reader:
            logger.error("Attempted to receive while not connected")
            raise ConnectionError("Not connected")

        try:
            # Read STX (0x02)
            stx = await self._reader.read(1)
            if not stx or stx[0] != 0x02:
                logger.error("Invalid STX received")
                return False, None

            # Read length (2 bytes)
            length_bytes = await self._reader.readexactly(2)
            apdu_len = int.from_bytes(length_bytes, "big")
            logger.debug("APDU data length: %d bytes", apdu_len)

            # Read APDU data
            apdu_data = await self._reader.readexactly(apdu_len)

            # Read potential CRC (2 bytes) and ETX
            if self._config.network == NetworkType.NB:
                crc = await self._reader.readexactly(2)

            etx = await self._reader.readexactly(1)
            if etx[0] != 0x03:
                logger.error("Invalid ETX received")
                return False, None

            # Create response stream
            stream = BytesIO()
            stream.write(stx)
            stream.write(length_bytes)
            stream.write(apdu_data)
            if self._config.network == NetworkType.NB:
                stream.write(crc)
            stream.write(etx)
            stream.seek(0)

            # Parse response NSDU
            try:
                response = Nsdu.read(stream)
                if isinstance(response.apdu, GenericApdu):
                    logger.debug("Received Generic APDU: %s", response.apdu.type)
                elif isinstance(response.apdu, FDataApdu):
                    logger.debug(
                        "Received F_DATA APDU: %d bytes", len(response.apdu.data)
                    )
                return True, response.apdu
            except ValueError as e:
                logger.error("NSDU parsing error: %s", str(e))
                return False, None

        except (asyncio.TimeoutError, asyncio.IncompleteReadError, OSError) as e:
            logger.error("Failed to receive data: %s", str(e))
            raise ConnectionError(f"Failed to receive data: {str(e)}")

    async def send_and_receive(self, apdu: ApduBase) -> tuple[bool, ApduBase | None]:
        """Send APDU and receive response

        Args:
            apdu: APDU to send

        Returns:
            Tuple containing:
            - Success flag
            - Received APDU if successful, None otherwise
        """
        if not self._writer or not self._reader:
            logger.error("Attempted to send/receive while not connected")
            raise ConnectionError("Not connected")

        async with self._lock:
            try:
                if not await self.send(apdu):
                    return False, None
                return await self.receive()
            except ConnectionError as e:
                logger.error("Send/receive error: %s", str(e))
                return False, None

    async def download_file(self, dir: int, file: int, dest_path: str) -> int:
        logger.info("Starting file download - Directory: %d, File: %d", dir, file)
        # F_START
        _, response = await self.send_and_receive(
            GenericApdu(
                ApduType.F_START,
                [
                    ApduItem(
                        ApduItemType.FILE_OPERATION,
                        FileOperationType.READ.value.to_bytes(
                            length=2, byteorder="big"
                        ),
                    ),
                    ApduItem(
                        ApduItemType.FILE_NUMBER,
                        dir.to_bytes(length=2, byteorder="big")
                        + file.to_bytes(length=4, byteorder="big"),
                    ),
                ],
            )
        )
        if not isinstance(response, GenericApdu) or response.type != ApduType.F_READY:
            logger.error("F_READY response not received")
            raise ValueError("F_READY not responded.")

        expected_size_item = response.get_item(ApduItemType.EXPECT_FILE_SIZE)
        if expected_size_item is None:
            expected_size = None
        else:
            expected_size = int.from_bytes(expected_size_item, byteorder="big")
            logger.info("Expected file size: %d bytes", expected_size)

        downloaded_size = 0
        with open(dest_path, "wb") as dest_file:
            while True:
                _, response = await self.receive()
                if not isinstance(response, GenericApdu) and not isinstance(
                    response, FDataApdu
                ):
                    logger.error("Invalid SFTP message received")
                    raise ValueError("Invalid SFTP message received.")

                if isinstance(response, GenericApdu):
                    if response.type == ApduType.F_FINAL:
                        # Finish
                        break

                    logger.error("Unexpected APDU received: %s", response.type)
                    raise ValueError("Unexpected APDU received.")

                data_size = len(response.data)
                downloaded_size += data_size
                dest_file.write(response.data)
                if expected_size is None:
                    logger.debug(
                        "Received data chunk: %d bytes (Total: %d)",
                        data_size,
                        downloaded_size,
                    )
                else:
                    logger.debug(
                        "Received data chunk: %d bytes (Total: %d/%d)",
                        data_size,
                        downloaded_size,
                        expected_size,
                    )

        # F_END
        logger.debug("Sending F_END")
        await self.send(GenericApdu(ApduType.F_END, []))

        logger.info(
            "File download completed: %s (%d bytes)", dest_path, downloaded_size
        )
        return downloaded_size

    async def upload_file(self, src_path: str, dir: int, file: int) -> int:
        file_size = path.getsize(src_path)
        logger.info(
            "Starting file upload - Path: %s, Size: %d bytes", src_path, file_size
        )

        # F_START
        _, response = await self.send_and_receive(
            GenericApdu(
                ApduType.F_START,
                [
                    ApduItem(
                        ApduItemType.FILE_OPERATION,
                        FileOperationType.REPLACE.value.to_bytes(
                            length=2, byteorder="big"
                        ),
                    ),
                    ApduItem(
                        ApduItemType.FILE_NUMBER,
                        dir.to_bytes(length=2, byteorder="big")
                        + file.to_bytes(length=4, byteorder="big"),
                    ),
                    ApduItem(
                        ApduItemType.EXPECT_FILE_SIZE,
                        file_size.to_bytes(length=4, byteorder="big"),
                    ),
                ],
            )
        )
        if not isinstance(response, GenericApdu) or response.type != ApduType.F_READY:
            logger.error("F_READY response not received")
            raise ValueError("F_READY not responded.")

        expected_size_item = response.get_item(ApduItemType.EXPECT_FILE_SIZE)
        if expected_size_item is None:
            logger.error("Invalid F_READY")
            raise ValueError("Invalid F_READY.")
        expected_size = int.from_bytes(expected_size_item, byteorder="big")
        if expected_size != file_size:
            logger.error(
                "File size mismatch - Expected: %d, Actual: %d",
                expected_size,
                file_size,
            )
            raise ValueError("EXPECT_FILE_SIZE mismatch.")

        uploaded_size = 0
        with open(src_path, "rb") as src_file:
            while True:
                buffer = src_file.read(self.__DATA_CHUNK_SIZE)
                if len(buffer) == 0:
                    break
                # F_DATA
                data_size = len(buffer)
                uploaded_size += data_size
                logger.debug(
                    "Sending data chunk: %d bytes (Total: %d/%d)",
                    data_size,
                    uploaded_size,
                    file_size,
                )

                result = await self.send(FDataApdu(buffer))
                if not result:
                    logger.error("F_DATA sending failed")
                    raise RuntimeError("F_DATA sending failed.")

        # F_FINAL
        logger.debug("Sending F_FINAL")
        _, response = await self.send_and_receive(GenericApdu(ApduType.F_FINAL, []))
        if not isinstance(response, GenericApdu) or response.type != ApduType.F_END:
            logger.error("F_END response not received")
            raise ValueError("F_END not responded.")

        logger.info("File upload completed: %d bytes", file_size)
        return file_size

    async def __aenter__(self) -> Self:
        """Context manager enter"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        await self.disconnect()
