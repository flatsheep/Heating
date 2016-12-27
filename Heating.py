import threading
import queue
import json
from HeatingManager import SocketClientThread, TCPThreadedServer, HeatingManager
from heating_web import HeatingWeb
import datetime
import schedule
import socket
import sys
import HeatingLogger

heatinglist = [bytearray([0x01, 0x29, 0x00, 0x2A]),
               bytearray([0x02, 0x26, 0x00, 0x28]),
               bytearray([0x03, 0x26, 0x00, 0x29]),
               bytearray([0x04, 0x26, 0x00, 0x2A]),
               bytearray([0x05, 0x26, 0x00, 0x2B]),
               bytearray([0x06, 0x26, 0x00, 0x2C]),
               bytearray([0x07, 0x26, 0x00, 0x2D]),
               bytearray([0x08, 0x26, 0x00, 0x2E]),
               bytearray([0x09, 0x26, 0x00, 0x2F]),
               bytearray([0x0A, 0x26, 0x00, 0x30]),
               bytearray([0x0B, 0x26, 0x00, 0x31]),
               bytearray([0x0C, 0x26, 0x00, 0x32])]

heating = None

def main():
    # Set everything up
    global heating

    schedule.every(5).minutes.do(LogHeating)

    #HeatingLogger.Log(1, 'settemp', '20', '15', 'from heating manager')

    heating_in_q = queue.Queue()
    heating_out_q = queue.Queue()
    heatingweb_in_q = queue.Queue()
    heatingweb_out_q = queue.Queue()

    # start the web socket
    heating_web_thread = threading.Thread(target=HeatingWeb, args=(heatingweb_in_q, heatingweb_out_q))
    heating_web_thread.start()

    # start the heating listener
    TCPServer = TCPThreadedServer(2626)
    TCPServer.setDaemon(True)
    TCPServer.start()

    heating = HeatingManager(heating_in_q, heating_out_q)

    sck = SocketClientThread(heating_in_q, heating_out_q)
    sck.start()

    conn = ("192.168.1.2", 8899)
    connectCommand = SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.CONNECT, conn)
    heating_in_q.put(connectCommand)

    for zone in heatinglist:
        heating_in_q.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.RECURRING, zone)))

    deferschedules = 4 # hate this, because message scheduling doesn't work well amongst queues

    #HeatingLogger.beginScheduler()

    while sck.alive.is_set():

        # receive from the web
        try:
            schedule.run_pending()

            htgmsg = heatingweb_out_q.get(True, 0.1)
            htgcmd = json.loads(htgmsg)

            # COMMANDS RECEIVED FROM THE WEB
            if htgcmd['command'] == 'zoneinfo':
                if htgcmd['zones'][0] == '*':
                    heatingweb_in_q.put(heating.asJSON(htgcmd['command']))
            elif htgcmd['command'] == 'zonegetschedule':
                json_wd = heating.zones[int(htgcmd['zoneid'])].schedule.asJSON(heating.zones[int(htgcmd['zoneid'])].scheduleraw_wd)
                json_we = heating.zones[int(htgcmd['zoneid'])].schedule.asJSON(heating.zones[int(htgcmd['zoneid'])].scheduleraw_we)

                json_wd = json_wd.replace('\"schedule\":', '')
                json_we = json_we.replace('\"schedule\":', '')
                heatingweb_in_q.put('{\"event\":\"schedule\",\"zone\":' + str(htgcmd['zoneid']) + ',\"schedules\":[' + json_wd + ',' + json_we + ']}')
            elif htgcmd['command'] == 'zonesettemp':
                heating.setZoneTemp(int(htgcmd['zoneid']), int(htgcmd['temp']))
            elif htgcmd['command'] == 'zonemode':
                heating.zones[int(htgcmd['zoneid'])].mode.set(int(htgcmd['keypadon']), int(htgcmd['keylockon']), int(htgcmd['frostmode']), int(htgcmd['hotwateron']))
            elif htgcmd['command'] == 'settimes':
                heating.setZoneTimes()
            elif htgcmd['command'] == 'zonerefreshallschedules':
                heating.getZoneSchedules()
            elif htgcmd['command'] == 'zonerefreshschedule':
                heating.getZoneSchedules(int(htgcmd['zoneid']))
            elif htgcmd['command'] == 'zonesetschedule':
                period = htgcmd.get('period')
                if period == None:
                    if datetime.datetime.today().weekday() in (5,6):
                        period = 'weekend'
                    else:
                        period = 'weekday'

                    heating.zones[int(htgcmd['zoneid'])].schedule.set(period, htgcmd['on1time'], int(htgcmd['on1temp']),
                                                                      htgcmd['off1time'], int(htgcmd['off1temp']),
                                                                      htgcmd['on2time'], int(htgcmd['on2temp']),
                                                                      htgcmd['off2time'], int(htgcmd['off2temp']))
                    heating.getZoneSchedules(int(htgcmd['zoneid']))
            elif htgcmd['command'] == 'zonesetheating':
                heating.zones[int(htgcmd['zoneid'])].setheating(htgcmd['heating'])



            #print(htgmsg)
            #heatingweb_in_q.put(htgmsg + ', back!', False)
        except queue.Empty as e:
            pass
        except ValueError as ve:
            # invalid json
            pass
        except AttributeError as ae:
            pass

        # process zone changes and transmit
        zonechanges = ''

        for zoneid, zonechange in heating.zones.items():
            if len(zonechange.change) > 0:
                zonechanges += '\"zone\":{\"number\":' + str(zoneid) + ',\"name\":\"' + str(zonechange.nameofzone) + '\", ' + zonechange.change + '}'
                zonechange.change = ''

        if len(zonechanges) > 0:
            zonechanges = '{\"event\":"changes", \"zones\":{' + zonechanges + '}}'
            heatingweb_in_q.put(zonechanges)
            zonechanges = ''

        try:
            newmsg = TCPServer.outQ.get(True, 0.1)
            #print("New command! " + newmsg)
            if newmsg == "QUIT\r\n": TCPServer.stopserver()
        except queue.Empty as e:
            pass

        try:
            msg = heating_out_q.get(True, 0.1)
            if msg.type == SocketClientThread.ClientReply.SUCCESS:
                if msg.data == "_initialised":
                    heatingweb_in_q.put('{\"event\":\"initialised\"}')
                    #heating.getZoneSchedules()
                    deferschedules -= 1
                elif msg.data:
                    #print("Mesage from socket Q:")
                    #for byt in msg.data:
                    heating.receiveData(msg.data)
                        #print(hex(byt), end='', flush=True)
                        #print(' ', end='', flush=True)
                    #print('')

                # this is temporary
                if deferschedules < 4 and deferschedules >= 1:
                    deferschedules -= 1
                elif deferschedules == 0:
                    heating.getZoneSchedules()
                    heating.getZoneHeating()
                    deferschedules = -1
            else:
                print("Error!")
        except queue.Empty as e:
            pass

    sck.join()

def LogHeating():
    HeatingLogger.LogHeating(heating)

if __name__ == '__main__': main()