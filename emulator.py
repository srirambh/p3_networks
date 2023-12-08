import argparse 
import asyncio
from collections import defaultdict
import copy
import csv
from datetime import datetime, timedelta
import errno
import socket
import struct

def encapsulateState(src_ip, src_port, seq_no, ttl, payload):
    packet = struct.pack("!c4sHIII" + ("8s"*len(payload)), b'L', src_ip, src_port,seq_no, len(payload), ttl , *[i[0] + i[1].to_bytes(4,'big') for i in payload])
    return packet

async def sendHello(src_ip, src_port, soc, top):
    while True:
        for idx in top[(src_ip, int(src_port))]:
            soc.sendto(struct.pack("!c4sH", b'H', src_ip, src_port), (socket.inet_ntoa(i[0]), idx[1]))
        await asyncio.sleep(.2)
        return top
    
async def sendState(src_ip, src_port, soc, top):
    seq_no = defaultdict(int)
    while True:
        for idx in top[(src_ip, int(src_port))]:
            seq_no[(src_ip, src_port)] += 1
            soc.sendto(encapsulateState(src_ip, src_port, seq_no[(src_ip, src_port)], 25, top[(src_ip, src_port)]), (socket.inet_ntoa(idx[0]), idx[1]))
        await asyncio.sleep(.2)

def forwardpacket(pack, src_ip, src_port, soc, top, ):
    t = struct.unpack_from("!c", pack, offset=0)
    if(t[0] == b'H'):
        pass
    elif(t[0] == b'L'):

        header = struct.unpack_from("!c4sHIII", pack)
        convert = lambda x: (x[:4], int.from_bytes(x[4:], "big"))
        length = header[4]
        payload = [convert(struct.unpack_from(f"!8s", pack, offset=19+(8*i))[0])  for i in range(length)]
        
        if(header[4]==0):
            return
        pack = encapsulateState(header[1], header[2], header[3], header[4]-1, payload)
        for n in top[(src_ip, src_port)]:
            soc.sendto(pack, (socket.inet_ntoa(n[0]), n[1]))
    else:
        header = struct.unpack_from(f"!BI4sH4sH", pack)
        if(header[1]==0):
            newRP = encapsulateRouteTrace(0, src_ip, src_port, header[4], header[5])
            soc.sendto(newRP, (socket.inet_ntoa(header[2]), header[3]))
        else:
            newRP = encapsulateRouteTrace(header[1]-1, header[2], header[3], header[4], header[5])
            if((header[4],header[5]) in ROUTING):
                nextHop = ROUTING[(header[4],header[5])]
                soc.sendto(newRP, (socket.inet_ntoa(nextHop[0]), nextHop[1]))
            else:
                print("next hop not found")

async def recvCheck(src_ip, src_port, soc, top, seq_no, h):
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
                header, payload = decapsulateLinkState(data)
                if(header[3] > seq_no[(header[1], header[2])] and not payload == top[(header[1],int(header[2]))]):
                    seq_no[(header[1],header[2])] = header[3]
                    top[(header[1],header[2])] = payload
                    forwardpacket(data, src_ip, src_port, soc)
                    buildForwardTable(src_ip,src_port)
            elif(x[0] == b'H'):
                pack = struct.unpack_from("!c4sH", data)
                if((pack[1], pack[2]) not in h):
                    h[(pack[1], pack[2])] = datetime.now()
                    top[(src_ip, src_port)] = top[(src_ip, src_port)]  + [(pack[1], pack[2])]
                    buildForwardTable(src_ip, src_port)
                    seq_no[(src_ip, src_port)] += 1
                    for k in top[(src_ip, src_port)]:
                        soc.sendto(encapsulateState(src_ip, src_port, seq_no[(src_ip, src_port)], 25, top[(src_ip, src_port)]), (socket.inet_ntoa(k[0]), k[1]))
                for idx in h.keys():
                    if(pack[1] == idx[0] and pack[2] == idx[1]):
                        h[idx] = datetime.now()
            else:
                forwardpacket(data, src_ip, src_port, soc)
        exp = []
        for idx in h.keys():
            if(abs(datetime.now()- h[idx]) > timedelta(milliseconds = 600)):
                temp = []
                for k in top[(src_ip, src_port)]:
                    if k != idx:
                        temp.append(k)
                top[(src_ip, src_port)] = temp
                exp.append(idx)
                buildForwardTable(src_ip, src_port)
                seq_no[(src_ip, src_port)] += 1
                for k in top[(src_ip, src_port)]:
                    soc.sendto(encapsulateState(src_ip, src_port, seq_no[(src_ip, src_port)], 25, top[(src_ip, src_port)]), (socket.inet_ntoa(k[0]), k[1]))
        for idx in exp:
            h.pop(idx)      
        await asyncio.sleep(0)
        return top, seq_no, h


def readtopology(fn, src_ip, src_port):
    top = defaultdict(list)
    with open(fn, "r") as f:
        for r in csv.reader(f, delimiter=' '):
            #top[(socket.inet_aton(r[0].split(",")[0]),int(r[0].split(",")[1]))] = list(map(lambda x: (socket.inet_aton(x.split(",")[0]), int(x.split(",")[1]) ),  r[1:]))
    buildForwardTable(src_ip, src_port, top)
    h = {}
    for idx in top[(src_ip, src_port)]:
        h[idx] = datetime.now()
    return (top, h)


def buildForwardTable(src_ip, src_port, top):
    #route = defaultdict(lambda : (b'',0))
    #route = { i : i for i in top[(sip,sport)] }
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

async def createrouteshelper(src_ip, src_port, soc, top, h):
    #t1 = asyncio.create_task(recvCheck(src_ip, src_port, soc, top, h))
    #t2 = asyncio.create_task(sendHello(src_ip, src_port, soc, top))
    #t3 = asyncio.create_task(sendState(src_ip, src_port, soc, top))
    await t1
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