from enum import IntEnum


class FileOperationType(IntEnum):
    IDLE = 0x00
    READ = 0x01
    REPLACE = 0x02
    APPEND = 0x03
    DELETE = 0x04
