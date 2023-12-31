import argparse
import socket
import struct
import sys
from collections import defaultdict

def receiveRes(sock):
    header = None
    try:
        rec = sock.recvfrom(10000)[0]
        header = struct.unpack_from(f"!cI4sH4sH", rec)
        return header
    except:
        return header


def printPacketInfo(srcIP, srcPort, destIP, destPort, ttl):
    print("TTL: ", ttl)
    print("Source IP: ", srcIP)
    print("Source Port: ", srcPort)
    print("Destination IP: ", destIP)
    print("Destination Port: ", destPort)
    print("=====================")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("-a", "--routetrace_port", help="Input routetrace port")
    p.add_argument("-b", "--source_hostname", help="Input hostname for source")
    p.add_argument("-c", "--source_port", help="Input source port")
    p.add_argument("-d", "--destination_hostname", help="Input hostname for destination")
    p.add_argument("-e", "--destination_port", help="Input destination port")
    p.add_argument("-f", "--debug_option", help="Input debug options")
    args = p.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((socket.gethostname(), int(args.routetrace_port)))
    sock.settimeout(5)

    selfIP = socket.inet_aton(socket.gethostbyname(socket.gethostname()))
    srcIP = socket.inet_aton(socket.gethostbyname(args.source_hostname))
    destIP = socket.inet_aton(socket.gethostbyname(args.destination_hostname))


    ttl = 0
    path = []
    while True:
        packet = struct.pack(f"!cI4sH4sH", b'T', ttl, srcIP, int(args.routetrace_port), destIP, int(args.destination_port))
        sock.sendto(packet, (socket.inet_ntoa(srcIP), int(args.source_port)))
        if(int(args.debug_option) == 1):
            print("=====Sent Packet====")
            printPacketInfo(socket.inet_ntoa(srcIP), int(args.source_port), socket.inet_ntoa(destIP), int(args.destination_port), ttl)

        res = receiveRes(sock)
        if(not res):
            print("Can't reach node")
            sys.exit()

        path.append((socket.inet_ntoa(res[2]),res[3]))
        if(int(args.debug_option) == 1):
            print("=====Received Packet====")
            printPacketInfo(socket.inet_ntoa(res[2]), res[3], socket.inet_ntoa(res[4]), res[5], ttl)

        if(res[2] == destIP and res[3] == int(args.destination_port)):
            print("Destination reached")
            print("Hop #\tIP:Port")
            for i in range(len(path)):
                print(f"{i+1} \t{path[i][0]}:{path[i][1]}")
            break
        else:
            ttl += 1