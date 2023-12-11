import argparse
import socket
import struct
import sys
from datetime import datetime

def receiveRes(sock):
    header = None
    try:
        rec = sock.recvfrom(10000)[0]
        header = struct.unpack_from("!cI4sH4sH", rec)
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

def traceRoute(src_ip, src_port, dest_ip, dest_port, debug_option):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((socket.gethostname(), src_port))
    sock.settimeout(5)

    ttl = 0
    path = []
    while True:
        packet = struct.pack(f"!cI4sH4sH", b'T', ttl, src_ip, src_port, dest_ip, dest_port)
        sock.sendto(packet, (socket.inet_ntoa(src_ip), src_port))
        if debug_option == 1:
            print("=====Sent Packet====")
            printPacketInfo(socket.inet_ntoa(src_ip), src_port, socket.inet_ntoa(dest_ip), dest_port, ttl)

        res = receiveRes(sock)
        if not res:
            print("Can't reach node")
            sys.exit()

        path.append((socket.inet_ntoa(res[2]), res[3]))
        if debug_option == 1:
            print("=====Received Packet====")
            printPacketInfo(socket.inet_ntoa(res[2]), res[3], socket.inet_ntoa(res[4]), res[5], ttl)

        if res[2] == dest_ip and res[3] == dest_port:
            print("Destination reached")
            for i in range(len(path)):
                print(f"Hop {i+1} IP {path[i][0]} Port {path[i][1]}")
            break
        else:
            ttl += 1

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("-a", "--routetrace_port", help="Input routetrace port")
    p.add_argument("-b", "--source_hostname", help="Input hostname for source")
    p.add_argument("-c", "--source_port", help="Input source port")
    p.add_argument("-d", "--destination_hostname", help="Input hostname for destination")
    p.add_argument("-e", "--destination_port", help="Input destination port")
    p.add_argument("-f", "--debug_option", help="Input debug options")
    args = p.parse_args()

    src_ip = socket.inet_aton(socket.gethostbyname(args.source_hostname))
    dest_ip = socket.inet_aton(socket.gethostbyname(args.destination_hostname))

    traceRoute(src_ip, int(args.source_port), dest_ip, int(args.destination_port), int(args.debug_option))
