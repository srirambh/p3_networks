import os
import socket
import subprocess
import time
import sys
def getPort():
    for i in range(2049, 65536):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((socket.gethostname(), i))   
        except socket.error as e:
            continue
        sock.close()
        yield str(i)
    yield -1

gen = getPort()
def test1():
    os.chdir("test1")
    elist = [(socket.gethostbyname(socket.gethostname()), next(gen)),(socket.gethostbyname(socket.gethostname()), next(gen))]

    with open("topology.txt", "w+") as f:
        f.write(f"{elist[0][0]},{elist[0][1]} {elist[1][0]},{elist[1][1]}\n")
        f.write(f"{elist[1][0]},{elist[1][1]} {elist[0][0]},{elist[0][1]}")
    
    parr = [None for i in range(2)]
    output = sys.stdout
    for i in range(2):
        parr[i] = subprocess.Popen(['python3', '../emulator.py',"-p", elist[i][1], "-f", "topology.txt"], stdout=output, stderr=subprocess.STDOUT)
        time.sleep(.5)
    subprocess.Popen(['python3', '../trace.py',"-a", next(gen), "-b", elist[0][0], "-c", elist[0][1], "-d",elist[1][0], "-e", elist[1][1] ,"-f", "1"], stdout=output, stderr=subprocess.STDOUT)

    time.sleep(5)
    for i in parr:
        i.terminate()
    # if out == None or len(out) == 0:
    #     subprocess.Popen(["echo", "-e" , "\e[92mtest 1 passed\e[0m"])
    # else:
    #     print(out)
    #     subprocess.Popen(["echo", "-e" , "\e[31mtest 1 failed\e[0m"])

def test2():
    os.chdir("test2")
    elist = [(socket.gethostbyname(socket.gethostname()), next(gen)),(socket.gethostbyname(socket.gethostname()), next(gen)),(socket.gethostbyname(socket.gethostname()), next(gen))]

    with open("topology.txt", "w+") as f:
        f.write(f"{elist[0][0]},{elist[0][1]} {elist[1][0]},{elist[1][1]} {elist[2][0]},{elist[2][1]}\n")
        f.write(f"{elist[1][0]},{elist[1][1]} {elist[0][0]},{elist[0][1]} {elist[2][0]},{elist[2][1]}\n")
        f.write(f"{elist[2][0]},{elist[2][1]} {elist[0][0]},{elist[0][1]} {elist[1][0]},{elist[1][1]}\n")

    
    parr = [None for i in range(3)]
    output = sys.stdout
    for i in range(3):
        parr[i] = subprocess.Popen(['python3', '../emulator.py',"-p", elist[i][1], "-f", "topology.txt"], stdout=output, stderr=subprocess.STDOUT)
        time.sleep(.5)
    parr[2].terminate()

    time.sleep(5)
    subprocess.Popen(['python3', '../trace.py',"-a", next(gen), "-b", elist[0][0], "-c", elist[0][1], "-d",elist[2][0], "-e", elist[2][1] ,"-f", "1"], stdout=output, stderr=subprocess.STDOUT)
    time.sleep(5)
    parr = [parr[0],parr[1]]
    for i in parr:
        i.terminate()
    # if out == None or len(out) == 0:
    #     subprocess.Popen(["echo", "-e" , "\e[92mtest 1 passed\e[0m"])
    # else:
    #     print(out)
    #     subprocess.Popen(["echo", "-e" , "\e[31mtest 1 failed\e[0m"])
def test3():
    os.chdir("test1")
    elist = [(socket.gethostbyname(socket.gethostname()), next(gen)),(socket.gethostbyname(socket.gethostname()), next(gen)),(socket.gethostbyname(socket.gethostname()), next(gen))]

    with open("topology.txt", "w+") as f:
        f.write(f"{elist[0][0]},{elist[0][1]} {elist[1][0]},{elist[1][1]}\n")
        f.write(f"{elist[1][0]},{elist[1][1]} {elist[0][0]},{elist[0][1]}")
    with open("topology2.txt", "w+") as f:
        f.write(f"{elist[0][0]},{elist[0][1]} {elist[1][0]},{elist[1][1]} {elist[2][0]},{elist[2][1]}\n")
        f.write(f"{elist[1][0]},{elist[1][1]} {elist[0][0]},{elist[0][1]} {elist[2][0]},{elist[2][1]}\n")
        f.write(f"{elist[2][0]},{elist[2][1]} {elist[0][0]},{elist[0][1]} {elist[1][0]},{elist[1][1]}\n")


    
    parr = [None for i in range(3)]
    output = sys.stdout
    for i in range(2):
        parr[i] = subprocess.Popen(['python3', '../emulator.py',"-p", elist[i][1], "-f", "topology.txt"], stdout=output, stderr=subprocess.STDOUT)
    
    parr[2] = subprocess.Popen(['python3', '../emulator.py',"-p", elist[2][1], "-f", "topology2.txt"], stdout=output, stderr=subprocess.STDOUT)
    time.sleep(5)
    subprocess.Popen(['python3', '../trace.py',"-a", next(gen), "-b", elist[0][0], "-c", elist[0][1], "-d",elist[2][0], "-e", elist[2][1] ,"-f", "1"], stdout=output, stderr=subprocess.STDOUT)
    time.sleep(5)
    for i in parr:
        i.terminate()
def test4():
    
    elist = [(socket.gethostbyname(socket.gethostname()), next(gen)) for i in range(5)]

    with open("topology.txt", "w+") as f:
        f.write(" ".join([f"{elist[i][0]},{elist[i][1]}" for i in [0,1,2]]) + "\n" )
        f.write(" ".join([f"{elist[i][0]},{elist[i][1]}" for i in [1,0,2,4]]) + "\n" )
        f.write(" ".join([f"{elist[i][0]},{elist[i][1]}" for i in [2,0,1,3]]) + "\n" )
        f.write(" ".join([f"{elist[i][0]},{elist[i][1]}" for i in [3,2,4]]) + "\n" )
        f.write(" ".join([f"{elist[i][0]},{elist[i][1]}" for i in [4,1,3]]) + "\n" )
    parr = [None for i in range(5)]
    output = sys.stdout
    for i in range(5):
        parr[i] = subprocess.Popen(['python3', 'emulator.py',"-p", elist[i][1], "-f", "topology.txt"], stdout=output, stderr=subprocess.STDOUT)
    time.sleep(1)
    subprocess.Popen(['python3', 'trace.py',"-a", next(gen), "-b", elist[0][0], "-c", elist[0][1], "-d",elist[3][0], "-e", elist[3][1] ,"-f", "1"], stdout=output, stderr=subprocess.STDOUT)
    time.sleep(1)
    parr[2].terminate()
    time.sleep(5)
    subprocess.Popen(['python3', 'trace.py',"-a", next(gen), "-b", elist[0][0], "-c", elist[0][1], "-d",elist[3][0], "-e", elist[3][1] ,"-f", "1"], stdout=output, stderr=subprocess.STDOUT)
    time.sleep(5)
    for i in parr:
        i.terminate()
if __name__ == "__main__":
    for i in ["test" + str(i) for i in range(4,5)]:
        globals()[i]()
        os.chdir(os.path.dirname(os.path.realpath(__file__)))