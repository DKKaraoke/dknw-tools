from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from ipaddress import IPv4Network
from logging import getLogger
from typing import Final, Iterator, TypeAlias
import socket
import threading

from tqdm import tqdm

from .messages import GetTerminalTypeRequest, GetTerminalTypeResponse

ResponseBuffer: TypeAlias = bytes
Address: TypeAlias = str
ScanResult: TypeAlias = tuple[Address, ResponseBuffer | None]

logger = getLogger(__name__)


class NetworkConstants:
    """Network-related constants"""

    DEFAULT_PORT: Final[int] = 22960
    DEFAULT_BUFFER_SIZE: Final[int] = 4096
    DEFAULT_TIMEOUT: Final[float] = 5.0
    DEFAULT_MAX_WORKERS: Final[int] = 255


class NetworkError(Exception):
    """Base exception for network operations"""

    pass


class ConnectionError(NetworkError):
    """Exception raised for connection-related errors"""

    pass


class ResponseError(NetworkError):
    """Exception raised for response-related errors"""

    pass


@dataclass(frozen=True)
class NetworkConfig:
    """Network operation configuration"""

    port: int = NetworkConstants.DEFAULT_PORT
    buffer_size: int = NetworkConstants.DEFAULT_BUFFER_SIZE
    timeout: float = NetworkConstants.DEFAULT_TIMEOUT
    max_workers: int = NetworkConstants.DEFAULT_MAX_WORKERS

    def validate(self) -> None:
        """Validate configuration parameters

        Raises:
            ValueError: If any parameter is invalid
        """
        if not 0 < self.port < 65536:
            raise ValueError(f"Invalid port number: {self.port}")
        if not 0 < self.timeout:
            raise ValueError(f"Invalid timeout: {self.timeout}")
        if not 0 < self.max_workers <= 1000:
            raise ValueError(f"Invalid number of workers: {self.max_workers}")


class ThreadLocalSocket:
    """Thread-local socket management"""

    _local = threading.local()

    @classmethod
    @contextmanager
    def get_socket(cls, timeout: float) -> Iterator[socket.socket]:
        """Get or create a thread-local socket with context management"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            yield sock
        finally:
            try:
                sock.close()
            except Exception as e:
                logger.debug(f"Error closing socket: {e}")


class NetworkScanner:
    """Network scanning functionality"""

    def __init__(self, config: NetworkConfig | None = None):
        """Initialize scanner with configuration

        Args:
            config: Network configuration, uses defaults if None
        """
        self.config = config or NetworkConfig()
        try:
            self.config.validate()
        except ValueError as e:
            raise ValueError(f"Invalid configuration: {e}")

    def send_message(self, remote_address: Address, message: bytes) -> ScanResult:
        """Send message to remote address and return response

        Args:
            remote_address: Target IP address
            message: Message to send

        Returns:
            Tuple of (address, response_buffer or None)

        Raises:
            ConnectionError: If connection fails
        """
        try:
            with ThreadLocalSocket.get_socket(self.config.timeout) as sock:
                sock.connect((remote_address, self.config.port))
                sock.send(message)
                received = sock.recv(self.config.buffer_size)
                return remote_address, received
        except Exception as e:
            logger.debug(f"Failed to communicate with {remote_address}: {e}")
            return remote_address, None

    def process_response(
        self, address: Address, response_buffer: ResponseBuffer
    ) -> str:
        """Process response buffer and return formatted output

        Args:
            address: Remote address
            response_buffer: Response buffer

        Returns:
            Formatted output string

        Raises:
            ResponseError: If response cannot be parsed
        """
        try:
            response_stream = BytesIO(response_buffer)
            response_message = GetTerminalTypeResponse.read(response_stream)

            return (
                f"{address}: "
                f"protocol_version={response_message.protocol_version} "
                f"model_id={response_message.model_id} "
                f"model_sub_id={response_message.model_sub_id} "
                f"serial={response_message.serial} "
                f"software_version={response_message.software_version} "
                f"bb_index={response_message.bb_index} "
                f"printer_version={response_message.printer_version}"
            )
        except Exception as e:
            raise ResponseError(f"Failed to parse response from {address}: {e}")

    @staticmethod
    def get_valid_addresses(target_cidr: str) -> list[Address]:
        """Get list of valid IP addresses from CIDR notation

        Args:
            target_cidr: Target network in CIDR notation

        Returns:
            List of valid IP addresses

        Raises:
            ValueError: If CIDR is invalid
        """
        try:
            network = IPv4Network(target_cidr)
            return [
                str(addr)
                for addr in network
                if not addr.is_multicast and not addr.is_reserved
            ]
        except ValueError as e:
            raise ValueError(f"Invalid CIDR notation: {e}")

    def scan_terminals(self, target_cidr: str, show_progress: bool = True) -> None:
        """Scan network for terminals and print results

        Args:
            target_cidr: Target network in CIDR notation
            show_progress: Whether to show progress bar
        """
        # Prepare request message
        request_buffer = GetTerminalTypeRequest().to_bytes()

        # Get valid addresses
        try:
            valid_addresses = self.get_valid_addresses(target_cidr)
        except ValueError as e:
            logger.error(f"Failed to parse target network: {e}")
            return

        logger.info(
            f"Scanning {len(valid_addresses)} addresses "
            f"with {self.config.max_workers} workers "
            f"(timeout: {self.config.timeout}s)"
        )

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all tasks
            future_to_addr = {
                executor.submit(self.send_message, addr, request_buffer): addr
                for addr in valid_addresses
            }

            # Process responses as they complete
            iterator = as_completed(future_to_addr)
            if show_progress:
                iterator = tqdm(
                    iterator, total=len(valid_addresses), desc="Scanning", unit="addr"
                )

            for future in iterator:
                addr = future_to_addr[future]
                try:
                    address, response = future.result()
                    if response:
                        tqdm.write(self.process_response(address, response))
                except Exception as e:
                    logger.error(f"Error processing {addr}: {e}")
