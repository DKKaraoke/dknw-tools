import datetime
from enum import Enum
import logging
import os
from typing import (
    Any,
    TypeVar,
    Type,
    cast,
    ParamSpec,
    Optional,
    Protocol,
    runtime_checkable,
    Union,
)

import fire
import tqdm

from denmoku.methods import NetworkConfig, NetworkScanner
from sftp.sftp_client import SftpClient, SftpConfig
from ds2ftp.client import DS2FTPClient, DS2FTPConfig


T = TypeVar("T")
P = ParamSpec("P")


class ProtocolType(str, Enum):
    """File transfer protocol types"""

    SFTP = "sftp"
    DS2FTP = "ds2ftp"


@runtime_checkable
class FileTransferClient(Protocol):
    """Protocol for file transfer clients"""

    async def connect(self) -> None:
        """Establish connection"""
        ...

    async def disconnect(self) -> None:
        """Close connection"""
        ...

    async def exists_file(self, dir: int, file: int) -> bool:
        """Check if file exists"""
        ...

    async def download_file(
        self, dir: int, file: int, dest_path: str
    ) -> Union[int, None]:
        """Download file to destination path"""
        ...

    async def upload_file(self, src_path: str, dir: int, file: int) -> Union[int, None]:
        """Upload file from source path"""
        ...

    async def __aenter__(self) -> "FileTransferClient":
        """Context manager enter"""
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        ...


class ClientFactory:
    """Factory for creating file transfer clients"""

    @staticmethod
    def create_client(
        protocol: ProtocolType,
        host: str,
        port: int,
        ctrl_port: Optional[int] = None,
        data_port: Optional[int] = None,
        timeout: float = 5.0,
    ) -> FileTransferClient:
        """Create a file transfer client based on the protocol type

        Args:
            protocol: Protocol type (sftp or ds2ftp)
            host: Host address
            port: Main port (for SFTP) or data port (for DS2FTP if data_port not specified)
            ctrl_port: Control port for DS2FTP (optional, default: port+1)
            data_port: Data port for DS2FTP (optional, default: port)
            timeout: Connection timeout

        Returns:
            A file transfer client instance
        """
        if protocol == ProtocolType.SFTP:
            return SftpClient(SftpConfig(host=host, port=port, timeout=timeout))
        elif protocol == ProtocolType.DS2FTP:
            # Default: data_port is port, ctrl_port is port+1
            _data_port = data_port or port
            _ctrl_port = ctrl_port or (_data_port + 1)
            return DS2FTPClient(
                DS2FTPConfig(
                    host=host,
                    ctrl_port=_ctrl_port,
                    data_port=_data_port,
                    timeout=timeout,
                )
            )
        else:
            raise ValueError(f"Unsupported protocol: {protocol}")


