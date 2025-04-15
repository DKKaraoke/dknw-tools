import asyncio
from dataclasses import dataclass
import logging
import os
from typing import Self

from .command import DS2FTPCTS, DS2FTPCommand, DS2FTPCommandType, FileMode

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class DS2FTPConfig:
    """DS2FTP client configuration."""

    host: str
    ctrl_port: int = 23105  # 0x59c1
    data_port: int = 23104  # 0x59c0
    timeout: float = 5.0
    chunk_size: int = 0x3C8C0  # Default chunk size (248000 bytes)


class DS2FTPChannel:
    """DS2FTP communication channel (control or data)."""

    def __init__(self, name: str, host: str, port: int, timeout: float) -> None:
        """Initialize channel."""
        self.name = name
        self.host = host
        self.port = port
        self.timeout = timeout
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        """Connect to the channel."""
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.timeout
            )
            logger.debug(
                f"{self.name} channel connection established to {self.host}:{self.port}"
            )
        except asyncio.TimeoutError:
            logger.error(
                f"{self.name} channel connection timeout: {self.host}:{self.port}"
            )
            raise ConnectionError(
                f"{self.name} channel connection timeout to {self.host}:{self.port}"
            )
        except OSError as e:
            logger.error(f"Failed to connect to {self.name} channel: {str(e)}")
            raise ConnectionError(f"Failed to connect to {self.name} channel: {str(e)}")

    async def disconnect(self) -> None:
        """Disconnect from the channel."""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
                logger.debug(f"{self.name} channel closed")
            except Exception as e:
                logger.error(f"Error closing {self.name} channel: {e}")
            finally:
                self.writer = None
                self.reader = None

    async def send(self, data: bytes) -> bool:
        """Send data on the channel."""
        if not self.writer:
            logger.error(
                f"Attempted to send on {self.name} channel while not connected"
            )
            raise ConnectionError(f"{self.name} channel not connected")

        try:
            self.writer.write(data)
            await self.writer.drain()
            logger.debug(f"Sent {len(data)} bytes on {self.name} channel")
            return True
        except (asyncio.TimeoutError, OSError) as e:
            logger.error(f"Failed to send data on {self.name} channel: {str(e)}")
            raise ConnectionError(
                f"Failed to send data on {self.name} channel: {str(e)}"
            )

    async def receive(self, size: int, timeout: float | None = None) -> bytes:
        """Receive data from the channel."""
        if not self.reader:
            logger.error(
                f"Attempted to receive on {self.name} channel while not connected"
            )
            raise ConnectionError(f"{self.name} channel not connected")

        timeout_val = timeout or self.timeout

        try:
            data = await asyncio.wait_for(self.reader.read(size), timeout=timeout_val)

            if not data:
                raise ConnectionError(f"{self.name} channel closed by server")

            logger.debug(f"Received {len(data)} bytes on {self.name} channel")
            return data

        except asyncio.TimeoutError:
            logger.error(f"{self.name} channel receive timeout")
            raise ConnectionError(f"{self.name} channel receive timeout")
        except OSError as e:
            logger.error(f"Failed to receive data from {self.name} channel: {str(e)}")
            raise ConnectionError(
                f"Failed to receive data from {self.name} channel: {str(e)}"
            )


