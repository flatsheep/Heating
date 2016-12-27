import socket
import binascii
from time import sleep

def maina():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('192.168.1.2', 8899))
    s.settimeout(2)

    sendStack = dict()

    sendStack[1] = bytearray([0x01, 0x29, 0x00, 0x2A])
    sendStack[2] = bytearray([0x02,0x26,0x00,0x28])
    sendStack[3] = bytearray([0x03,0x26,0x00,0x29])
    sendStack[4] = bytearray([0x04,0x26,0x00,0x2A])
    sendStack[5] = bytearray([0x05,0x26,0x00,0x2B])
    sendStack[6] = bytearray([0x06,0x26,0x00,0x2C])
    sendStack[7] = bytearray([0x07, 0x26, 0x00, 0x2D])
    sendStack[8] = bytearray([0x08, 0x26, 0x00, 0x2E])
    sendStack[9] = bytearray([0x09, 0x26, 0x00, 0x2F])
    sendStack[10] = bytearray([0x0A, 0x26, 0x00, 0x30])
    sendStack[11] = bytearray([0x0B, 0x26, 0x00, 0x31])
    sendStack[12] = bytearray([0x0C, 0x26, 0x00, 0x32])

    sendIndex = 1

    while True:
        try:
            s.send(sendStack[sendIndex])

            sendIndex += 1
            if(sendIndex == len(sendStack) + 1): sendIndex = 1

            sleep(1)

            msg = s.recv(1024)
        except socket.timeout as e:
            err = e.args[0]

            if err == 'timed out':
                sleep(1)
                print('recv timed out, try later')
                continue
            else:
                print(e)
                #sys.exit(1)
        except socket.error as e:
            print("")
        else:
            if len(msg) == 0:
                print('shutdown')
                #sys.exit(0)
            else:
                for b in msg:
                    print(hex(b) + " ", end='',flush=True)
                print('\n')

                #print('data: ' + msg)

#if __name__ == '__main__': main()
