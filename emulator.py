import argparse 
import asyncio
from collections import defaultdict
import copy
import csv
from datetime import datetime, timedelta
import errno
import socket
import struct

def encapstate(src_ip, src_port, seq_no, ttl, payload):
    return struct.pack("!c4sHIII" + ("8s" *len(payload)), b'L', src_ip, src_port, seq_no, len(payload), ttl, *[i[0] + i[1].to_bytes(4, 'big') for i in payload])

async def sendhello(src_ip, src_port, soc, top):
    while True:
        for idx in top[(src_ip, int(src_port))]:
            soc.sendto(struct.pack("!c4sH", b'H', src_ip, src_port), (socket.inet_ntoa(idx[0]), idx[1]))
        await asyncio.sleep(.3)
    
async def sendstate(src_ip, src_port, soc, top):
    seq_no = defaultdict(int)
    while True:
        for idx in top[(src_ip, int(src_port))]:
            seq_no[(src_ip, src_port)] += 1
            soc.sendto(encapstate(src_ip, src_port, seq_no[(src_ip, src_port)], 25, top[(src_ip, src_port)]), (socket.inet_ntoa(idx[0]), idx[1]))
        await asyncio.sleep(.3)

def forwardpacket(pack, src_ip, src_port, soc, top, route):
    t = struct.unpack_from("!c", pack, offset = 0)
    if (t[0] != b'H'):
        header = struct.unpack_from(f"!BI4sH4sH", pack)
        if(header[1] == 0):            
            soc.sendto(struct.pack(f"!cI4sH4sH", b'T', 0, src_ip, src_port, header[4], header[5]), (socket.inet_ntoa(header[2]), header[3]))
        else:
            if((header[4], header[5]) in route):
                nextHop = route[(header[4], header[5])]
                soc.sendto(struct.pack(f"!cI4sH4sH", b'T', header[1]-1, header[2], header[3], header[4], header[5])
, (socket.inet_ntoa(nextHop[0]), nextHop[1]))
            else:
                print("next hop not found")
    elif(t[0] == b'L'):
        header = struct.unpack_from("!c4sHIII", pack)
        payload = [(lambda x: (x[:4], int.from_bytes(x[4:], "big")))(struct.unpack_from(f"!8s", pack, offset = (idx * 8) + 19)[0])  for idx in range(header[4])]
        
        if(header[4]==0):
            return
        pack = encapstate(header[1], header[2], header[3], header[4]-1, payload)
        for n in top[(src_ip, src_port)]:
            soc.sendto(pack, (socket.inet_ntoa(n[0]), n[1]))
    

async def recvcheck(src_ip, src_port, soc, top, seq_no, h):
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
                if(header[3] > seq_no[(header[1], header[2])] and not payload == top[(header[1],int(header[2]))]):
                    seq_no[(header[1], header[2])] = header[3]
                    top[(header[1], header[2])] = payload
                    forwardpacket(data, src_ip, src_port, soc)
                    buildForwardTable(src_ip, src_port)
            elif(x[0] == b'H'):
                pack = struct.unpack_from("!c4sH", data)
                if((pack[1], pack[2]) not in h):
                    h[(pack[1], pack[2])] = datetime.now()
                    top[(src_ip, src_port)] = top[(src_ip, src_port)]  + [(pack[1], pack[2])]
                    buildForwardTable(src_ip, src_port)
                    seq_no[(src_ip, src_port)] += 1
                    for k in top[(src_ip, src_port)]:
                        soc.sendto(encapstate(src_ip, src_port, seq_no[(src_ip, src_port)], 25, top[(src_ip, src_port)]), (socket.inet_ntoa(k[0]), k[1]))
                for idx in h.keys():
                    if(pack[1] == idx[0] and pack[2] == idx[1]):
                        h[idx] = datetime.now()
            else:
                forwardpacket(data, src_ip, src_port, soc)
        exp = list()
        for idx in h.keys():
            if(abs(datetime.now() - h[idx]) > timedelta(milliseconds = 600)):
                temp = list()
                for k in top[(src_ip, src_port)]:
                    if k != idx:
                        temp.append(k)
                top[(src_ip, src_port)] = temp
                exp.append(idx)
                buildForwardTable(src_ip, src_port)
                seq_no[(src_ip, src_port)] += 1
                for k in top[(src_ip, src_port)]:
                    soc.sendto(encapstate(src_ip, src_port, seq_no[(src_ip, src_port)], 25, top[(src_ip, src_port)]), (socket.inet_ntoa(k[0]), k[1]))
        for idx in exp:
            h.pop(idx)      
        await asyncio.sleep(0)
        return top, seq_no, h


def readtopology(fn, src_ip, src_port):
    top = defaultdict(list)
    with open(fn, "r") as f:
        for r in csv.reader(f, delimiter=' '):
            top[(socket.inet_aton(r[0].split(",")[0]),int(r[0].split(",")[1]))] = list(map(lambda x: (socket.inet_aton(x.split(",")[0]), int(x.split(",")[1]) ),  r[1:]))
    buildForwardTable(src_ip, src_port, top)
    h = dict()
    for idx in top[(src_ip, src_port)]:
        h[idx] = datetime.now()
    return top, h


def buildForwardTable(src_ip, src_port, top):
    route = defaultdict(lambda: (b'', 0), {idx: idx for idx in top[(src_ip, src_port)]})
    queue = copy.deepcopy(top[(src_ip, src_port)])
    traversed = set()
    for idx in top[(src_ip, src_port)]:
        traversed.add(idx)
    traversed.add((src_ip, src_port))
    while len(queue) > 0:
        node = queue.pop(0)
        for n in top[node]:
            if(n not in traversed):
                queue.append(n)
                traversed.add(n)
                route[n] = route[node]
    route[(src_ip, src_port)] = None
    print(f"ROUTING FOR NODE ({src_ip}, {src_port})")
    for k,v in route.items():
        print(k, f"nextHop: {v}")
    print(f"TOPOLOGY FOR NODE ({src_ip}, {src_port})")
    for k,v in top.items():
        print(k, f"Adjacent Nodes {v}")
    

async def createrouteshelper(src_ip, src_port, soc, topology, hello):
    t1 = asyncio.create_task(recvcheck(src_ip, src_port, soc, topology, defaultdict(int), hello))
    top, seq_no, h = await t1
    t2 = asyncio.create_task(sendhello(src_ip, src_port, soc, top))
    t3 = asyncio.create_task(sendstate(src_ip, src_port, soc, top))
    await t2
    await t3

def createroutes(src_ip, src_port, soc, top, h):
    asyncio.run(createrouteshelper(src_ip, src_port, soc, top, h))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("-p", "--port")
    p.add_argument("-f", "--filename")
    args = p.parse_args()
    address = socket.inet_aton(socket.gethostbyname(socket.gethostname()))
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.bind((socket.gethostname(), int(args.port)))
    soc.setblocking(False)
    top, h = readtopology(args.filename, address, int(args.port))
    createroutes(address, int(args.port), soc, top, h)