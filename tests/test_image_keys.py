import struct
import unittest

from wechat.image_keys import ImageKeys


class ImageKeysTest(unittest.TestCase):
    def fixture(self, account="test"):
        image = bytearray(512)
        image[384:397] = b"global_config"
        struct.pack_into("<Q", image, 400, 13)
        header = account.encode().ljust(16, b"\0") + struct.pack(
            "<QQ", len(account), 15
        )
        memory = {
            0x10000 + 144: struct.pack("<Q", 0x30000),
            0x30000 + 0x30: struct.pack("<Q", 0x40000),
            0x40000 + 0x48: header,
            0x40000 + 0x40: struct.pack("<I", 12345),
        }
        return bytes(image), lambda address, size: memory.get(address)

    def test_configuration_requires_account_and_ciphertext_verification(self) -> None:
        image, read = self.fixture()
        result = ImageKeys.locate(
            image, 0x10000, read, "test", lambda number: number == 12345
        )
        self.assertEqual(result, 12345)
        with self.assertRaises(ValueError):
            ImageKeys.locate(image, 0x10000, read, "test", lambda number: False)

    def test_configuration_from_another_account_is_rejected(self) -> None:
        image, read = self.fixture("other")
        with self.assertRaises(ValueError):
            ImageKeys.locate(image, 0x10000, read, "test", lambda number: True)

    def test_unbounded_string_capacities_are_rejected(self) -> None:
        header = b"test".ljust(16, b"\0") + struct.pack("<QQ", 4, 2**32)
        self.assertFalse(
            ImageKeys.matches_string(lambda address, size: header, 1, "test")
        )
