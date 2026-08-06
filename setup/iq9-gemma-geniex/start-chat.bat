@echo off
rem QNet: opens the SSH tunnel to the IQ-9075's LLM endpoint and the test chat UI.
rem Keep this window open while chatting; close it to drop the tunnel.
start "" "%~dp0chat.html"
echo Tunnel to iq9 (127.0.0.1:18181) - keep this window open, Ctrl+C to stop.
ssh -N -L 18181:127.0.0.1:18181 iq9
