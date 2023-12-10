import argparse 
import asyncio
from collections import defaultdict
import copy
import csv
from datetime import datetime, timedelta
import errno
import socket
import struct
H = dict()
ROUTE = defaultdict(lambda: (b'', 0))
SEQ_NO = defaultdict(int)
TOP = defaultdict(list)
def encapstate(src_ip, src_port, seq_no, ttl, payload):
    return struct.pack("!c4sHIII" + ("8s" *len(payload)), b'L', src_ip, src_port, seq_no, len(payload), ttl, *[i[0] + i[1].to_bytes(4, 'big') for i in payload])

async def sendhello(src_ip, src_port, soc):
    global TOP
    while True:
        for idx in TOP[(src_ip, int(src_port))]:
            soc.sendto(struct.pack("!c4sH", b'H', src_ip, src_port), (socket.inet_ntoa(idx[0]), idx[1]))
        await asyncio.sleep(.3)
    
async def sendstate(src_ip, src_port, soc):
    global SEQ_NO
    while True:
        for idx in TOP[(src_ip, int(src_port))]:
            SEQ_NO[(src_ip, src_port)] += 1
            soc.sendto(encapstate(src_ip, src_port, SEQ_NO[(src_ip, src_port)], 25, TOP[(src_ip, src_port)]), (socket.inet_ntoa(idx[0]), idx[1]))
        await asyncio.sleep(.3)

def forwardpacket(pack, src_ip, src_port, soc):
    global TOP, ROUTE
    t = struct.unpack_from("!c", pack, offset = 0)
    if(t[0] == b'L'):
        header = struct.unpack_from("!c4sHIII", pack)
        payload = [(lambda x: (x[:4], int.from_bytes(x[4:], "big")))(struct.unpack_from(f"!8s", pack, offset = (idx * 8) + 19)[0])  for idx in range(header[4])]
        
        if(header[4]==0):
            return
        pack = encapstate(header[1], header[2], header[3], header[4]-1, payload)
        for n in TOP[(src_ip, src_port)]:
            soc.sendto(pack, (socket.inet_ntoa(n[0]), n[1]))
    elif (t[0] != b'H'):
        header = struct.unpack_from(f"!BI4sH4sH", pack)
        if(header[1] == 0):            
            soc.sendto(struct.pack(f"!cI4sH4sH", b'T', 0, src_ip, src_port, header[4], header[5]), (socket.inet_ntoa(header[2]), header[3]))
        else:
            if((header[4], header[5]) in ROUTE):
                nextHop = ROUTE[(header[4], header[5])]
                soc.sendto(struct.pack(f"!cI4sH4sH", b'T', header[1]-1, header[2], header[3], header[4], header[5])
, (socket.inet_ntoa(nextHop[0]), nextHop[1]))
            else:
                print("next hop not found")
    
    

