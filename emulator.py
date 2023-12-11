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
SEQ_NUM = defaultdict(int)
TOP = defaultdict(list)

def encapstate(src_ip, src_port, seq_no, payload, ttl):
    return struct.pack("!c4sHIII" + ("8s" *len(payload)), b'L', src_ip, 
                       src_port, seq_no, len(payload), ttl, *[i[0] + i[1].to_bytes(4, 'big') for i in payload])

async def sendstate(soc, src_port, src_ip):
    global SEQ_NUM
    while True:
        for idx in TOP[(src_ip, int(src_port))]:
            SEQ_NUM[(src_ip, src_port)] += 1
            soc.sendto(encapstate(src_ip, src_port, SEQ_NUM[(src_ip, src_port)], TOP[(src_ip, src_port)], 25)
                       (socket.inet_ntoa(idx[0]), idx[1]))
        await asyncio.sleep(.3)

async def sendhello(soc, src_port, src_ip):
    global TOP
    while True:
        for idx in TOP[(src_ip, int(src_port))]:
            soc.sendto(struct.pack("!c4sH", b'H', src_ip, src_port), (socket.inet_ntoa(idx[0]), idx[1]))
        await asyncio.sleep(.3)

def forwardpacket(pack, src_ip, src_port, soc):
    #global TOP, ROUTE
    a = struct.unpack_from("!c", pack, offset = 0)
    if(a[0] == b'L'):
        header = struct.unpack_from("!c4sHIII", pack)
        payload = [(lambda x: (x[:4], int.from_bytes(x[4:], 
                    "big")))(struct.unpack_from(f"!8s",
                    pack, offset = (idx * 8) + 19)[0])  for idx in range(header[4])]
        
        if(header[4] != 0):
            pack = encapstate(header[1], header[2], header[3], payload, header[4]-1)
            for n in TOP[(src_ip, src_port)]:
                soc.sendto(pack, (socket.inet_ntoa(n[0]), n[1]))
        else:
            return
    elif (a[0] != b'H'):
        header = struct.unpack_from(f"!BI4sH4sH", pack)
        if (header[1] != 0):
            if((header[4], header[5]) in ROUTE):
                nextHop = ROUTE[(header[4], header[5])]
                soc.sendto(struct.pack(f"!cI4sH4sH", b'T', header[1]-1, 
                                       header[2], header[3], header[4], header[5]), 
                                       (socket.inet_ntoa(nextHop[0]), nextHop[1]))
                print("sent!")
            else:
                print("unable to find next hop")
        else:
            soc.sendto(struct.pack(f"!cI4sH4sH", b'T', 0, src_ip, src_port, header[4], 
                                   header[5]), (socket.inet_ntoa(header[2]), header[3]))
    

async def recvcheck(soc, src_port, src_ip):
    global TOP, SEQ_NUM, H
    while True:
        data = None
        try:
            data = soc.recvfrom(10000)[0]
        except socket.error as err:
            e = err.args[0] 
            if e != errno.EAGAIN and e != errno.EWOULDBLOCK:
                print(err)
        if(data is not None):
            x = struct.unpack_from("!c", data, offset=0)
            if(x[0] == b'L'):
                head = struct.unpack_from("!c4sHIII", data)
                pay = [(lambda x: (x[:4], int.from_bytes(x[4:], "big")))
                           (struct.unpack_from(f"!8s", data, offset = (idx * 8) + 19)[0])  for idx in range(head[4])]
                if(pay != TOP[(head[1], int(head[2]))] and head[3] > SEQ_NUM[(head[1], head[2])]):
                    TOP[(head[1], head[2])] = pay
                    SEQ_NUM[(head[1], head[2])] = head[3]
                    forwardpacket(data, src_ip, src_port, soc)
                    buildForwardTable(src_ip, src_port)
            elif(x[0] == b'H'):
                pack = struct.unpack_from("!c4sH", data)
                if((pack[1], pack[2]) not in H):
                    TOP[(src_ip, src_port)] = TOP[(src_ip, src_port)]  + [(pack[1], pack[2])]
                    H[(pack[1], pack[2])] = datetime.now()
                    buildForwardTable(src_ip, src_port)
                    SEQ_NUM[(src_ip, src_port)] += 1
                    for k in TOP[(src_ip, src_port)]:
                        soc.sendto(encapstate(src_ip, src_port, SEQ_NUM[(src_ip, src_port)], 
                                              TOP[(src_ip, src_port)], 25), (socket.inet_ntoa(k[0]), k[1]))
                for idx in H.keys():
                    if(pack[2] == idx[1] and pack[1] == idx[0]):
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
                SEQ_NUM[(src_ip, src_port)] += 1
                for k in TOP[(src_ip, src_port)]:
                    soc.sendto(encapstate(src_ip, src_port, SEQ_NUM[(src_ip, src_port)], 
                                          TOP[(src_ip, src_port)], 25), (socket.inet_ntoa(k[0]), k[1]))
        for idx in exp:
            H.pop(idx)      
        await asyncio.sleep(0)

def readtopology(fn, src_ip, src_port):
    global TOP, H
    TOP = defaultdict(list)
    with open(fn, "r") as f:
        for r in csv.reader(f, delimiter=' '):
            TOP[(socket.inet_aton((r[0].split(","))[0]), 
                 int((r[0].split(","))[1]))] = list(map(lambda x: (socket.inet_aton(x.split(",")[0]), 
                                                                   int(x.split(",")[1]) ),  r[1:]))
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
    print("Routing: " + f"{socket.inet_ntoa(src_ip)}" + ":" f"{src_port}")
    for k, v in ROUTE.items():
        if v:
            print(f"{socket.inet_ntoa(k[0])}" + ":" f"{k[1]}", f"\tNext hop: {socket.inet_ntoa(v[0])}" + ":" f"{v[1]}")
        else:
            print(f"{socket.inet_ntoa(k[0])}" + ":" f"{k[1]}", f"\tNext hop: {v}")
    print("Topology: " + f"{socket.inet_ntoa(src_ip)}" + ":" f"{src_port}")
    for k, v in TOP.items():
        temp = [(socket.inet_ntoa(v[i][0]), v[i][1]) for i in range(len(v))]
        format = list()
        for x in temp:
            format.append(x[0] + ":" + str(x[1]))
        print(f"{socket.inet_ntoa(k[0])}" + ":" f"{k[1]}", f"\tAdjacent nodes: {format}")
    

def createroutes(soc, src_port, src_ip):
    asyncio.run(createrouteshelper(soc, src_port, src_ip))

async def createrouteshelper(soc, src_port, src_ip):
    t1 = asyncio.create_task(recvcheck(soc, src_port, src_ip))
    t2 = asyncio.create_task(sendhello(soc, src_port, src_ip))
    t3 = asyncio.create_task(sendstate(soc, src_port, src_ip))
    await t1
    await t2
    await t3

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("-p", "--port", help="Input port")
    p.add_argument("-f", "--filename", help="Input file name")
    args = p.parse_args()
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.bind((socket.gethostname(), int(args.port)))
    soc.setblocking(False)
    address = socket.inet_aton(socket.gethostbyname(socket.gethostname()))
    readtopology(args.filename, address, int(args.port))
    createroutes(soc, int(args.port), address)