#==============================================================================
# File: server.py
#
# Description:
#     Simple HTTP server for QuecPython OTA.
#
#     Supported operations:
#
#         GET  /manifest.json
#         GET  /files/...
#         POST /ota/report
#
#==============================================================================


#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import socket
import os
import mimetypes
import json
from datetime import datetime
from urllib.parse import unquote


#------------------------------------------------------------------------------
# Server configuration
#------------------------------------------------------------------------------

HOST = "0.0.0.0"
PORT = 8000

ROOT_DIR = os.path.abspath(".")

REPORTS_DIR = os.path.join(
    ROOT_DIR,
    "reports"
)

OTA_REPORT_PATH = "/ota/report"

MAX_REPORT_SIZE = 4096

FILE_CHUNK_SIZE = 4096

CLIENT_TIMEOUT = 10


#------------------------------------------------------------------------------
# Logging
#------------------------------------------------------------------------------

LOG_SEPARATOR = "-" * 70


def get_timestamp():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def log(message):

    print(
        "[{}] {}".format(
            get_timestamp(),
            message
        )
    )


#------------------------------------------------------------------------------
# HTTP response
#------------------------------------------------------------------------------

def send_response(
    client,
    status,
    content_type,
    data
):

    header = (
        "HTTP/1.1 {}\r\n"
        "Content-Length: {}\r\n"
        "Content-Type: {}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).format(
        status,
        len(data),
        content_type
    )

    client.sendall(
        header.encode("utf-8")
    )

    client.sendall(data)


#------------------------------------------------------------------------------
# JSON response
#------------------------------------------------------------------------------

def send_json_response(
    client,
    status,
    data
):

    body = json.dumps(data).encode(
        "utf-8"
    )

    send_response(
        client,
        status,
        "application/json",
        body
    )


#------------------------------------------------------------------------------
# File transfer error
#------------------------------------------------------------------------------

class FileTransferError(Exception):

    def __init__(
        self,
        message,
        bytes_sent
    ):

        super().__init__(message)

        self.bytes_sent = bytes_sent


#------------------------------------------------------------------------------
# Send file
#------------------------------------------------------------------------------

def send_file(
    client,
    filename,
    content_type
):

    file_size = os.path.getsize(
        filename
    )

    header = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Length: {}\r\n"
        "Content-Type: {}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).format(
        file_size,
        content_type
    )

    total_sent = 0

    try:

        client.sendall(
            header.encode("utf-8")
        )

        with open(
            filename,
            "rb"
        ) as file:

            while True:

                chunk = file.read(
                    FILE_CHUNK_SIZE
                )

                if not chunk:
                    break

                client.sendall(
                    chunk
                )

                total_sent += len(chunk)

    except Exception as error:

        raise FileTransferError(
            str(error),
            total_sent
        )

    return (
        file_size,
        total_sent
    )


#------------------------------------------------------------------------------
# Format size
#------------------------------------------------------------------------------

def format_size(size):

    if size < 1024:

        return "{} B".format(
            size
        )

    if size < 1024 * 1024:

        return "{:.2f} KB".format(
            size / 1024
        )

    return "{:.2f} MB".format(
        size / (1024 * 1024)
    )


#------------------------------------------------------------------------------
# Read HTTP request
#------------------------------------------------------------------------------

def read_request(client):

    data = b""

    while b"\r\n\r\n" not in data:

        chunk = client.recv(4096)

        if not chunk:
            break

        data += chunk

        if len(data) > 8192:

            raise ValueError(
                "HTTP request headers are too large"
            )

    separator = b"\r\n\r\n"

    header_end = data.find(
        separator
    )

    if header_end < 0:

        raise ValueError(
            "Invalid HTTP request"
        )

    header_data = data[
        :header_end
    ]

    body = data[
        header_end + len(separator):
    ]

    lines = header_data.decode(
        "utf-8",
        errors="ignore"
    ).split("\r\n")

    if not lines:

        raise ValueError(
            "Missing HTTP request line"
        )

    request_line = lines[0]

    parts = request_line.split()

    if len(parts) != 3:

        raise ValueError(
            "Invalid HTTP request line"
        )

    method = parts[0]

    path = parts[1]

    http_version = parts[2]

    headers = {}

    for line in lines[1:]:

        if ":" not in line:
            continue

        name, value = line.split(
            ":",
            1
        )

        headers[
            name.strip().lower()
        ] = value.strip()

    content_length = headers.get(
        "content-length",
        "0"
    )

    try:

        content_length = int(
            content_length
        )

    except ValueError:

        raise ValueError(
            "Invalid Content-Length"
        )

    if content_length < 0:

        raise ValueError(
            "Invalid Content-Length"
        )

    if content_length > MAX_REPORT_SIZE:

        raise ValueError(
            "Request body is too large"
        )

    while len(body) < content_length:

        chunk = client.recv(4096)

        if not chunk:
            break

        body += chunk

    if len(body) < content_length:

        raise ValueError(
            "Incomplete request body"
        )

    body = body[
        :content_length
    ]

    return (
        method,
        path,
        http_version,
        headers,
        body
    )


