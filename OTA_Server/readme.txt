.\cloudflared.exe tunnel --url http://localhost:8000
in powershell and use address after 
"Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):"

folder 'files' should only have files for updating

manifest.json should not be changed manually, it is generated automatically
by build.py

to change manifest.json manually, use project.json before executing generate_manifest.py