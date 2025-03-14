from dataclasses import dataclass
from io import BufferedReader, BytesIO
from typing import Self

from . import ApduType, ApduBase, ApduItemType, ApduItem


@dataclass
class GenericApdu(ApduBase):
    """Generic APDU"""

    type: ApduType
    items: list[ApduItem]

    @classmethod
    def read(cls, stream: BufferedReader) -> Self:
        """Read Generic APDU"""
        apdu_type, payload = ApduBase._read_common(stream)
        if apdu_type == ApduType.F_DATA:
            raise ValueError("Invalid APDU Type: F_DATA")

        items = []
        payload_stream = BytesIO(payload)

        while payload_stream.tell() < len(payload):
            try:
                item = ApduItem.read(payload_stream)
                items.append(item)
            except ValueError as e:
                raise ValueError(f"Failed to read APDU item: {e}")

        return cls(apdu_type, items)

    def _apdu_type(self) -> ApduType:
        return self.type

    def _payload_buffer(self) -> bytes:
        buffer = BytesIO()
        for item in self.items:
            item.write(buffer)
        buffer.seek(0)
        return buffer.read()

    def get_item(self, item_type: ApduItemType) -> bytes | None:
        """Get item data by type"""
        for item in self.items:
            if item.type == item_type:
                return item.data
        return None

    def set_item(self, item_type: ApduItemType, data: bytes) -> None:
        """Set item data by type"""
        for item in self.items:
            if item.type == item_type:
                item.data = data
                return
        self.items.append(ApduItem(item_type, data))