#------------------------------------------------------------------------------
# Validate semantic version
#------------------------------------------------------------------------------

def validate_version(version):

    if not isinstance(
        version,
        str
    ):

        return False

    parts = version.split(".")

    if len(parts) != 3:

        return False

    try:

        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])

    except Exception:

        return False

    if (
        major < 0
        or minor < 0
        or patch < 0
    ):

        return False

    return True


#------------------------------------------------------------------------------
# Validate relative application path
#------------------------------------------------------------------------------

def is_safe_relative_path(path):

    if not isinstance(
        path,
        str
    ):

        return False

    if not path:

        return False

    if path.startswith("/"):

        return False

    if path.startswith("\\"):

        return False

    if "\\" in path:

        return False

    parts = path.split("/")

    for part in parts:

        if part in (
            "",
            ".",
            ".."
        ):

            return False

    return True


#------------------------------------------------------------------------------
# Validate OTA report
#------------------------------------------------------------------------------

def validate_ota_report(report):

    if not isinstance(
        report,
        dict
    ):

        return (
            False,
            "Report must be an object"
        )

    required_fields = {
        "imei",
        "operation",
        "state",
        "target_version",
        "obsolete_files",
        "report_sent"
    }

    if set(report.keys()) != required_fields:

        return (
            False,
            "Invalid OTA report fields"
        )

    imei = report["imei"]

    if (
        not isinstance(imei, str)
        or len(imei) != 15
        or not imei.isdigit()
    ):

        return (
            False,
            "Invalid IMEI"
        )

    operation = report["operation"]

    if operation not in (
        "update",
        "force_update"
    ):

        return (
            False,
            "Invalid operation"
        )

    state = report["state"]

    if state != "success":

        return (
            False,
            "Invalid OTA state"
        )

    target_version = report[
        "target_version"
    ]

    if not validate_version(
        target_version
    ):

        return (
            False,
            "Invalid target version"
        )

    obsolete_files = report[
        "obsolete_files"
    ]

    if not isinstance(
        obsolete_files,
        list
    ):

        return (
            False,
            "Invalid obsolete_files"
        )

    seen = set()

    for filename in obsolete_files:

        if not is_safe_relative_path(
            filename
        ):

            return (
                False,
                "Invalid obsolete file path"
            )

        if filename in seen:

            return (
                False,
                "Duplicate obsolete file"
            )

        seen.add(filename)

    if (
        operation == "force_update"
        and obsolete_files
    ):

        return (
            False,
            "force_update must not contain obsolete files"
        )

    report_sent = report[
        "report_sent"
    ]

    if report_sent is not False:

        return (
            False,
            "report_sent must be false"
        )

    return (
        True,
        None
    )


#------------------------------------------------------------------------------
# Save OTA report
#------------------------------------------------------------------------------