class Cli:
    """Command-line interface for DKNW tools."""

    @staticmethod
    def __config_logger(level: str) -> None:
        """Configure the logging system with the specified level and format.

        Sets up a basic logging configuration with a standardized format that includes
        timestamp, log level, module name, function name, line number and message.

        Args:
            level: The logging level to use (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        """
        logging.basicConfig(
            level=level,
            format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        )

    def __init__(self, log_level: str = "INFO") -> None:
        """Initialize the dknw-tools CLI.

        Args:
            log_level: The logging level to use. Defaults to "INFO".
        """
        Cli.__config_logger(log_level)
        self.__logger = logging.getLogger(__name__)

    @staticmethod
    def _validate_arg(arg: Any, arg_name: str, expected_type: Type[T]) -> T:
        """Validate that an argument is of the expected type.

        Args:
            arg: The argument to validate
            arg_name: The name of the argument (for error messages)
            expected_type: The expected type of the argument

        Returns:
            The validated argument

        Raises:
            ValueError: If the argument is not of the expected type
        """
        if not isinstance(arg, expected_type):
            raise ValueError(
                f"Argument `{arg_name}` must be a {expected_type.__name__}."
            )
        return cast(T, arg)

    def scan_terminals(
        self, target: str, timeout: float = 5.0, workers: int = 255
    ) -> None:
        """Scan DAM terminals.

        Args:
            target: Target network CIDR
            timeout: Timeout in seconds. Defaults to 5.0.
            workers: Number of workers. Defaults to 255.

        Raises:
            ValueError: If any argument is of incorrect type
        """
        target = self._validate_arg(target, "target", str)
        timeout = self._validate_arg(timeout, "timeout", float)
        workers = self._validate_arg(workers, "workers", int)

        config = NetworkConfig(timeout=timeout, max_workers=workers)
        scanner = NetworkScanner(config)
        scanner.scan_terminals(target)

    async def _check_file_existence(
        self,
        client: FileTransferClient,
        dir_num: int,
        file_num: int,
        dest_path: str | None = None,
    ) -> bool:
        """Check if a file exists in the server.

        Args:
            client: The file transfer client
            dir_num: Directory number
            file_num: File number
            dest_path: Optional destination path to download the file to

        Returns:
            True if the file exists, False otherwise
        """
        if dest_path is None:
            return await client.exists_file(dir_num, file_num)
        else:
            result = await client.download_file(dir_num, file_num, dest_path)
            return result is not None and result > 0

    async def search_dirs(
        self,
        host: str,
        port: int,
        protocol: str = "sftp",
        ctrl_port: Optional[int] = None,
        data_port: Optional[int] = None,
        dest: str | None = None,
    ) -> None:
        """Search directories in a DAM terminal.

        Args:
            host: DAM terminal address
            port: DAM terminal port (main port for SFTP, data port for DS2FTP if data_port not specified)
            protocol: Protocol type ("sftp" or "ds2ftp"). Defaults to "sftp".
            ctrl_port: Control port for DS2FTP (optional, default: port+1)
            data_port: Data port for DS2FTP (optional, default: port)
            dest: Destination file path. If provided, found files will be downloaded.

        Raises:
            ValueError: If any argument is of incorrect type
        """
        host = self._validate_arg(host, "host", str)
        port = self._validate_arg(port, "port", int)
        protocol = self._validate_arg(protocol, "protocol", str)
        if ctrl_port is not None:
            ctrl_port = self._validate_arg(ctrl_port, "ctrl_port", int)
        if data_port is not None:
            data_port = self._validate_arg(data_port, "data_port", int)
        if dest is not None:
            dest = self._validate_arg(dest, "dest", str)
            os.makedirs(dest, exist_ok=True)

        try:
            protocol_type = ProtocolType(protocol.lower())
        except ValueError:
            raise ValueError(
                f"Unsupported protocol: {protocol}. Use 'sftp' or 'ds2ftp'."
            )

        client = ClientFactory.create_client(
            protocol=protocol_type,
            host=host,
            port=port,
            ctrl_port=ctrl_port,
            data_port=data_port,
        )

        async with client:

            async def exists_dir(dir_num: int) -> bool:
                # Check common file numbers
                for i in range(6):
                    for j in range(1, 10):
                        file_num = 10**i * j
                        dest_path = (
                            None
                            if dest is None
                            else os.path.join(dest, f"{dir_num}.{file_num}")
                        )
                        if await self._check_file_existence(
                            client, dir_num, file_num, dest_path
                        ):
                            return True

                # Check date-based file
                mmdd = datetime.datetime.now().strftime("%m%d")
                file_num = int(f"1{mmdd}")
                dest_path = (
                    None
                    if dest is None
                    else os.path.join(dest, f"{dir_num}.{file_num}")
                )
                return await self._check_file_existence(
                    client, dir_num, file_num, dest_path
                )

            # Use tqdm for progress tracking
            for dir_num in tqdm.trange(1, 9999):
                if await exists_dir(dir_num):
                    tqdm.tqdm.write(f"Directory found: {dir_num}")

    async def download_file(
        self,
        host: str,
        port: int,
        dir: int,
        file: int,
        dest: str,
        protocol: str = "sftp",
        ctrl_port: Optional[int] = None,
        data_port: Optional[int] = None,
    ) -> None:
        """Download a file from a DAM terminal.

        Args:
            host: DAM terminal address
            port: DAM terminal port (main port for SFTP, data port for DS2FTP if data_port not specified)
            dir: Directory number
            file: File number
            dest: Destination file path
            protocol: Protocol type ("sftp" or "ds2ftp"). Defaults to "sftp".
            ctrl_port: Control port for DS2FTP (optional, default: port+1)
            data_port: Data port for DS2FTP (optional, default: port)

        Raises:
            ValueError: If any argument is of incorrect type
        """
        host = self._validate_arg(host, "host", str)
        port = self._validate_arg(port, "port", int)
        dir = self._validate_arg(dir, "dir", int)
        file = self._validate_arg(file, "file", int)
        dest = self._validate_arg(dest, "dest", str)
        protocol = self._validate_arg(protocol, "protocol", str)
        if ctrl_port is not None:
            ctrl_port = self._validate_arg(ctrl_port, "ctrl_port", int)
        if data_port is not None:
            data_port = self._validate_arg(data_port, "data_port", int)

        try:
            protocol_type = ProtocolType(protocol.lower())
        except ValueError:
            raise ValueError(
                f"Unsupported protocol: {protocol}. Use 'sftp' or 'ds2ftp'."
            )

        client = ClientFactory.create_client(
            protocol=protocol_type,
            host=host,
            port=port,
            ctrl_port=ctrl_port,
            data_port=data_port,
        )

        async with client:
            result = await client.download_file(dir, file, dest)
            if result is None:
                self.__logger.warning(f"Failed to download file {dir}.{file}")
            else:
                self.__logger.info(f"Successfully downloaded {result} bytes to {dest}")

    async def upload_file(
        self,
        host: str,
        port: int,
        src: str,
        dir: int,
        file: int,
        protocol: str = "sftp",
        ctrl_port: Optional[int] = None,
        data_port: Optional[int] = None,
    ) -> None:
        """Upload a file to a DAM terminal.

        Args:
            host: DAM terminal address
            port: DAM terminal port (main port for SFTP, data port for DS2FTP if data_port not specified)
            src: Source file path
            dir: Directory number
            file: File number
            protocol: Protocol type ("sftp" or "ds2ftp"). Defaults to "sftp".
            ctrl_port: Control port for DS2FTP (optional, default: port+1)
            data_port: Data port for DS2FTP (optional, default: port)

        Raises:
            ValueError: If any argument is of incorrect type
        """
        host = self._validate_arg(host, "host", str)
        port = self._validate_arg(port, "port", int)
        src = self._validate_arg(src, "src", str)
        dir = self._validate_arg(dir, "dir", int)
        file = self._validate_arg(file, "file", int)
        protocol = self._validate_arg(protocol, "protocol", str)
        if ctrl_port is not None:
            ctrl_port = self._validate_arg(ctrl_port, "ctrl_port", int)
        if data_port is not None:
            data_port = self._validate_arg(data_port, "data_port", int)

        if not os.path.exists(src):
            raise FileNotFoundError(f"Source file '{src}' not found")

        try:
            protocol_type = ProtocolType(protocol.lower())
        except ValueError:
            raise ValueError(
                f"Unsupported protocol: {protocol}. Use 'sftp' or 'ds2ftp'."
            )

        client = ClientFactory.create_client(
            protocol=protocol_type,
            host=host,
            port=port,
            ctrl_port=ctrl_port,
            data_port=data_port,
        )

        async with client:
            result = await client.upload_file(src, dir, file)
            if result is None or result == 0:
                self.__logger.warning(f"Failed to upload file {src} to {dir}.{file}")
            else:
                self.__logger.info(
                    f"Successfully uploaded {result} bytes to {dir}.{file}"
                )


def main() -> None:
    """Entry point for the dknw-tools CLI application."""
    fire.Fire(Cli)


if __name__ == "__main__":
    main()
