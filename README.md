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
    dknw-tools search-dirs HOST PORT <flags>

DESCRIPTION
    Search directories in a DAM terminal.

POSITIONAL ARGUMENTS
    HOST
        Type: str
        DAM terminal address
    PORT
        Type: int
        DAM terminal SFTP port

FLAGS
    -d, --dest=DEST
        Type: Optional[str | None]
        Default: None
        Destination file path. If provided, found files will be downloaded.

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

Example:

```bash
dknw-tools search_dirs 192.168.1.100 22 ./downloads/
```

### download-file

Download a file from a DAM terminal

```
$ dknw-tools download_file --help
NAME
    dknw-tools download_file - Download a file from a DAM terminal.

SYNOPSIS
    dknw-tools download_file HOST PORT DIR FILE DEST

DESCRIPTION
    Download a file from a DAM terminal.

POSITIONAL ARGUMENTS
    HOST
        DAM terminal address
    PORT
        DAM terminal SFTP port
    DIR
        Directory number
    FILE
        File number
    DEST
        Destination file path

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

Example:

```bash
dknw-tools download_file 192.168.1.100 22 1006 123456 ./1006.123456
```

### upload-file

Upload a file to a DAM terminal

```
$ dknw-tools upload_file --help
NAME
    dknw-tools upload_file - Upload a file to a DAM terminal.

SYNOPSIS
    dknw-tools upload_file HOST PORT SRC DIR FILE

DESCRIPTION
    Upload a file to a DAM terminal.

POSITIONAL ARGUMENTS
    HOST
        DAM terminal address
    PORT
        DAM terminal SFTP port
    SRC
        Source file path
    DIR-
        Directory number
    FILE
        File number

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

Example:

```bash
dknw-tools upload_file 192.168.1.100 22 ./1006.123456 1006 123456
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
