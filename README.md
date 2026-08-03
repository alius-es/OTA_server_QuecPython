===============================================================================
QuecPython OTA Demo
===============================================================================

Description
-------------------------------------------------------------------------------

This project implements a simple OTA (Over-The-Air) update system for
QuecPython modules.

The project consists of two independent parts:

    module/
        Source code running on the Quectel module.

    OTA_Server/
        HTTP server that provides OTA files to the module.


===============================================================================
Project structure
===============================================================================

QuecPython/

│
├── module/
│   ├── app.py
│   ├── main.py
│   ├── ota.py
│   ├── config.py
│   └── ...
│
├── OTA_Server/
│   ├── files/
│   ├── server.py
│   ├── generate_manifest.py
│   ├── project.json
│   ├── manifest.json
│   ├── cloudflared.exe
│   └── ...
│
└── README.txt


===============================================================================
module/
===============================================================================

Contains the application that runs on the Quectel module.

Main files:

main.py
    Application entry point.

app.py
    Main application.

ota.py
    OTA update mechanism.

config.py
    OTA configuration.

Only these files are copied to the module (/usr).


===============================================================================
OTA_Server/
===============================================================================

Contains everything required to publish OTA updates.

files/
    Files available for downloading by the module.

server.py
    Simple HTTP server.

generate_manifest.py
    Automatically generates manifest.json.

project.json
    Project information.
    Edit this file before creating a new release.

manifest.json
    Automatically generated.
    DO NOT edit manually.

cloudflared.exe
    Creates a public HTTPS tunnel to the local OTA server.


===============================================================================
Creating a new OTA release
===============================================================================

1. Modify application files inside:

       module/

2. Copy updated files into:

       OTA_Server/files/

3. Edit:

       OTA_Server/project.json

   Update at least:

       version
       description

4. Generate a new manifest:

       python generate_manifest.py

5. Start OTA server:

       python server.py

6. (Optional) Start Cloudflare Tunnel:

       cloudflared.exe tunnel --url http://localhost:8000

7. Copy the HTTPS address printed by Cloudflare.

8. Update:

       module/config.py

   Example:

       OTA_SERVER = "https://xxxxxxxx.trycloudflare.com"

9. Upload module files to the device.

10. Restart the device or call OTA update.


===============================================================================
How OTA works
===============================================================================

1.
Module downloads:

    manifest.json

2.
Manifest version is compared with the local version.

3.
If versions differ:

    download changed files

4.
Downloaded files are verified.

5.
Old files are replaced.

6.
Local manifest.json is updated.

7.
Application continues with the new version.


===============================================================================
Important notes
===============================================================================

Do NOT edit:

    OTA_Server/manifest.json

It is generated automatically.

Always edit:

    OTA_Server/project.json

Never place files directly into OTA_Server.

Only place downloadable files into:

    OTA_Server/files/


config.py
-------------------------------------------------------------------------------

config.py contains runtime configuration.

Example:

    OTA_SERVER

Whenever a new Cloudflare Tunnel address is generated,
update OTA_SERVER accordingly.


===============================================================================
Cloudflare Tunnel
===============================================================================

Cloudflare Tunnel provides temporary public HTTPS access
to the local OTA server.

Workflow:

    server.py
        ↓
    localhost:8000
        ↓
    cloudflared.exe
        ↓
    https://xxxxxxxx.trycloudflare.com
        ↓
    Quectel module

Each new tunnel generates a different URL.

After creating a new tunnel:

    update OTA_SERVER in config.py.


===============================================================================
Notes
===============================================================================

This repository contains only the OTA mechanism.

Application-specific logic should remain inside module/.

OTA_Server should only contain files required to distribute updates.