from . import MessageBase, MessageType


class GetTerminalTypeRequest(MessageBase):
    def _message_type(self) -> MessageType:
        return MessageType.GET_TERMINAL_TYPE_REQUEST

    def _payload_buffer(self) -> bytes:
        return b""