async def recvcheck(src_ip, src_port, soc):
    global TOP, SEQ_NO, H
    while True:
        data = None
        try:
            data = soc.recvfrom(10000)[0]
        except socket.error as err:
            e = err.args[0] 
            if e != errno.EAGAIN and e != errno.EWOULDBLOCK:
                print(err)
        if(data):
            x = struct.unpack_from("!c", data, offset=0)
            if(x[0] == b'L'):
                header = struct.unpack_from("!c4sHIII", data)
                payload = [(lambda x: (x[:4], int.from_bytes(x[4:], "big")))(struct.unpack_from(f"!8s", data, offset = (idx * 8) + 19)[0])  for idx in range(header[4])]
                if(header[3] > SEQ_NO[(header[1], header[2])] and not payload == TOP[(header[1],int(header[2]))]):
                    SEQ_NO[(header[1], header[2])] = header[3]
                    TOP[(header[1], header[2])] = payload
                    forwardpacket(data, src_ip, src_port, soc)
                    buildForwardTable(src_ip, src_port)
            elif(x[0] == b'H'):
                pack = struct.unpack_from("!c4sH", data)
                if((pack[1], pack[2]) not in H):
                    H[(pack[1], pack[2])] = datetime.now()
                    TOP[(src_ip, src_port)] = TOP[(src_ip, src_port)]  + [(pack[1], pack[2])]
                    buildForwardTable(src_ip, src_port)
                    SEQ_NO[(src_ip, src_port)] += 1
                    for k in TOP[(src_ip, src_port)]:
                        soc.sendto(encapstate(src_ip, src_port, SEQ_NO[(src_ip, src_port)], 25, TOP[(src_ip, src_port)]), (socket.inet_ntoa(k[0]), k[1]))
                for idx in H.keys():
                    if(pack[1] == idx[0] and pack[2] == idx[1]):
                        H[idx] = datetime.now()
            else:
                forwardpacket(data, src_ip, src_port, soc)
        exp = list()
        for idx in H.keys():
            if(abs(datetime.now() - H[idx]) > timedelta(milliseconds = 600)):
                temp = list()
                for k in TOP[(src_ip, src_port)]:
                    if k != idx:
                        temp.append(k)
                TOP[(src_ip, src_port)] = temp
                exp.append(idx)
                buildForwardTable(src_ip, src_port)
                SEQ_NO[(src_ip, src_port)] += 1
                for k in TOP[(src_ip, src_port)]:
                    soc.sendto(encapstate(src_ip, src_port, SEQ_NO[(src_ip, src_port)], 25, TOP[(src_ip, src_port)]), (socket.inet_ntoa(k[0]), k[1]))
        for idx in exp:
            H.pop(idx)      
        await asyncio.sleep(0)


def readtopology(fn, src_ip, src_port):
    global TOP, H
    TOP = defaultdict(list)
    with open(fn, "r") as f:
        for r in csv.reader(f, delimiter=' '):
            TOP[(socket.inet_aton((r[0].split(","))[0]),int((r[0].split(","))[1]))] = list(map(lambda x: (socket.inet_aton(x.split(",")[0]), int(x.split(",")[1]) ),  r[1:]))
    buildForwardTable(src_ip, src_port)
    H = dict()
    for idx in TOP[(src_ip, src_port)]:
        H[idx] = datetime.now()


def buildForwardTable(src_ip, src_port):
    global ROUTE
    ROUTE = {idx: idx for idx in TOP[(src_ip, src_port)]}
    queue = copy.deepcopy(TOP[(src_ip, src_port)])
    traversed = set()
    for idx in TOP[(src_ip, src_port)]:
        traversed.add(idx)
    traversed.add((src_ip, src_port))
    while len(queue) > 0:
        node = queue.pop(0)
        for n in TOP[node]:
            if(n not in traversed):
                queue.append(n)
                traversed.add(n)
                ROUTE[n] = ROUTE[node]
    ROUTE[(src_ip, src_port)] = None
    print(f"ROUTING FOR NODE ({src_ip}, {src_port})")
    for k,v in ROUTE.items():
        print(k, f"nextHop: {v}")
    print(f"TOPOLOGY FOR NODE ({src_ip}, {src_port})")
    for k,v in TOP.items():
        print(k, f"Adjacent Nodes {v}")
    

async def createrouteshelper(src_ip, src_port, soc):
    t1 = asyncio.create_task(recvcheck(src_ip, src_port, soc))
    t2 = asyncio.create_task(sendhello(src_ip, src_port, soc))
    t3 = asyncio.create_task(sendstate(src_ip, src_port, soc))
    await t1
    await t2
    await t3

def createroutes(src_ip, src_port, soc):
    asyncio.run(createrouteshelper(src_ip, src_port, soc))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("-p", "--port")
    p.add_argument("-f", "--filename")
    args = p.parse_args()
    address = socket.inet_aton(socket.gethostbyname(socket.gethostname()))
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.bind((socket.gethostname(), int(args.port)))
    soc.setblocking(False)
    readtopology(args.filename, address, int(args.port))
    createroutes(address, int(args.port), soc)