import socket      # Module for TCP/IP networking (server/client sockets)
import os          # Module for working with files, folders and paths
import mimetypes   # Detect MIME type from file extension

# MIME type tells the client what kind of file is being transferred.
# Examples:
#   text/plain
#   application/json
#   image/png
#   application/octet-stream

HOST = "0.0.0.0"      # Listen on all available network interfaces
PORT = 8000           # TCP port used by the OTA server

# Absolute path to the folder where server.py is running , "." - THIS folder
ROOT_DIR = os.path.abspath(".")


# Build an HTTP response and send it to the client.
#
# client        -> connected socket
# status        -> "200 OK", "404 Not Found", ...
# content_type  -> MIME type
# data          -> file contents (bytes)
def send_response(client, status, content_type, data):

    # Build HTTP response header
    header = (
        f"HTTP/1.1 {status}\r\n"
        f"Content-Length: {len(data)}\r\n"
        f"Content-Type: {content_type}\r\n"
        "Connection: close\r\n\r\n"
    )

    # Send HTTP header
    client.send(header.encode())

    # Send file contents
    client.send(data)


# Create TCP socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind socket to HOST:PORT
server.bind((HOST, PORT))

# Start listening for incoming connections
# Maximum number of pending connections = 5
server.listen(5)

print("=" * 50)
print("OTA HTTP Server")
print("Root:", ROOT_DIR)
print("Listening:", PORT)
print("=" * 50)

# Server never stops
while True:

    # Wait until a client connects
    client, addr = server.accept()

    # Print client's IP address and TCP port
    print(f"\nClient: {addr}")

    # Receive HTTP request
    # Maximum receive buffer = 2048 bytes
    request = client.recv(2048).decode(errors="ignore")

    # Client disconnected without sending anything
    if not request:
        client.close()
        continue

    # Extract first line of HTTP request
    # Example:
    # GET /version.json HTTP/1.1
    first_line = request.split("\r\n")[0]

    print(first_line)

    try:

        # Split HTTP request line
        #
        # method -> GET
        # path   -> /version.json
        # _      -> HTTP/1.1
        method, path, _ = first_line.split()

    except ValueError:

        # Invalid HTTP request
        client.close()
        continue

    # If browser requests "/"
    # automatically return version.json
    if path == "/":
        path = "/version.json"

    # Replace URL separator with OS separator
    # Linux:
    #   /
    #
    # Windows:
    #   \
    path = path.replace("/", os.sep)

    # Build full path to requested file
    filename = os.path.join(ROOT_DIR, path.lstrip(os.sep))

    print("File:", filename)

    # Check if requested file exists
    if os.path.isfile(filename):

        # Read entire file into memory
        with open(filename, "rb") as f:
            data = f.read()

        # Detect MIME type automatically
        content_type = mimetypes.guess_type(filename)[0]

        # Unknown extension
        if content_type is None:
            content_type = "application/octet-stream"

        # Send HTTP response
        send_response(
            client,
            "200 OK",
            content_type,
            data
        )

        print("200 OK")

    else:

        # File does not exist
        send_response(
            client,
            "404 Not Found",
            "text/plain",
            b"File not found"
        )

        print("404")

    # Close TCP connection
    client.close()