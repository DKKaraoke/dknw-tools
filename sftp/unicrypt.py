import unittest
from unittest.mock import patch

from .bit_operations import count_set_bits, reverse_bits, rotate_bits
from .unicrypt_sbox import UNICRYPT_SBOX


class Unicrypt:
    def __init__(self) -> None:
        self.sbox_index: int = 0

    def get_sbox(self) -> int:
        sbox = UNICRYPT_SBOX[self.sbox_index]
        self.sbox_index = (self.sbox_index + 1) % 0x100
        return sbox

    def __round(self, plaintext: bytearray) -> bytearray:
        temp = plaintext.copy()

        # Step 1: XOR with the table
        for i in range(len(temp)):
            temp[i] ^= self.get_sbox()

        # Step 2: Rotate bits
        n_set_bits = count_set_bits(temp)
        temp = rotate_bits(temp, n_set_bits)

        # Step 3: XOR with the table
        for i in range(len(temp)):
            temp[i] ^= self.get_sbox()

        # Step 4: Reverse bits in byte
        temp = reverse_bits(temp)

        return temp

    def encrypt(self, plaintext: bytes):
        self.sbox_index = count_set_bits(plaintext) % 0x100

        temp = bytearray(plaintext)

        for _ in range(0x11):
            temp = self.__round(temp)

        return bytes(temp)


class TestUnicrypt(unittest.TestCase):
    def setUp(self):
        """Set up test cases"""
        self.unicrypt = Unicrypt()

    def test_init(self):
        """Test initialization"""
        self.assertEqual(self.unicrypt.sbox_index, 0)

    def test_get_sbox(self):
        """Test get_sbox method"""
        # First S-BOX should be UNICRYPT_SBOX[0]
        first_sbox = self.unicrypt.get_sbox()
        self.assertEqual(self.unicrypt.sbox_index, 1)

        # Test S-BOX rotation
        for i in range(0xFF):
            self.unicrypt.get_sbox()
        next_sbox = self.unicrypt.get_sbox()
        self.assertEqual(self.unicrypt.sbox_index, 1)

    def test_encrypt_empty_input(self):
        """Test encryption with empty input"""
        empty_input = b""
        result = self.unicrypt.encrypt(empty_input)
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 0)

    def test_encrypt_single_byte(self):
        """Test encryption with single byte input"""
        single_byte = b"\x00"
        result = self.unicrypt.encrypt(single_byte)
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 1)
        self.assertNotEqual(result, single_byte)  # Encryption should change the input

    def test_encrypt_multiple_bytes(self):
        """Test encryption with multiple bytes"""
        test_input = b"Hello, World!"
        result = self.unicrypt.encrypt(test_input)
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), len(test_input))
        self.assertNotEqual(result, test_input)  # Encryption should change the input

    def test_encrypt_idempotent(self):
        """Test that encryption with same input produces same output"""
        test_input = b"Test message"
        result1 = self.unicrypt.encrypt(test_input)
        self.unicrypt = Unicrypt()  # Reset the instance
        result2 = self.unicrypt.encrypt(test_input)
        self.assertEqual(result1, result2)

    def test_round_transformation(self):
        """Test internal round transformation"""
        test_input = bytearray(b"Test")
        with patch.object(Unicrypt, "get_sbox", return_value=0x42):
            result = self.unicrypt._Unicrypt__round(test_input)
            self.assertIsInstance(result, bytearray)
            self.assertEqual(len(result), len(test_input))
            self.assertNotEqual(result, test_input)  # Round should modify the input

    def test_sbox_index_initialization(self):
        """Test sbox_index initialization in encrypt method"""
        test_input = b"Test"

        # Get the initial sbox_index value after initialization
        initial_sbox_index = count_set_bits(test_input) % 0x100

        # Create a new instance and start encryption
        self.unicrypt = Unicrypt()
        # Mock the round method to prevent sbox_index changes during rounds
        with patch.object(
            Unicrypt, "_Unicrypt__round", return_value=bytearray(test_input)
        ):
            self.unicrypt.encrypt(test_input)
            self.assertEqual(self.unicrypt.sbox_index, initial_sbox_index)

    def test_encrypt_preserves_length(self):
        """Test that encryption preserves input length"""
        test_cases = [b"", b"A", b"Hello", b"A" * 1000]
        for test_input in test_cases:
            with self.subTest(input_length=len(test_input)):
                result = self.unicrypt.encrypt(test_input)
                self.assertEqual(len(result), len(test_input))

    def test_encrypt_different_inputs(self):
        """Test that different inputs produce different outputs"""
        input1 = b"Message 1"
        input2 = b"Message 2"
        result1 = self.unicrypt.encrypt(input1)
        self.unicrypt = Unicrypt()  # Reset the instance
        result2 = self.unicrypt.encrypt(input2)
        self.assertNotEqual(result1, result2)
