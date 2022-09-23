import os
import subprocess
import requests
import time

#max gpu load
MAX_GPU=0
#max time of no util usage
MAX_SEC=7200
#exclude root process (leave empty for match root process too)
EXCLUDE_ROOT="grep -v root"
#process command name to check
KILLCMD="nvidia-smi -q -d PIDs | grep 'Process ID' | awk '{print $4}'"
KILLLIST= str(subprocess.run(KILLCMD, stdout=subprocess.PIPE, shell=True).stdout).lstrip("b'").rstrip("\\n'").split("\\n")
KILLLIST= list(map(int, KILLLIST))

#process Sort by
SORTBY=8

#time ticker
TIME_LIST= {}

headers = {
    'Content-type': 'application/json',
}

while(True):
    #iterate for each process to check in list
    for PROCESS_TOCHECK in KILLLIST:
        start= time.time()
        #pid
        PID=PROCESS_TOCHECK

        if(PID not in TIME_LIST):
            TIME_LIST[PID]= 0

        #user
        TEMP="cat /proc/{PID}/cgroup | grep 'name' | tr '/' '\n'".format(PID=PID)
        TEMP= str(subprocess.run(TEMP, stdout=subprocess.PIPE, shell=True).stdout)
        TEMP2= list(TEMP.split("\\n"))
        TEMP2= TEMP2[2]
        TEMP3="docker ps -f id=%s --format '{{.Names}}'" % (TEMP2)
        USER= str(subprocess.run(TEMP3, stdout=subprocess.PIPE, shell=True).stdout).lstrip("b'").rstrip("\\n'").rstrip("")

        if (USER == "root"):
            continue

        #Fetch other process stats by pid
        #GPU Memory Usage
        GPU="nvidia-smi | grep %s | sort -k 8 -r | head -n 1 | awk '{print $8}'" %(PID)
        GPU= str(subprocess.run(GPU, stdout=subprocess.PIPE, shell=True).stdout).lstrip("b'").rstrip("MiB\\n'")
        GPU= int(GPU)

        #GPU UID
        GPU_UIDS="nvidia-smi -q | grep 'GPU UUID' | awk '{print $4}'"
        GPU_UIDS= str(subprocess.run(GPU_UIDS, stdout=subprocess.PIPE, shell=True).stdout).lstrip("b'").rstrip("\\n'").split("\\n")

        #PID list of GPU
        for GPU_UID in GPU_UIDS:
            PID2S="nvidia-smi -q -d PIDs -i %s | grep 'Process ID' | awk '{print $4}'" %(GPU_UID)
            PID2S= str(subprocess.run(PID2S, stdout=subprocess.PIPE, shell=True).stdout).lstrip("b'").rstrip("\\n'").split("\\n")
            PID2S= list(map(int, PID2S))
            #GPU Util
            for PID2 in PID2S:
                if (PID == PID2):
                    TEMP4="nvidia-smi -q -d UTILIZATION -i %s | grep 'Gpu' | awk '{print $3}'" %(GPU_UID)
                    UTIL= str(subprocess.run(TEMP4, stdout=subprocess.PIPE, shell=True).stdout).lstrip("b'").rstrip("\\n'")
                    UTIL= int(UTIL)
                    break
        
        #Kill process
        if(GPU > MAX_GPU and UTIL ==0):
            if(TIME_LIST[PID] >= MAX_SEC):
                json="{'text': 'GPU load from process ( PID: %d ) User: %s used %dMiB of GPU Memory with no utilization. Process was killed.'}" %(PID, USER, GPU)
                response = requests.post('YOUR_SLACK_WEBHOOK', headers=headers, data=json) #Put your Slack webhook at YOUR_SLACK_WEBHOOK
                kill= "kill -15 %d" %(PID)
                subprocess.run(kill, shell=True)
                subprocess.run("sleep 3", shell=True)
                kill= "kill -9 %d" %(PID)
                subprocess.run(kill, shell=True)
                ##Kill zombie process
                #echo "kill zombies"
                #subprocess.run("ps -ef | grep defunct | awk '{print $3}' | xargs kill -9", shell=True)
                del(TIME_LIST[PID])
            else:
                TIME_LIST[PID] += time.time() - start
        else:
            TIME_LIST[PID]= 0