from SimpleWebSocketServer import WebSocket, SimpleWebSocketServer
import socket

def HeatingWeb(inQ, outQ):
    ipaddress = socket.gethostbyname(socket.getfqdn())

    print('beginning HeatingWeb')
    hw_server = SimpleWebSocketServer(ipaddress, 8080, HeatingWebHandler)
    hw_server.outq = outQ
    hw_server.inq = inQ
    hw_server.serveforever()

class HeatingWebHandler(WebSocket):

    def handleConnected(self):
      pass

    def handleClose(self):
      pass