import datetime
import logging
import os
from typing import Any, TypeVar, Type, cast, ParamSpec

import fire
import tqdm

from denmoku.methods import NetworkConfig, NetworkScanner
from sftp.sftp_client import SftpClient, SftpConfig


T = TypeVar("T")
P = ParamSpec("P")


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
        sftp_client: SftpClient,
        dir_num: int,
        file_num: int,
        dest_path: str | None = None,
    ) -> bool:
        """Check if a file exists in the SFTP server.

        Args:
            sftp_client: The SFTP client
            dir_num: Directory number
            file_num: File number
            dest_path: Optional destination path to download the file to

        Returns:
            True if the file exists, False otherwise
        """
        if dest_path is None:
            return await sftp_client.exists_file(dir_num, file_num)
        else:
            return (
                await sftp_client.download_file(dir_num, file_num, dest_path)
            ) is not None

    async def search_dirs(self, host: str, port: int, dest: str | None = None) -> None:
        """Search directories in a DAM terminal.

        Args:
            host: DAM terminal address
            port: DAM terminal SFTP port
            dest: Destination file path. If provided, found files will be downloaded.

        Raises:
            ValueError: If any argument is of incorrect type
        """
        host = self._validate_arg(host, "host", str)
        port = self._validate_arg(port, "port", int)
        if dest is not None:
            dest = self._validate_arg(dest, "dest", str)
            os.makedirs(dest, exist_ok=True)

        sftp_config = SftpConfig(host, port)

        async with SftpClient(sftp_config) as sftp_client:

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
                            sftp_client, dir_num, file_num, dest_path
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
                    sftp_client, dir_num, file_num, dest_path
                )

            # Use tqdm for progress tracking
            for dir_num in tqdm.trange(1, 65535):
                if await exists_dir(dir_num):
                    tqdm.tqdm.write(f"Directory found: {dir_num}")

    async def download_file(
        self, host: str, port: int, dir: int, file: int, dest: str
    ) -> None:
        """Download a file from a DAM terminal.

        Args:
            host: DAM terminal address
            port: DAM terminal SFTP port
            dir: Directory number
            file: File number
            dest: Destination file path

        Raises:
            ValueError: If any argument is of incorrect type
        """
        host = self._validate_arg(host, "host", str)
        port = self._validate_arg(port, "port", int)
        dir = self._validate_arg(dir, "dir", int)
        file = self._validate_arg(file, "file", int)
        dest = self._validate_arg(dest, "dest", str)

        sftp_config = SftpConfig(host, port)
        async with SftpClient(sftp_config) as sftp_client:
            result = await sftp_client.download_file(dir, file, dest)
            if result is None:
                self.__logger.warning(f"Failed to download file {dir}.{file}")

    async def upload_file(
        self, host: str, port: int, src: str, dir: int, file: int
    ) -> None:
        """Upload a file to a DAM terminal.

        Args:
            host: DAM terminal address
            port: DAM terminal SFTP port
            src: Source file path
            dir: Directory number
            file: File number

        Raises:
            ValueError: If any argument is of incorrect type
        """
        host = self._validate_arg(host, "host", str)
        port = self._validate_arg(port, "port", int)
        src = self._validate_arg(src, "src", str)
        dir = self._validate_arg(dir, "dir", int)
        file = self._validate_arg(file, "file", int)

        if not os.path.exists(src):
            raise FileNotFoundError(f"Source file '{src}' not found")

        sftp_config = SftpConfig(host, port)
        async with SftpClient(sftp_config) as sftp_client:
            await sftp_client.upload_file(src, dir, file)


def main() -> None:
    """Entry point for the dknw-tools CLI application."""
    fire.Fire(Cli)


if __name__ == "__main__":
    main()
