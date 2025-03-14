from enum import IntEnum


class MessageType(IntEnum):
    UNDEFINED = 0x0000

    # Requests
    GET_TERMINAL_TYPE_REQUEST = 0x4032

    # Responses
    GET_TERMINAL_TYPE_RESPONSE = 0x8032
