#!/usr/bin/env python3

import subprocess,os,signal
from argparse import ArgumentParser, FileType, REMAINDER
from sys import argv,float_info,stdout,stderr
from pathlib import Path
from threading import Thread, current_thread
from time import sleep

DUMP=['--dump']
EVENT=['--event','--event-mask','NEW','--event-mask','DESTROY']

count=0

def log(*message):
    print(current_thread().name+':>',*message)
    stdout.flush()

def stop(*args,**kwargs):
    print()
    send_signal(True)
    log('goodbye')
    exit(0)

def conntrack(command=None,family=None,proto=None,port=None,args=None):
    cmd=command.copy()
    cmd.insert(0,'conntrack')
    if(family):
        cmd.extend(['--family',family])
    if(proto):
        cmd.extend(['--proto',proto])
    if(port):
        cmd.extend(['--dport',port])
    if(args):
        cmd.extend(args)
    log(' '.join(cmd))
    return subprocess.Popen(cmd,stdout=subprocess.PIPE,universal_newlines=True)

def get_connection_count(family,proto,port):
    count=-1
    with conntrack(DUMP,family,proto,port) as process:
        for line in process.stdout:
            count+=1
    return count

def pid_signal(cont):
    if cont:
        log('SIGCONT > '+str(target))
        os.kill(target,signal.SIGCONT)
    else:
        log('SIGSTOP > '+str(target))
        os.kill(target,signal.SIGSTOP)

def cgroup_signal(cont):
    path=Path('/sys/fs/cgroup',cgroup,'cgroup.freeze')
    if(cont):
        log('0 > '+path.as_posix())
        path.write_text('0')
    else:
        log('0 > '+path.as_posix())
        path.write_text('1')

def systemd_signal(cont):
    if cont:
        log('systemctl kill --signal=CONT '+target)
        subprocess.run(['systemctl','kill','--signal=CONT',target])
    else:
        log('systemctl kill --signal=STOP '+target)
        subprocess.run(['systemctl','kill','--signal=STOP',target])

def docker_signal(cont):
    if cont:
        log('docker unpause '+target)
        subprocess.run(['docker','unpause',target])
    else:
        log('docker pause '+target)
        subprocess.run(['docker','pause',target])

def get_pid_sockets(pid):
    sockets=[]
    with subprocess.Popen(['ss','-tunlp'],stdout=subprocess.PIPE,universal_newlines='*') as process:
        for line in process.stdout:
            if 'pid='+str(pid) in line:
                line=line.split()
                proto=line[0]
                index=line[4].rfind(':')
                ip=line[4][0:index]
                port=line[4][index+1:]
                if ip == '*':
                    sockets.append({
                        'family':'ipv4',
                        'proto':proto,
                        'port':port
                    })
                    sockets.append({
                        'family':'ipv6',
                        'proto':proto,
                        'port':port
                    })
                elif ip[0] == '[':
                    sockets.append({
                        'family':'ipv6',
                        'proto':proto,
                        'port':port
                    })
                else:
                    sockets.append({
                        'family':'ipv4',
                        'proto':proto,
                        'port':port
                    })
    return sockets

def get_cgroup_sockets(cgroup):
    pids=Path('/sys/fs/cgroup',cgroup,'cgroup.procs').read_text().split()
    sockets=[]
    for pid in pids:
        sockets.extend(get_pid_sockets(pid))
    return sockets

def get_service_sockets(service):
    result=subprocess.run(['systemctl','show','-p','ControlGroup','--value',service],capture_output=True)
    return get_cgroup_sockets(result.stdout.decode().strip())

def get_docker_sockets(container):
    sockets=[]
    with subprocess.Popen(['docker','port',container],stdout=subprocess.PIPE,universal_newlines=True) as process:
        for line in process.stdout:
            line=line.split()
            proto=line[0].split('/')[1]
            index=line[2].rfind(':')
            ip=line[2][0:index]
            port=line[2][index+1:]
            if ip == '0.0.0.0':
                sockets.append({
                    'family':'ipv4',
                    'proto':proto,
                    'port':port
                })
                sockets.append({
                    'family':'ipv6',
                    'proto':proto,
                    'port':port
                })
            elif ip[0] == '[':
                sockets.append({
                    'family':'ipv6',
                    'proto':proto,
                    'port':port
                })
            else:
                sockets.append({
                    'family':'ipv4',
                    'proto':proto,
                    'port':port
                })
    return sockets

def main(family,proto,port):
    global count
    count+=get_connection_count(family,proto,port)
    send_signal(count)
    with conntrack(EVENT,family,proto,port) as process:
        for line in process.stdout:
            if 'NEW' in line:
                count+=1
            if 'DESTROY' in line:
                count-=1
            send_signal(count)

parser=ArgumentParser(
    prog=argv[0],
    description='pause a process, container, or service based on firewall connection state tracking',
    epilog='this program must be run as root and should only be started after the target is ready to accept connections.'
)

target=parser.add_mutually_exclusive_group(required=True)
target.add_argument('-p','--pid',help='PID of a process with listening sockets')
target.add_argument('-d','--docker',help='Name of a docker container with published ports or listening sockets',metavar='CONTAINER')
target.add_argument('-s','--service',help='Name of a systemd service with listening sockets')
target.add_argument('-g','--cgroup',help='Name of a cgroup with listening sockets')
parser.add_argument('-c','--conntrack',help="""Override automatic socket detection in favor of these conntrack args.
                                            This should be a single argument with spaces between the conntrack args,
                                            so you'll need to use quotes if calling from a shell.""",metavar='ARGS',action='append')

args=parser.parse_args(argv[1:])

if args.pid:
    target=args.pid
    send_signal=pid_signal
    get_sockets=get_pid_sockets

if args.cgroup:
    target=args.cgroup
    send_signal=cgroup_signal
    get_sockets=get_cgroup_sockets
    if(target[0]=='/'):
        target=target[1:]

if args.service:
    target=args.service
    send_signal=systemd_signal
    get_sockets=get_service_sockets

if args.docker:
    target=args.docker
    send_signal=docker_signal
    get_sockets=get_docker_sockets

sockets=get_sockets(target)
log('found '+str(len(sockets))+' sockets')
if not len(sockets):
    stop()
for socket in sockets:
    Thread(name=str(socket),target=main,kwargs=socket,daemon=True).start()

signal.signal(signal.SIGTERM,stop)
signal.signal(signal.SIGINT,stop)

while True:
    sleep(float_info.max_exp)