class DS2FTPClient:
    """Async DS2FTP client implementation with separate control and data ports."""

    def __init__(self, config: DS2FTPConfig) -> None:
        """Initialize DS2FTP client."""
        self._config = config

        # Communication channels
        self._ctrl_channel = DS2FTPChannel(
            "Control", config.host, config.ctrl_port, config.timeout
        )
        self._data_channel = DS2FTPChannel(
            "Data", config.host, config.data_port, config.timeout
        )

        self._lock = asyncio.Lock()

        # Internal state
        self.mode = FileMode.NONE
        self.dir = 0
        self.file = 0
        self.total = 0
        self.done = 0
        self.last_cts = DS2FTPCTS()

        logger.debug(
            f"Initializing DS2FTP client: {config.host} (Ctrl: {config.ctrl_port}, Data: {config.data_port})"
        )

    async def connect(self) -> None:
        """Connect to control and data ports."""
        logger.info(
            f"Connecting to server: {self._config.host} (Ctrl: {self._config.ctrl_port}, Data: {self._config.data_port})"
        )

        try:
            # Connect to control channel first
            await self._ctrl_channel.connect()

            try:
                # Then connect to data channel
                await self._data_channel.connect()
            except Exception as e:
                # If data channel connection fails, close control channel
                await self._ctrl_channel.disconnect()
                raise e

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise ConnectionError(f"Failed to connect: {e}")

    async def disconnect(self) -> None:
        """Disconnect from control and data ports."""
        logger.info("Disconnecting from server")

        # Close both channels
        await self._data_channel.disconnect()
        await self._ctrl_channel.disconnect()

    async def ctrl_send(self, data: bytes) -> bool:
        """Send data on control channel."""
        return await self._ctrl_channel.send(data)

    async def ctrl_receive(self, timeout: float | None = None) -> bytes:
        """Receive data from control channel with DS2FTP protocol parsing."""
        if not self._ctrl_channel.reader:
            raise ConnectionError("Control channel not connected")

        timeout_val = timeout or self._config.timeout

        try:
            # Find DS2 header
            while True:
                header = await asyncio.wait_for(
                    self._ctrl_channel.reader.read(4), timeout=timeout_val
                )
                if not header:
                    raise ConnectionError("Control channel closed by server")

                if header == DS2FTPCommand.DS2_HEADER:
                    break

            # Read command type
            cmd_type_bytes = await asyncio.wait_for(
                self._ctrl_channel.reader.read(4), timeout=timeout_val
            )
            if not cmd_type_bytes or len(cmd_type_bytes) < 4:
                raise ConnectionError(
                    "Failed to read command type from control channel"
                )

            cmd_type = int.from_bytes(cmd_type_bytes, "big")

            # Determine command length
            cmd_length = 0
            for i, cmd_id in enumerate(DS2FTPCommand.DS2FTP_CMD):
                if cmd_id == cmd_type:
                    cmd_length = DS2FTPCommand.DS2FTP_CMD_LENGTH[i]
                    break

            if cmd_length == 0:
                logger.error(
                    f"Unknown command type received on control channel: {cmd_type}"
                )
                return header + cmd_type_bytes

            # Read remaining command body
            remaining = cmd_length - 8  # header(4) + command type(4)
            cmd_body = await asyncio.wait_for(
                self._ctrl_channel.reader.read(remaining), timeout=timeout_val
            )

            if not cmd_body or len(cmd_body) < remaining - 4:
                raise ConnectionError(
                    "Failed to read command body from control channel"
                )

            # For ERRORCTS, read additional variable length data
            if cmd_type == DS2FTPCommandType.ERRORCTS.value:
                more_data = bytearray()
                try:
                    while True:
                        byte = await asyncio.wait_for(
                            self._ctrl_channel.reader.read(1),
                            timeout=1.0,  # Shorter timeout for error message
                        )
                        if not byte or byte == b"\n":
                            break
                        more_data.extend(byte)
                except asyncio.TimeoutError:
                    pass  # End of data or timeout

                if more_data:
                    cmd_body += more_data

            return header + cmd_type_bytes + cmd_body

        except asyncio.TimeoutError:
            logger.error("Control channel receive timeout")
            raise ConnectionError("Control channel receive timeout")
        except OSError as e:
            logger.error(f"Failed to receive data from control channel: {str(e)}")
            raise ConnectionError(
                f"Failed to receive data from control channel: {str(e)}"
            )

    async def data_send(self, data: bytes) -> bool:
        """Send data on data channel."""
        return await self._data_channel.send(data)

    async def data_receive(self, size: int, timeout: float | None = None) -> bytes:
        """Receive specified size of data from data channel with partial read handling."""
        if not self._data_channel.reader:
            raise ConnectionError("Data channel not connected")

        timeout_val = timeout or self._config.timeout
        received_data = bytearray()
        remaining = size

        try:
            while remaining > 0:
                chunk = await asyncio.wait_for(
                    self._data_channel.reader.read(remaining), timeout=timeout_val
                )

                if not chunk:  # Connection closed
                    if not received_data:  # Data nothing to error
                        raise ConnectionError("Data channel closed by server")
                    break  # Partial data received

                received_data.extend(chunk)
                remaining -= len(chunk)
                logger.debug(
                    f"Received chunk of {len(chunk)} bytes, {remaining} bytes remaining"
                )

                # Shorten timeout
                if remaining > 0:
                    timeout_val = min(timeout_val, 2.0)

            total_received = len(received_data)
            logger.debug(
                f"Received total of {total_received} bytes on Data channel (requested: {size})"
            )
            return bytes(received_data)

        except asyncio.TimeoutError:
            # Partial data received
            if received_data:
                logger.warning(
                    f"Partial data received ({len(received_data)}/{size} bytes) before timeout"
                )
                return bytes(received_data)

            logger.error("Data channel receive timeout")
            raise ConnectionError("Data channel receive timeout")

    def _reset_processing_info(self) -> None:
        """Reset transfer state."""
        self.mode = FileMode.NONE
        self.dir = 0
        self.file = 0
        self.total = 0
        self.done = 0

    async def send_cts(self, size: int) -> bool:
        """Send CTS (control channel)."""
        # Use current state to generate CTS
        cmd = DS2FTPCommand()

        # Generate CTS with current state
        data = cmd.make_cts(self.total, self.done, size)

        # Record sent CTS
        self.last_cts.tsize = self.total
        self.last_cts.fsize = self.done
        self.last_cts.bsize = size

        logger.debug(
            f"Sending CTS - total: {self.total}, done: {self.done}, next: {size}"
        )
        return await self.ctrl_send(data)

    async def send_error_cts(self, error_code: int, error_msg: str = "") -> bool:
        """Send error CTS (control channel)."""
        cmd = DS2FTPCommand()
        data = cmd.make_errorcts(0, 0, error_code, error_msg)
        return await self.ctrl_send(data)

    async def download_file(self, dir: int, file: int, dest_path: str) -> int | None:
        """
        Download a file from the server.

        Args:
            dir: Directory number
            file: File number
            dest_path: Local destination path

        Returns:
            Number of bytes downloaded (0 on failure)
        """
        logger.debug(f"Starting file download - Directory: {dir}, File: {file}")

        # Ensure connected
        if not self._ctrl_channel.writer or not self._data_channel.writer:
            await self.connect()

        async with self._lock:
            try:
                # Reset processing state
                self._reset_processing_info()

                # Create and send RTS command (filesize=0 for download request)
                cmd = DS2FTPCommand()
                rts_data = cmd.make_rts(dir, file, 0)
                if not await self.ctrl_send(rts_data):
                    logger.error("Failed to send RTS")
                    return 0

                # Receive initial CTS response
                logger.debug("Waiting for initial CTS from server")
                initial_response_data = await self.ctrl_receive()
                cmd = DS2FTPCommand()
                cmd_type = cmd.parse_rx_buffer(
                    initial_response_data, len(initial_response_data)
                )

                if cmd_type != DS2FTPCommandType.CTS:
                    logger.debug(f"Unexpected initial response type: {cmd_type}")
                    return None

                initial_cts = cmd.get_cts()
                if not initial_cts:
                    logger.error("Invalid initial CTS response")
                    return None

                # Record server's CTS values
                received_cts = DS2FTPCTS()
                received_cts.tsize = initial_cts.tsize
                received_cts.fsize = initial_cts.fsize
                received_cts.bsize = initial_cts.bsize

                logger.debug(
                    f"Received initial CTS: tsize={received_cts.tsize}, fsize={received_cts.fsize}, bsize={received_cts.bsize}"
                )

                # Set file information
                self.mode = FileMode.GET
                self.dir = dir
                self.file = file
                self.total = received_cts.tsize
                self.done = received_cts.fsize

                if self.total < 1:
                    logger.error("File empty")
                    return 0

                # Prepare for file writing
                downloaded_size = 0

                # Create parent directories if they don't exist
                os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

                with open(dest_path, "wb") as dest_file:
                    # Send CTS acknowledgment (same values as received)
                    logger.debug(
                        f"Sending first CTS acknowledgment: tsize={received_cts.tsize}, fsize={received_cts.fsize}, bsize={received_cts.bsize}"
                    )
                    cmd = DS2FTPCommand()
                    cts_data = cmd.make_cts(
                        received_cts.tsize, received_cts.fsize, received_cts.bsize
                    )
                    if not await self.ctrl_send(cts_data):
                        logger.error("Failed to send CTS acknowledgment")
                        return 0

                    while self.done < self.total:
                        # Receive data chunk
                        chunk_size = received_cts.bsize
                        logger.debug(f"Receiving data chunk of size {chunk_size}")
                        chunk_data = await self.data_receive(chunk_size)
                        if not chunk_data:
                            logger.error("Failed to receive data chunk")
                            break

                        # Write to file
                        dest_file.write(chunk_data)

                        # Update progress
                        chunk_length = len(chunk_data)
                        self.done += chunk_length
                        downloaded_size += chunk_length

                        logger.debug(
                            f"Received data chunk: {chunk_length} bytes (Total: {downloaded_size}/{self.total})"
                        )

                        if self.done >= self.total:
                            logger.debug("All data received, download complete")
                            break

                        # Receive next CTS from server
                        logger.debug("Waiting for next CTS from server")
                        try:
                            next_response_data = await self.ctrl_receive(
                                timeout=3.0
                            )  # Shorten timeout
                            cmd = DS2FTPCommand()
                            cmd_type = cmd.parse_rx_buffer(
                                next_response_data, len(next_response_data)
                            )

                            if cmd_type != DS2FTPCommandType.CTS:
                                if cmd_type == DS2FTPCommandType.ERRORCTS:
                                    err_cts = cmd.get_errorcts()
                                    logger.error(
                                        f"Received ERRORCTS: {err_cts.error_msg if err_cts else 'Unknown error'}"
                                    )
                                else:
                                    logger.error(
                                        f"Unexpected response type: {cmd_type}"
                                    )
                                break

                            next_cts = cmd.get_cts()
                            if not next_cts:
                                logger.error("Invalid next CTS response")
                                break

                            # Log received CTS
                            logger.debug(
                                f"Received next CTS: tsize={next_cts.tsize}, fsize={next_cts.fsize}, bsize={next_cts.bsize}"
                            )

                            # Save received CTS
                            received_cts.tsize = next_cts.tsize
                            received_cts.fsize = next_cts.fsize
                            received_cts.bsize = next_cts.bsize

                            # Exit loop if all data received
                            if next_cts.fsize >= next_cts.tsize:
                                logger.debug(
                                    "Download complete as indicated by server CTS"
                                )
                                break
                        except ConnectionError as e:
                            # Handle cases where the server does not send the next CTS after the last data chunk is sent
                            if (
                                "timeout" in str(e).lower()
                                and self.done >= self.total - chunk_length
                            ):
                                logger.debug(
                                    "Expected timeout after all data received, download complete"
                                )
                                break
                            else:
                                logger.error(f"Connection error waiting for CTS: {e}")
                                raise

                        # Send CTS acknowledgment (same values as received)
                        logger.debug(
                            f"Sending CTS acknowledgment: tsize={received_cts.tsize}, fsize={received_cts.fsize}, bsize={received_cts.bsize}"
                        )
                        cmd = DS2FTPCommand()
                        cts_data = cmd.make_cts(
                            received_cts.tsize, received_cts.fsize, received_cts.bsize
                        )
                        if not await self.ctrl_send(cts_data):
                            logger.error("Failed to send CTS acknowledgment")
                            break

                logger.debug(
                    f"File download completed: {dest_path} ({downloaded_size} bytes)"
                )
                self._reset_processing_info()
                return downloaded_size

            except Exception as e:
                logger.error(f"Download error: {e}")
                self._reset_processing_info()
                return 0

    async def upload_file(self, src_path: str, dir: int, file: int) -> int:
        """
        Upload a file to the server.

        Args:
            src_path: Local source file path
            dir: Directory number
            file: File number

        Returns:
            Number of bytes uploaded (0 on failure)
        """
        logger.debug(f"Starting file upload - Path: {src_path}")

        # Get file size
        try:
            file_size = os.path.getsize(src_path)
        except OSError as e:
            logger.error(f"Failed to get file size: {e}")
            return 0

        # Ensure connected
        if not self._ctrl_channel.writer or not self._data_channel.writer:
            await self.connect()

        async with self._lock:
            try:
                # Reset processing state
                self._reset_processing_info()

                # Create and send RTS command (filesize>0 for upload request)
                cmd = DS2FTPCommand()
                rts_data = cmd.make_rts(dir, file, file_size)
                if not await self.ctrl_send(rts_data):
                    logger.error("Failed to send RTS")
                    return 0

                # Receive CTS response
                logger.debug("Waiting for initial CTS from server")
                response_data = await self.ctrl_receive()
                cmd = DS2FTPCommand()
                cmd_type = cmd.parse_rx_buffer(response_data, len(response_data))

                if cmd_type != DS2FTPCommandType.CTS:
                    logger.error(f"Unexpected response type: {cmd_type}")
                    return 0

                initial_cts = cmd.get_cts()
                if not initial_cts:
                    logger.error("Invalid CTS response")
                    return 0

                logger.debug(
                    f"Received initial CTS: tsize={initial_cts.tsize}, fsize={initial_cts.fsize}, bsize={initial_cts.bsize}"
                )

                # Set file information
                self.mode = FileMode.PUT
                self.dir = dir
                self.file = file
                self.total = initial_cts.tsize  # Use server's value
                self.done = initial_cts.fsize  # Use server's value

                # Prepare for file reading
                uploaded_size = 0

                with open(src_path, "rb") as src_file:
                    # For uploads, receive CTS first then send data
                    received_cts = initial_cts

                    while self.done < self.total:
                        # Use server's bsize from CTS
                        chunk_size = received_cts.bsize
                        logger.debug(f"Preparing to send chunk of size {chunk_size}")

                        # Read data chunk
                        src_file.seek(self.done)  # Seek to exact position
                        chunk_data = src_file.read(chunk_size)
                        if not chunk_data:
                            logger.warning("End of file reached unexpectedly")
                            break

                        # Send data (using data channel)
                        logger.debug(f"Sending data chunk: {len(chunk_data)} bytes")
                        if not await self.data_send(chunk_data):
                            logger.error("Failed to send data chunk")
                            return uploaded_size

                        # Update progress
                        chunk_length = len(chunk_data)
                        self.done += chunk_length
                        uploaded_size += chunk_length

                        logger.debug(
                            f"Sent data chunk: {chunk_length} bytes (Total: {uploaded_size}/{self.total})"
                        )

                        if self.done >= self.total:
                            logger.debug("All data sent, upload complete")
                            break

                        # Receive next CTS
                        logger.debug("Waiting for next CTS from server")
                        try:
                            response_data = await self.ctrl_receive(
                                timeout=3.0
                            )  # Shorten timeout
                            cmd = DS2FTPCommand()
                            cmd_type = cmd.parse_rx_buffer(
                                response_data, len(response_data)
                            )

                            if cmd_type != DS2FTPCommandType.CTS:
                                if cmd_type == DS2FTPCommandType.ERRORCTS:
                                    err_cts = cmd.get_errorcts()
                                    logger.error(
                                        f"Received ERRORCTS: {err_cts.error_msg if err_cts else 'Unknown error'}"
                                    )
                                else:
                                    logger.error(
                                        f"Unexpected response type: {cmd_type}"
                                    )
                                break

                            next_cts = cmd.get_cts()
                            if not next_cts:
                                logger.error("Invalid next CTS response")
                                break

                            # Log received CTS
                            logger.debug(
                                f"Received next CTS: tsize={next_cts.tsize}, fsize={next_cts.fsize}, bsize={next_cts.bsize}"
                            )

                            # Save received CTS for next iteration
                            received_cts = next_cts

                            # Exit loop if all data sent
                            if next_cts.fsize >= next_cts.tsize:
                                logger.debug(
                                    "Upload complete as indicated by server CTS"
                                )
                                break
                        except ConnectionError as e:
                            # Handle cases where the server does not send the next CTS after the last data chunk is sent
                            if (
                                "timeout" in str(e).lower()
                                and self.done >= self.total - chunk_length
                            ):
                                logger.debug(
                                    "Expected timeout after all data sent, upload complete"
                                )
                                break
                            else:
                                logger.error(f"Connection error waiting for CTS: {e}")
                                raise

                logger.debug(f"File upload completed: {uploaded_size} bytes")
                self._reset_processing_info()
                return uploaded_size

            except Exception as e:
                logger.error(f"Upload error: {e}")
                self._reset_processing_info()
                return 0

    async def exists_file(self, dir: int, file: int) -> bool:
        """Check if file exists on the server."""
        logger.debug(f"Checking file existence - Directory: {dir}, File: {file}")

        try:
            # Create a temporary file for the check
            temp_file = os.path.join(
                os.path.dirname(__file__), f"temp_check_{dir}_{file}"
            )
            try:
                # Try to download to check existence
                result = await self.download_file(dir, file, temp_file)
                exists = result > 0

                # Clean up temporary file
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

                return exists
            except Exception as e:
                logger.error(f"Error checking file existence: {e}")

                # Clean up temporary file
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

                return False
        except Exception as e:
            logger.error(f"File check error: {e}")
            return False

    async def __aenter__(self) -> Self:
        """Context manager enter."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        await self.disconnect()