def save_ota_report(report):

    if not os.path.isdir(
        REPORTS_DIR
    ):

        os.makedirs(
            REPORTS_DIR
        )

    imei = report["imei"]

    filename = os.path.join(
        REPORTS_DIR,
        imei + ".json"
    )

    temp_filename = (
        filename + ".tmp"
    )

    data = json.dumps(
        report,
        indent=4
    )

    with open(
        temp_filename,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(data)

        file.flush()

        try:

            os.fsync(
                file.fileno()
            )

        except Exception:

            pass

    os.replace(
        temp_filename,
        filename
    )

    return filename


#------------------------------------------------------------------------------
# Handle OTA report
#------------------------------------------------------------------------------

def handle_ota_report(
    client,
    body
):

    try:

        if not body:

            raise ValueError(
                "Empty request body"
            )

        report = json.loads(
            body.decode("utf-8")
        )

    except Exception as error:

        log(
            "OTA REPORT REJECTED | {}".format(
                error
            )
        )

        send_json_response(
            client,
            "400 Bad Request",
            {
                "ack": False
            }
        )

        return "400 Bad Request"

    valid, error = validate_ota_report(
        report
    )

    if not valid:

        log(
            "OTA REPORT REJECTED | {}".format(
                error
            )
        )

        send_json_response(
            client,
            "400 Bad Request",
            {
                "ack": False
            }
        )

        return "400 Bad Request"

    print()

    log("OTA REPORT")

    print(
        "  IMEI:      {}".format(
            report["imei"]
        )
    )

    print(
        "  Operation: {}".format(
            report["operation"]
        )
    )

    print(
        "  State:     {}".format(
            report["state"]
        )
    )

    print(
        "  Version:   {}".format(
            report["target_version"]
        )
    )

    try:

        filename = save_ota_report(
            report
        )

    except Exception as error:

        log(
            "OTA REPORT ERROR | {}".format(
                error
            )
        )

        send_json_response(
            client,
            "500 Internal Server Error",
            {
                "ack": False
            }
        )

        return "500 Internal Server Error"

    log(
        "OTA REPORT SAVED | {}".format(
            filename
        )
    )

    send_json_response(
        client,
        "200 OK",
        {
            "ack": True
        }
    )

    log(
        "200 OK | ACK SENT"
    )

    return "200 OK"


#------------------------------------------------------------------------------
# Build safe file path
#------------------------------------------------------------------------------

def get_file_path(url_path):

    url_path = url_path.split(
        "?",
        1
    )[0]

    url_path = unquote(
        url_path
    )

    relative_path = url_path.lstrip(
        "/\\"
    )

    relative_path = relative_path.replace(
        "/",
        os.sep
    )

    filename = os.path.abspath(
        os.path.join(
            ROOT_DIR,
            relative_path
        )
    )

    root = os.path.abspath(
        ROOT_DIR
    )

    try:

        if os.path.commonpath(
            [root, filename]
        ) != root:

            return None

    except Exception:

        return None

    return filename


#------------------------------------------------------------------------------
# Create TCP socket
#------------------------------------------------------------------------------

server = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

server.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

server.bind(
    (
        HOST,
        PORT
    )
)

server.listen(5)


#------------------------------------------------------------------------------
# Server information
#------------------------------------------------------------------------------

print("=" * 70)
print("QuecPython OTA HTTP Server")
print("=" * 70)
print(
    "Root:      {}".format(
        ROOT_DIR
    )
)
print(
    "Reports:   {}".format(
        REPORTS_DIR
    )
)
print(
    "Address:   {}:{}".format(
        HOST,
        PORT
    )
)
print(
    "Chunk:     {} bytes".format(
        FILE_CHUNK_SIZE
    )
)
print(
    "Timeout:   {} seconds".format(
        CLIENT_TIMEOUT
    )
)
print("=" * 70)


#------------------------------------------------------------------------------
# Main server loop
#------------------------------------------------------------------------------

while True:

    client = None

    client_ip = "unknown"

    client_port = 0

    try:

        client, addr = server.accept()

        client_ip = addr[0]

        client_port = addr[1]

        print()
        print(LOG_SEPARATOR)

        log(
            "CONNECT  {}:{}".format(
                client_ip,
                client_port
            )
        )

        client.settimeout(
            CLIENT_TIMEOUT
        )

        (
            method,
            path,
            http_version,
            headers,
            body
        ) = read_request(client)

        log(
            "{} {} {}".format(
                method,
                path,
                http_version
            )
        )

        status = "Unknown"

        #----------------------------------------------------------------------
        # OTA report
        #----------------------------------------------------------------------

        if (
            method == "POST"
            and path.split("?", 1)[0]
            == OTA_REPORT_PATH
        ):

            status = handle_ota_report(
                client,
                body
            )

        #----------------------------------------------------------------------
        # File download
        #----------------------------------------------------------------------

        elif method == "GET":

            request_path = path

            if request_path == "/":

                request_path = (
                    "/manifest.json"
                )

            filename = get_file_path(
                request_path
            )

            if filename is None:

                status = "403 Forbidden"

                send_response(
                    client,
                    status,
                    "text/plain",
                    b"Forbidden"
                )

                log(
                    "403 Forbidden"
                )

            elif os.path.isfile(
                filename
            ):

                content_type = (
                    mimetypes.guess_type(
                        filename
                    )[0]
                )

                if content_type is None:

                    content_type = (
                        "application/octet-stream"
                    )

                file_size = os.path.getsize(
                    filename
                )

                try:

                    (
                        expected_size,
                        bytes_sent
                    ) = send_file(
                        client,
                        filename,
                        content_type
                    )

                    # send_file() returns only after the complete
                    # file has been passed to sendall().
                    if bytes_sent == expected_size:

                        status = "200 OK"

                        log(
                            "200 OK   {}".format(
                                format_size(
                                    bytes_sent
                                )
                            )
                        )

                except FileTransferError as error:

                    status = "Client disconnected"

                    log(
                        "TRANSFER FAILED   {} / {}".format(
                            format_size(
                                error.bytes_sent
                            ),
                            format_size(
                                file_size
                            )
                        )
                    )

                    log(
                        "DETAIL             {}".format(
                            error
                        )
                    )

            else:

                status = "404 Not Found"

                send_response(
                    client,
                    status,
                    "text/plain",
                    b"File not found"
                )

                log(
                    "404 Not Found"
                )

        #----------------------------------------------------------------------
        # Unsupported method
        #----------------------------------------------------------------------

        else:

            status = (
                "405 Method Not Allowed"
            )

            send_response(
                client,
                status,
                "text/plain",
                b"Method not allowed"
            )

            log(
                "405 Method Not Allowed"
            )

    except socket.timeout:

        status = "408 Request Timeout"

        log(
            "408 Request Timeout"
        )

    except (
        BrokenPipeError,
        ConnectionResetError
    ) as error:

        status = "Client disconnected"

        log(
            "ERROR    client disconnected | {}".format(
                error
            )
        )

    except Exception as error:

        status = "400 Bad Request"

        log(
            "ERROR    {}".format(
                error
            )
        )

        if client is not None:

            try:

                send_response(
                    client,
                    status,
                    "text/plain",
                    b"Bad request"
                )

            except Exception:

                pass

    finally:

        if client is not None:

            try:

                client.close()

            except Exception:

                pass

        print(LOG_SEPARATOR)
