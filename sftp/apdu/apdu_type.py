from enum import IntEnum


class ApduType(IntEnum):
    A_CONNECT = 0x0000
    A_ACCEPT = 0x0001
    A_REJECT = 0x0002
    A_RELEASE = 0x0003
    A_SYNC = 0x0004
    A_AUTHENT = 0x0005
    A_AUTHENT_RSP = 0x0006

    F_START = 0x0100
    F_READY = 0x0101
    F_FINAL = 0x0102
    F_END = 0x0103
    F_DATA = 0x0104
    F_CANCEL = 0x0105
    F_ALIVE = 0x0106
    F_PURGE = 0x0107
    F_PURGE_RSP = 0x0108
    F_SKIP = 0x0109
    F_SKIP_RSP = 0x010A

    NONE = 0xFFFF
