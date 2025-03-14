import logging

import fire

from denmoku.methods import NetworkConfig, NetworkScanner
from sftp.sftp_client import SftpClient, SftpConfig


class Cli:
    @staticmethod
    def __config_logger(level: str) -> None:
        """Configure the logging system with the specified level and format.

        Sets up a basic logging configuration with a standardized format that includes
        timestamp, log level, module name, function name, line number and message.

        Args:
            level (str): The logging level to use (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        """
        logging.basicConfig(
            level=level,
            format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        )

    def __init__(self, log_level="INFO") -> None:
        """Initialize the dknw-tools CLI.

        Args:
            log_level (str, optional): The logging level to use. Defaults to "INFO".
        """
        Cli.__config_logger(log_level)
        self.__logger = logging.getLogger(__name__)

    def scan_terminals(self, target, timeout=5.0, workers=255):
        """Scan DAM terminals.

        Args:
            target (str): Target network CIDR
            timeout (float, optional): Timeout (second). Defaults to 0.5.
            workers (int, optional): Number of worker. Defaults to 50.

        Raises:
            ValueError: Argument `target` must be a str.
            ValueError: Argument `timeout` must be a float.
            ValueError: Argument `workers` must be a int.
        """
        if not isinstance(target, str):
            raise ValueError("Argument `target` must be a str.")
        if not isinstance(timeout, float):
            raise ValueError("Argument `timeout` must be a float.")
        if not isinstance(workers, int):
            raise ValueError("Argument `workers` must be a int.")

        config = NetworkConfig(timeout=timeout, max_workers=workers)

        scanner = NetworkScanner(config)
        scanner.scan_terminals(target)

    async def download_file(self, host, port, dir, file, dest):
        """Download a file from a DAM terminal.

        Args:
            host (str): DAM terminal address
            port (int): DAM terminal SFTP port
            dir (int): Directory number
            file (int): File number
            dest (str): Destination file path

        Raises:
            ValueError: Argument `host` must be a str.
            ValueError: Argument `port` must be a int.
            ValueError: Argument `dir` must be a int.
            ValueError: Argument `file` must be a int.
            ValueError: Argument `dest` must be a str.
        """
        if not isinstance(host, str):
            raise ValueError("Argument `host` must be a str.")
        if not isinstance(port, int):
            raise ValueError("Argument `port` must be a int.")
        if not isinstance(dir, int):
            raise ValueError("Argument `dir` must be a int.")
        if not isinstance(file, int):
            raise ValueError("Argument `file` must be a int.")
        if not isinstance(dest, str):
            raise ValueError("Argument `dest` must be a str.")

        sftp_config = SftpConfig(host, port)

        async with SftpClient(sftp_config) as sftp_client:
            await sftp_client.download_file(dir, file, dest)

    async def upload_file(self, host, port, src, dir, file):
        """Upload a file to a DAM terminal.

        Args:
            host (str): DAM terminal address
            port (int): DAM terminal SFTP port
            src (str): Source file path
            dir (int): Directory number
            file (int): File number

        Raises:
            ValueError: Argument `host` must be a str.
            ValueError: Argument `port` must be a int.
            ValueError: Argument `src` must be a str.
            ValueError: Argument `dir` must be a int.
            ValueError: Argument `file` must be a int.
        """
        if not isinstance(host, str):
            raise ValueError("Argument `host` must be a str.")
        if not isinstance(port, int):
            raise ValueError("Argument `port` must be a int.")
        if not isinstance(src, str):
            raise ValueError("Argument `src` must be a str.")
        if not isinstance(dir, int):
            raise ValueError("Argument `dir` must be a int.")
        if not isinstance(file, int):
            raise ValueError("Argument `file` must be a int.")

        sftp_config = SftpConfig(host, port)

        async with SftpClient(sftp_config) as sftp_client:
            await sftp_client.upload_file(src, dir, file)


def main() -> None:
    """Entry point for the dknw-tools CLI application."""
    fire.Fire(Cli)


if __name__ == "__main__":
    main()
