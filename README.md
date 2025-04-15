# dknw-tools

Network tools for DAM Karaoke terminals

## Summary

This tool allows you to scan for DAM terminals on your network, and transfer files to and from these terminals using SFTP.

## Usage

### scan-terminals

Scan for DAM terminals on your network

```
$ dknw-tools scan_terminals --help
NAME
    dknw-tools scan_terminals - Scan DAM terminals.

SYNOPSIS
    dknw-tools scan_terminals TARGET <flags>

DESCRIPTION
    Scan DAM terminals.

POSITIONAL ARGUMENTS
    TARGET
        Target network CIDR

FLAGS
    -t, --timeout=TIMEOUT
        Default: 5.0
        Timeout (second). Defaults to 0.5.
    -w, --workers=WORKERS
        Default: 255
        Number of worker. Defaults to 50.

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

Example:

```bash
dknw-tools scan_terminals 192.168.1.0/24 --timeout=2.0 --workers=100
```

### search-dirs

Search directories in a DAM terminal.

```
$ dknw-tools search-dirs --help

NAME
    dknw-tools search-dirs - Search directories in a DAM terminal.

SYNOPSIS
    dknw-tools - search-dirs HOST PORT <flags>

DESCRIPTION
    Search directories in a DAM terminal.

POSITIONAL ARGUMENTS
    HOST
        Type: str
        DAM terminal address
    PORT
        Type: int
        DAM terminal port (main port for SFTP, data port for DS2FTP if data_port not specified)

FLAGS
    -p, --protocol=PROTOCOL
        Type: str
        Default: 'sftp'
        Protocol type ("sftp" or "ds2ftp"). Defaults to "sftp".
    -c, --ctrl_port=CTRL_PORT
        Type: Optional[Optional]
        Default: None
        Control port for DS2FTP (optional, default: port+1)
    --data_port=DATA_PORT
        Type: Optional[Optional]
        Default: None
        Data port for DS2FTP (optional, default: port)
    --dest=DEST
        Type: Optional[str | None]
        Default: None
        Destination file path. If provided, found files will be downloaded.

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

Example:

```bash
dknw-tools - search-dirs 192.168.1.100 0x59C0 --protocol=DS2FTP --dest=./downloads/
```

### download-file

Download a file from a DAM terminal

```
$ dknw-tools download-file --help

NAME
    dknw-tools download-file - Download a file from a DAM terminal.

SYNOPSIS
    dknw-tools - download-file HOST PORT DIR FILE DEST <flags>

DESCRIPTION
    Download a file from a DAM terminal.

POSITIONAL ARGUMENTS
    HOST
        Type: str
        DAM terminal address
    PORT
        Type: int
        DAM terminal port (main port for SFTP, data port for DS2FTP if data_port not specified)
    DIR
        Type: int
        Directory number
    FILE
        Type: int
        File number
    DEST
        Type: str
        Destination file path

FLAGS
    -p, --protocol=PROTOCOL
        Type: str
        Default: 'sftp'
        Protocol type ("sftp" or "ds2ftp"). Defaults to "sftp".
    -c, --ctrl_port=CTRL_PORT
        Type: Optional[Optional]
        Default: None
        Control port for DS2FTP (optional, default: port+1)
    -d, --data_port=DATA_PORT
        Type: Optional[Optional]
        Default: None
        Data port for DS2FTP (optional, default: port)

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

Example:

```bash
dknw-tools download_file 192.168.1.100 0x4200 1006 123456 ./1006.123456
```

### upload-file

Upload a file to a DAM terminal

```
$ dknw-tools upload-file --help
INFO: Showing help with the command 'dknw-tools - upload-file -- --help'.

NAME
    dknw-tools upload-file - Upload a file to a DAM terminal.

SYNOPSIS
    dknw-tools - upload-file HOST PORT SRC DIR FILE <flags>

DESCRIPTION
    Upload a file to a DAM terminal.

POSITIONAL ARGUMENTS
    HOST
        Type: str
        DAM terminal address
    PORT
        Type: int
        DAM terminal port (main port for SFTP, data port for DS2FTP if data_port not specified)
    SRC
        Type: str
        Source file path
    DIR
        Type: int
        Directory number
    FILE
        Type: int
        File number

FLAGS
    -p, --protocol=PROTOCOL
        Type: str
        Default: 'sftp'
        Protocol type ("sftp" or "ds2ftp"). Defaults to "sftp".
    -c, --ctrl_port=CTRL_PORT
        Type: Optional[Optional]
        Default: None
        Control port for DS2FTP (optional, default: port+1)
    -d, --data_port=DATA_PORT
        Type: Optional[Optional]
        Default: None
        Data port for DS2FTP (optional, default: port)

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

Example:

```bash
dknw-tools upload_file 192.168.1.100 0x4200 ./1006.123456 1006 123456
```

## List of verified DAM Karaoke terminals

- DAM-XG5000[G,R] (LIVE DAM [(GOLD EDITION|RED TUNE)])
- DAM-XG7000[Ⅱ] (LIVE DAM STADIUM [STAGE])
- DAM-XG8000[R] (LIVE DAM Ai[R])
- DAM-XG9000 (LIVE DAM WAO!)

## Authors

- soltia48

## License

[MIT](https://opensource.org/licenses/MIT)

Copyright (c) 2025 soltia48
