# PausePal
This script uses the linux firewall's connection tracking mechanism to determine if a daemon has connected users,
and if there are none it issues a `SIGSTOP` (or `docker pause`) to prevent any idle processing from consuming CPU resources.
When a new connection is detected, `SIGCONT` (or `docker unpause`) is sent, keeping the daemon responsive to new requests.
This program was written for use with PalWorld dedicated servers, hence the name PausePal,
but can be used on any linux process with UDP or TCP listening sockets.
## Requirements
This script relies on the command `conntrack` to provide connection tracking info.
The command `ss` is required for automatic socket detection.
## Usage
```
usage: ./pausepal.py [-h] (-p PID | -d CONTAINER | -s SERVICE | -g CGROUP) [-c ARGS]

pause a process, container, or service based on firewall connection state tracking

optional arguments:
  -h, --help            show this help message and exit
  -p PID, --pid PID     PID of a process with listening sockets
  -d CONTAINER, --docker CONTAINER
                        Name of a docker container with published ports or listening sockets
  -s SERVICE, --service SERVICE
                        Name of a systemd service with listening sockets
  -g CGROUP, --cgroup CGROUP
                        Name of a cgroup with listening sockets
  -c ARGS, --conntrack ARGS
                        Override automatic socket detection in favor of these conntrack args. This should be a single argument with spaces between the conntrack args, so you'll need to use quotes if calling from a
                        shell.

this program must be run as root and should only be started after the target is ready to accept connections.
```