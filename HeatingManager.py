import threading
import math
import datetime
import queue
from time import sleep
import socket
import select
import binascii
#import HeatingLogger

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

class HeatingManager():

    CTR_COMMANDS = {81:{'id':0, 'command':1, 'type':2, 'day':3, 'hour':4, 'minute':5, 'act-temp':6, 'status':8, 'set-temp':9, 'frost-temp':10, 'unit':14, 'checksum':15},
                    82:{'id':0, 'command':1, 'type':2, 'day':3, 'hour':4, 'minute':5, 'act-temp':6, 'status':8, 'set-temp':7, 'frost-temp':10, 'unit':14, 'checksum':15}}

    ZONE_NAMES = ['', 'Kitchen', 'Study', 'Hall', 'Lounge', 'Master Bedroom', 'Ensuite', 'Bathroom', 'Cats room', 'J Study', 'J&J', 'Guest room', 'Landing']

    SEND_COMMAND = bytearray([0x00,0xA6,0x51,0x00,0x00,0x00,0xFF,0x03,0x01,0x00,0x00,0x0A,0x00,0x00,0x1C,0x00])

    class zone():
        SCHEDULE_WEEKEND, SCHEDULE_WEEKDAY = range(2)

        def __init__(self, parent):
            self.zoneid = None
            self.type = None
            self.nameofzone = None
            self.actualtemperature = None
            self.settemperature = None
            self.frosttemperature = None
            self.day = None
            self.hour = None
            self.min = None
            self.status = None
            self.unit = None
            self.checksum = None
            self.raw = None
            self.parent = parent
            self.mode = self.modes(self)

            self.scheduleraw_wd = None
            self.scheduleraw_we = None
            self.schedule = self.schedules(self)

            self.heatingraw_wd = None
            self.heatingraw_we = None

            self.oldstatus = None
            self.oldactualtemperature = None
            self.oldsettemperature = None
            self.change = ''

        def updatefromdata(self, data):

            self.raw = data
            zonetype = data[HeatingManager.CTR_COMMANDS[81]['type']]
            self.type = zonetype
            self.zoneid = data[HeatingManager.CTR_COMMANDS[zonetype]['id']]
            self.nameofzone = HeatingManager.ZONE_NAMES[self.zoneid]
            self.actualtemperature = data[HeatingManager.CTR_COMMANDS[zonetype]['act-temp']]
            self.settemperature = data[HeatingManager.CTR_COMMANDS[zonetype]['set-temp']]
            self.frosttemperature = data[HeatingManager.CTR_COMMANDS[zonetype]['frost-temp']]
            self.status = data[HeatingManager.CTR_COMMANDS[zonetype]['status']]
            self.day = data[HeatingManager.CTR_COMMANDS[zonetype]['day']]
            self.hour = data[HeatingManager.CTR_COMMANDS[zonetype]['hour']]
            self.min = data[HeatingManager.CTR_COMMANDS[zonetype]['minute']]
            self.unit = data[HeatingManager.CTR_COMMANDS[zonetype]['unit']]
            self.checksum = data[HeatingManager.CTR_COMMANDS[zonetype]['checksum']]

            if self.oldstatus != None and self.change == '':
                if self.oldactualtemperature != self.actualtemperature:
                    self.change += '\"act-temp\":{\"was\":' + str(self.oldactualtemperature) + ', \"now\":' + str(self.actualtemperature) + '},'
                    #HeatingLogger.Log(self.zoneid, 'act-temp', str(self.oldactualtemperature), str(self.actualtemperature), '')
                if self.oldsettemperature != self.settemperature:
                    self.change += '\"set-temp\":{\"was\":' + str(self.oldsettemperature) + ', \"now\":' + str(self.settemperature) + '},'
                    #HeatingLogger.Log(self.zoneid, 'set-temp', str(self.oldsettemperature), str(self.settemperature), '')
                if self.oldstatus != self.status:
                    self.change += '\"status\":{\"was\":' + str(self.oldstatus) + ', \"now\":' + str(self.status) + '},' + self.mode.asJSON() + ','
                    #HeatingLogger.Log(self.zoneid, 'status', str(self.oldstatus), str(self.status), '')

                if len(self.change) > 0: self.change = self.change[:-1]

            self.oldstatus = self.status
            self.oldactualtemperature = self.actualtemperature
            self.oldsettemperature = self.settemperature

        def heatingJSON(self):
            if self.heatingraw_we != None and self.heatingraw_wd != None and self.type == 0x52:
                returnJSON = '{\"weekend\":{\"schedule1\":{\"on\":\"<we_s1on>\",\"off\":\"<we_s1off>\"},\"schedule2\":{\"on\":\"<we_s2on>\",\"off\":\"<we_s2off>\"},\"schedule3\":{\"on\":\"<we_s3on>\",\"off\":\"<we_s3off>\"},\"schedule4\":{\"on\":\"<we_s4on>\",\"off\":\"<we_s4off>\"}},'
                returnJSON += '\"weekday\":{\"schedule1\":{\"on\":\"<wd_s1on>\",\"off\":\"<wd_s1off>\"},\"schedule2\":{\"on\":\"<wd_s2on>\",\"off\":\"<wd_s2off>\"},\"schedule3\":{\"on\":\"<wd_s3on>\",\"off\":\"<wd_s3off>\"},\"schedule4\":{\"on\":\"<wd_s4on>\",\"off\":\"<wd_s4off>\"}}}'

                returnJSON = returnJSON.replace('<we_s1on>',str((self.heatingraw_we[3]-80)) + ':' + str((self.heatingraw_we[4]-80)))
                returnJSON = returnJSON.replace('<we_s1off>',str((self.heatingraw_we[5]-80)) + ':' + str((self.heatingraw_we[6]-80)))
                returnJSON = returnJSON.replace('<we_s2on>',str((self.heatingraw_we[7]-80)) + ':' + str((self.heatingraw_we[8]-80)))
                returnJSON = returnJSON.replace('<we_s2off>',str((self.heatingraw_we[9]-80)) + ':' + str((self.heatingraw_we[10]-80)))
                returnJSON = returnJSON.replace('<we_s3on>',str((self.heatingraw_we[11]-80)) + ':' + str((self.heatingraw_we[12]-80)))
                returnJSON = returnJSON.replace('<we_s3off>',str((self.heatingraw_we[13]-80)) + ':' + str((self.heatingraw_we[14]-80)))
                returnJSON = returnJSON.replace('<we_s4on>',str((self.heatingraw_we[15]-80)) + ':' + str((self.heatingraw_we[16]-80)))
                returnJSON = returnJSON.replace('<we_s4off>',str((self.heatingraw_we[17]-80)) + ':' + str((self.heatingraw_we[18]-80)))
                
                returnJSON = returnJSON.replace('<wd_s1on>',str((self.heatingraw_wd[3]-80)) + ':' + str((self.heatingraw_wd[4]-80)))
                returnJSON = returnJSON.replace('<wd_s1off>',str((self.heatingraw_wd[5]-80)) + ':' + str((self.heatingraw_wd[6]-80)))
                returnJSON = returnJSON.replace('<wd_s2on>',str((self.heatingraw_wd[7]-80)) + ':' + str((self.heatingraw_wd[8]-80)))
                returnJSON = returnJSON.replace('<wd_s2off>',str((self.heatingraw_wd[9]-80)) + ':' + str((self.heatingraw_wd[10]-80)))
                returnJSON = returnJSON.replace('<wd_s3on>',str((self.heatingraw_wd[11]-80)) + ':' + str((self.heatingraw_wd[12]-80)))
                returnJSON = returnJSON.replace('<wd_s3off>',str((self.heatingraw_wd[13]-80)) + ':' + str((self.heatingraw_wd[14]-80)))
                returnJSON = returnJSON.replace('<wd_s4on>',str((self.heatingraw_wd[15]-80)) + ':' + str((self.heatingraw_wd[16]-80)))
                returnJSON = returnJSON.replace('<wd_s4off>',str((self.heatingraw_wd[17]-80)) + ':' + str((self.heatingraw_wd[18]-80)))

                return  returnJSON
            else:
                return ''

        def createzonesetschedule(self, s1_on, s1_off, s1_temp, s2_on, s2_off, s2_temp):
            schedulebyte = None

            if datetime.datetime.today().weekday() in (5,6): # weekend
                if self.zoneid == 1:
                    schedulebyte = bytearray([self.zoneid, 0xcf, 0x52, (s1_on + 80), (s1_off + 80), (s1_temp + 80), (s2_on + 80), (s2_off + 80), (s2_temp + 80)])
                else:
                    schedulebyte = bytearray([self.zoneid, 0xd1, 0x51, (s1_on + 80), (s1_off + 80), (s1_temp + 80), (s2_on + 80), (s2_off + 80), (s2_temp + 80)])
            else:   # weekday
                if self.zoneid == 1:
                    schedulebyte = bytearray([self.zoneid, 0xce, 0x52, (s1_on + 80), (s1_off + 80), (s1_temp + 80), (s2_on + 80), (s2_off + 80), (s2_temp + 80)])
                else:
                    schedulebyte = bytearray([self.zoneid, 0xd0, 0x51, (s1_on + 80), (s1_off + 80), (s1_temp + 80), (s2_on + 80), (s2_off + 80), (s2_temp + 80)])

            checksum = self.calculateChecksum(schedulebyte)
            schedulebyte.append(checksum)
            return schedulebyte

        def receiveHeatingData(self, heatingdata):
            if heatingdata[2] == 0x51:
                self.heatingraw_wd = heatingdata
            elif heatingdata[2] == 0x52:
                self.heatingraw_we = heatingdata

        def createzonegetheating(self, schedulePeriod):
            schedulebyte = None
            if schedulePeriod == HeatingManager.zone.SCHEDULE_WEEKDAY:
                schedulebyte = bytearray([self.zoneid, 0x50, 0x52])
            elif schedulePeriod == HeatingManager.zone.SCHEDULE_WEEKEND:
                schedulebyte = bytearray([self.zoneid, 0x51, 0x52])

            checksum = self.calculateChecksum(schedulebyte)
            schedulebyte.append(checksum)
            return schedulebyte

        def createzonegetschedule(self, schedulePeriod):
            schedulebyte = None

            if schedulePeriod == HeatingManager.zone.SCHEDULE_WEEKEND:  # weekend
                if self.zoneid == 1:
                    schedulebyte = bytearray([self.zoneid, 0x4f, 0x52])
                else:
                    schedulebyte = bytearray([self.zoneid, 0x4f, 0x51])
            else:
                if self.zoneid == 1:
                    schedulebyte = bytearray([self.zoneid, 0x4e, 0x52])
                else:
                    schedulebyte = bytearray([self.zoneid, 0x4e, 0x51])

            checksum = self.calculateChecksum(schedulebyte)
            schedulebyte.append(checksum)
            return schedulebyte

        def calculateChecksum(self, thebytes):
            chksum = 0

            # for(int i = 0; i < length; i++)
            for i in thebytes:
                chksum = chksum + i
                #print("hex: " + hex(i), end=None)
                #print("dec: " + str(i))

            if chksum > 256:
                return chksum - (math.floor(chksum / 256.0) * 256)
            else:
                return chksum

        def setheating(self, heatingJSON):
            for period in ('weekday', 'weekend'):
                heatingraw = bytearray([0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0])
    
                if period == 'weekday':
                    setcommand = 0xd0
                else:
                    setcommand = 0xd1
    
                heatingraw[0] = self.zoneid
                heatingraw[1] = setcommand
                heatingraw[2] = self.type
                heatingraw[3] = int(heatingJSON[period]['schedule1']['on'].split(":")[0]) + 80
                heatingraw[4] = int(heatingJSON[period]['schedule1']['on'].split(":")[1]) + 80
                heatingraw[5] = int(heatingJSON[period]['schedule1']['off'].split(":")[0]) + 80
                heatingraw[6] = int(heatingJSON[period]['schedule1']['off'].split(":")[1]) + 80
                heatingraw[7] = int(heatingJSON[period]['schedule2']['on'].split(":")[0]) + 80
                heatingraw[8] = int(heatingJSON[period]['schedule2']['on'].split(":")[1]) + 80
                heatingraw[9] = int(heatingJSON[period]['schedule2']['off'].split(":")[0]) + 80
                heatingraw[10] = int(heatingJSON[period]['schedule2']['off'].split(":")[1]) + 80
                heatingraw[11] = int(heatingJSON[period]['schedule3']['on'].split(":")[0]) + 80
                heatingraw[12] = int(heatingJSON[period]['schedule3']['on'].split(":")[1]) + 80
                heatingraw[13] = int(heatingJSON[period]['schedule3']['off'].split(":")[0]) + 80
                heatingraw[14] = int(heatingJSON[period]['schedule3']['off'].split(":")[1]) + 80
                heatingraw[15] = int(heatingJSON[period]['schedule4']['on'].split(":")[0]) + 80
                heatingraw[16] = int(heatingJSON[period]['schedule4']['on'].split(":")[1]) + 80
                heatingraw[17] = int(heatingJSON[period]['schedule4']['off'].split(":")[0]) + 80
                heatingraw[18] = int(heatingJSON[period]['schedule4']['off'].split(":")[1]) + 80
                heatingraw[19] = self.calculateChecksum(heatingraw)
                self.parent.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, heatingraw)))
                
            
        class schedules():
            def __init__(self, parent, scheduleSelect = None):
                self.parent = parent

                self.refresh(scheduleSelect)

            def refresh(self, scheduleSelect = None):
                if scheduleSelect ==  None:
                    if datetime.datetime.today().day in (5,6):
                        self.scheduleraw = self.parent.scheduleraw_we
                    else:
                        self.scheduleraw = self.parent.scheduleraw_wd
                else:
                    self.scheduleraw = scheduleSelect

            def period(self):
                if self.scheduleraw[1] == 0x4f:
                    return 'weekend'
                else:
                    return 'weekday'

            def on1hour(self):
                return self.scheduleraw[3] - 80

            def on1minute(self):
                mins = str(self.scheduleraw[4] - 80)
                if len(mins) == 1: mins =  '0' + mins
                return mins

            def on1temp(self):
                return self.scheduleraw[5] - 80

            def off1hour(self):
                return  self.scheduleraw[6] - 80

            def off1minute(self):
                mins = str(self.scheduleraw[4] - 80)
                if len(mins) == 1: mins = '0' + mins
                return mins

            def off1temp(self):
                return self.scheduleraw[8] - 80

            def on2hour(self):
                return self.scheduleraw[9] - 80

            def on2minute(self):
                mins = str(self.scheduleraw[4] - 80)
                if len(mins) == 1: mins = '0' + mins
                return mins

            def on2temp(self):
                return self.scheduleraw[11] - 80

            def off2hour(self):
                return self.scheduleraw[12] - 80

            def off2minute(self):
                mins = str(self.scheduleraw[4] - 80)
                if len(mins) == 1: mins = '0' + mins
                return mins

            def off2temp(self):
                return self.scheduleraw[14] - 80

            def set(self, period, on1time, on1temp, off1time, off1temp, on2time, on2temp, off2time, off2temp):
                scheduleset = bytearray([0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0])

                scheduleset[0] = self.parent.zoneid

                if period == 'weekend':  # weekend
                    scheduleset[1] = 0xcf
                else:
                    scheduleset[1] = 0xce

                if self.parent.zoneid == 1:
                    scheduleset[2] = 0x52
                else:
                    scheduleset[2] = 0x51

                scheduleset[3] = int(on1time.split(':')[0]) + 80
                scheduleset[4] = int(on1time.split(':')[1]) + 80
                scheduleset[5] = on1temp + 80
                scheduleset[6] = int(off1time.split(':')[0]) + 80
                scheduleset[7] = int(off1time.split(':')[1]) + 80
                scheduleset[8] = off1temp + 80
                scheduleset[9] = int(on2time.split(':')[0]) + 80
                scheduleset[10] = int(on2time.split(':')[1]) + 80
                scheduleset[11] = on2temp + 80
                scheduleset[12] = int(off2time.split(':')[0]) + 80
                scheduleset[13] = int(off2time.split(':')[1]) + 80
                scheduleset[14] = off2temp + 80
                scheduleset[15] = self.parent.calculateChecksum(scheduleset)

                self.parent.parent.sendZoneSchedule(scheduleset)


            def asJSON(self, ouputraw = None):

                tempraw = None

                if ouputraw != None:
                    tempraw = self.scheduleraw
                    self.scheduleraw = ouputraw

                if self.scheduleraw == None: return '\"schedules\":\"loading\"'
                toreturn = '\"schedule\":{\"period\":\"' + self.period() + '\",\"on1time\":\"' + str(self.on1hour()) + ':' + str(self.on1minute()) + '\",\"on1temp\":' + str(self.on1temp()) + ',\"off1time\":\"' + str(self.off1hour()) + ':' + str(self.off1minute()) + '\",\"off1temp\":' + str(self.off1temp()) + ',' + \
                                     '\"on2time\":\"' + str(self.on2hour()) + ':' + str(self.on2minute()) + '\",\"on2temp\":' + str(self.on2temp()) + ',\"off2time\":\"' + str(self.off2hour()) + ':' + str(self.off2minute()) + '\",\"off2temp\":' + str(self.off2temp()) + '}'

                if tempraw != None: self.scheduleraw = tempraw
                tempraw = None
                return toreturn

        class modes():
            def __init__(self, parent):
                self.parent = parent

            def keypadon(self):
                return (self.parent.status & 128) >> 7

            def keylock(self):
                return (self.parent.status & 64) >> 6

            def frostmode(self):
                return (self.parent.status & 32) >> 5

            def heatingon(self):
                return (self.parent.status & 16) >> 4

            def hotwater(self):
                return (self.parent.status & 8) >> 3

            def set(self, keypadon = True, keylockon = False, frostmode = False, hotwateron = False):
                self.parent.status = 254 & ((keypadon * 128) + (keylockon * 64) + (frostmode * 32) + (self.heatingon() * 16) + (hotwateron * 12) + 2)
                self.parent.parent.sendZone(self.parent.zoneid)

            def asJSON(self):
                return '\"modes\":{\"keypadon\":' + str(self.keypadon()) + ',\"keylock\":' + str(self.keylock()) + ',\"frostmode\":' + str(self.frostmode()) + ',\"heatingon\":' + str(self.heatingon()) + ',\"hotwater\":' + str(self.hotwater()) + '}'

    def __init__(self, inQ, outQ):
        self.zones = {}
        self.inQ = inQ
        self.outQ = outQ

    def setZoneTimes(self):
        for eachZone in self.zones:
            self.sendZone(eachZone.zoneid)

    def receiveData(self, data):
        thezone = None

        #for d in data:
        #    print(str(d) + ' ', end='')
        #print('')

        if len(data) == 16:
            #print(str(data[0]) + " : " + str(data[1]))
            if data[1] == 38 or data[1] == 41:
                if data[0] in self.zones:
                    thezone = self.zones[data[0]]
                else:
                    thezone = HeatingManager.zone(self)
                    self.zones[data[0]] = thezone

                thezone.updatefromdata(data)
            elif data[1] == 78:
                thezone = self.zones[data[0]]
                thezone.scheduleraw_wd = data
                thezone.schedule.refresh()
            elif data[1] == 79:
                thezone = self.zones[data[0]]
                thezone.scheduleraw_we = data
                thezone.schedule.refresh()
        elif len(data) == 20:
            thezone = self.zones[data[0]]
            if data[1] == 0x50:
                thezone.heatingraw_wd = data
            elif data[1] == 0x51:
                thezone.heatingraw_we = data


        elif len(data) == 4:
            if data[1] in (0x50,0x51):
                self.getZoneHeating(data[1])
            else:
                self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND,(SocketClientThread.ClientCommand.ONETIME, heatinglist[data[0]-1])))


        #elif len(data) == 20:
            #print('response from command    ')

    def sendZoneSchedule(self, commandtosend):
        self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, commandtosend)))

    def sendZone(self, zoneToSend):
        theZone = self.zones[zoneToSend]
        zoneCMD = HeatingManager.SEND_COMMAND[:]
        zoneCMD[0] = theZone.zoneid #zone id
        zoneCMD[3] = datetime.datetime.today().weekday() + 1
        zoneCMD[4] = datetime.datetime.today().hour
        zoneCMD[5] = datetime.datetime.today().minute

        if theZone.type == 81:
            zoneCMD[1] = 166 #a6
            zoneCMD[2] = 81
            zoneCMD[9] = theZone.status
            zoneCMD[10] = theZone.settemperature
            zoneCMD[11] = theZone.frosttemperature
        else:
            zoneCMD[1] = 169 #a9
            zoneCMD[2]= 82
            zoneCMD[9] = theZone.actualtemperature
            zoneCMD[8] = theZone.status
            zoneCMD[7] = theZone.settemperature
            zoneCMD[10] = theZone.frosttemperature

        zoneCMD[15] = theZone.calculateChecksum(zoneCMD)

        self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, zoneCMD)))

    def setZoneTemp(self, zoneid, temp):
        thezone = self.zones[zoneid]
        thezone.settemperature = temp
        self.sendZone(zoneid)

    def getZoneSchedules(self, zoneid = None):
        if zoneid != None:
            self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, self.zones[zoneid].createzonegetschedule(HeatingManager.zone.SCHEDULE_WEEKDAY))))
            self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, self.zones[zoneid].createzonegetschedule(HeatingManager.zone.SCHEDULE_WEEKEND))))
        else:
            for azone in self.zones:
                self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, self.zones[azone].createzonegetschedule(HeatingManager.zone.SCHEDULE_WEEKDAY))))
                self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, self.zones[azone].createzonegetschedule(HeatingManager.zone.SCHEDULE_WEEKEND))))

    def getZoneHeating(self, whichtype = None):
        for azone in self.zones:
            if self.zones[azone].type == 0x52:
                if whichtype == None:
                    self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, self.zones[azone].createzonegetheating(HeatingManager.zone.SCHEDULE_WEEKDAY))))
                    self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, self.zones[azone].createzonegetheating(HeatingManager.zone.SCHEDULE_WEEKEND))))
                else:
                    if whichtype == 0x50:
                        self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, self.zones[azone].createzonegetheating(HeatingManager.zone.SCHEDULE_WEEKDAY))))
                    else:
                        self.inQ.put(SocketClientThread.ClientCommand(SocketClientThread.ClientCommand.SEND, (SocketClientThread.ClientCommand.ONETIME, self.zones[azone].createzonegetheating(HeatingManager.zone.SCHEDULE_WEEKEND))))

    def asJSON(self, command):
        heatingJSON = ''

        return_json = '{\"event\":\"' + command + '\",\"zones\":{'
        for k, azone in self.zones.items():

            heatingJSON = azone.heatingJSON()

            if len(heatingJSON) > 0:
                heatingJSON = ', \"heating\":' + heatingJSON

            return_json += '\"' + str(azone.zoneid) + '\":{\"zoneid\":' + str(azone.zoneid) + \
                                                    ', \"zonename\":\"' + HeatingManager.ZONE_NAMES[azone.zoneid] + '\"' + \
                                                    ', \"day\":' + str(azone.day) + \
                                                    ', \"hour\":' + str(azone.hour) + \
                                                    ', \"min\":' + str(azone.min) + \
                                                    ', \"unit\":' + str(azone.unit) + \
                                                    ', \"checksum\":' + str(azone.checksum) + \
                                                    ', \"status\":' + str(azone.status) + \
                                                    ', \"frosttemp\":' + str(azone.frosttemperature) + \
                                                    ', \"settemp\":' + str(azone.settemperature) + \
                                                    ', \"acttemp\":' + str(azone.actualtemperature) + \
                                                    ',' + azone.mode.asJSON() + \
                                                    ',' + azone.schedule.asJSON() + \
                                                    heatingJSON + \
                                                    '},'
        return_json = return_json[:-1]
        return_json += '}}'
        return return_json

class SocketClientThread(threading.Thread):
    """ Implements the threading.Thread interface (start, join, etc.) and
        can be controlled via the cmd_q Queue attribute. Replies are
        placed in the reply_q Queue attribute.
    """

    class ClientCommand(object):
        """ A command to the client thread.
            Each command type has its associated data:

            CONNECT:    (host, port) tuple
            SEND:       Data string
            CLOSE:      None
        """
        CONNECT, SEND, RECEIVE, CLOSE = range(4)
        RECURRING, ONETIME = range(2)

        def __init__(self, type, data=None):
            self.type = type
            self.data = data

    class ClientReply(object):
        """ A reply from the client thread.
            Each reply type has its associated data:

            ERROR:      The error string
            SUCCESS:    Depends on the command - for RECEIVE it's the received
                        data string, for others None.
        """
        ERROR, SUCCESS = range(2)

        def __init__(self, type, data=None):
            self.type = type
            self.data = data

    def __init__(self, cmd_q=None, reply_q=None):
        super(SocketClientThread, self).__init__()
        self.cmd_q = cmd_q or queue.Queue()
        self.reply_q = reply_q or queue.Queue()
        self.alive = threading.Event()
        self.alive.set()
        self.socket = None
        self.ip = None
        self.port = 0
        self.initialised = False

        self._recurringSendStack = []
        self._onetimeSendStack = queue.Queue()

        self.handlers = {
            SocketClientThread.ClientCommand.CONNECT: self._handle_CONNECT,
            SocketClientThread.ClientCommand.CLOSE: self._handle_CLOSE,
            SocketClientThread.ClientCommand.SEND: self._handle_SEND
        }

    def run(self):
        recurringindex = 0
        fromsocket = ''
        maxrecurring = 999

        while self.alive.isSet():
            # if there is a message on the Q, process it
            try:
                cmd = self.cmd_q.get(True, 0.1)
                self.handlers[cmd.type](cmd)
            except queue.Empty as e:
                pass

            # send any one off messages waiting
            try:
                onetimemsg = self._onetimeSendStack.get(True, 0.1)
                self.socket.send(onetimemsg)
                print('One time msg: ', end='')
                for byt in onetimemsg:
                    print(hex(byt), end='', flush=True)
                    print(' ', end='', flush=True)
                print('')
                sleep(0.6) # allow time for the message to be broadcast
            except queue.Empty as e:
                pass

            # keep cycling through the recurring messages to be transmitted on the socket
            if len(self._recurringSendStack) > 0:
                self.socket.send(self._recurringSendStack[recurringindex])
                sleep(0.6) # allow time for the message to be broadcast

                recurringindex += 1
                if recurringindex == 12: # TODO fix this> (len(self._recurringSendStack) - 1)):
                    #maxrecurring = recurringindex
                    recurringindex = 0

                    if not self.initialised:
                        self.initialised = True
                        self.reply_q.put(self._success_reply("_initialised"))

            #if len(self._recurringSendStack) > maxrecurring : del self._recurringSendStack[0]

            # try to receive from the socket
            try:
                fromsocket = self.socket.recv(1024)
            except socket.timeout as e:
                pass

            if fromsocket != '':
                buffer = []
                buffcount = 0

                # parses the received data, every 3th byte is tries to see if it has a complete message by calculating the buffer
                # checksum, if is fails, it keeps receiving and appending to the buffer, otherwise it send the command and resets the buffer.
                for byt in fromsocket:
                    buffer.append(byt)
                    buffcount += 1

                    if buffcount == 4:
                        buffcount = 0
                        # print('checksum: ' + str(HeatingManager.zone.calculateChecksum(None, buffer[:-1])) + ' 4th bit= ' + str(buffer[-1]))
                        if HeatingManager.zone.calculateChecksum(None, buffer[:-1]) == buffer[-1] and (len(buffer) == 4 or len(buffer) == 16  or len(buffer) == 20):
                            #for buf in buffer:
                            #    print(hex(buf), end=' ')
                            #print('')
                            self.reply_q.put(self._success_reply(buffer))
                            buffer = []

            fromsocket = ''

    def join(self, timeout=None):
        self.alive.clear()
        threading.Thread.join(self, timeout)

    def _handle_CONNECT(self, cmd):
        try:
            print("connecting...")
            self.ip = cmd.data[0]
            self.port = cmd.data[1]
            self.socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((cmd.data[0], cmd.data[1]))
            self.socket.settimeout(2)
            self.reply_q.put(self._success_reply())
            print("connected")
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))

    def _handle_CLOSE(self, cmd):
        self.socket.close()
        reply = SocketClientThread.ClientReply(SocketClientThread.ClientReply.SUCCESS)
        self.reply_q.put(reply)

    def _handle_SEND(self, cmd):
        try:
            if(cmd.data[0] == SocketClientThread.ClientCommand.ONETIME):
                self._onetimeSendStack.put(cmd.data[1])
                self.reply_q.put(self._success_reply())
            else:
                self._recurringSendStack.append(cmd.data[1])
                self.reply_q.put(self._success_reply())
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))


    def _error_reply(self, errstr):
        return SocketClientThread.ClientReply(SocketClientThread.ClientReply.ERROR, errstr)

    def _success_reply(self, data=None):
        return SocketClientThread.ClientReply(SocketClientThread.ClientReply.SUCCESS, data)

TCPServerCommand = ""   # TCP: TCP command buffer (after succesfully decoding the input data stream)


class TCPThreadedServer(threading.Thread):
   def __init__(self, TCPPort):
       threading.Thread.__init__(self)
       self.TCPPort = TCPPort
       self.stopflag = 0
       self.outQ = queue.Queue()
       self.inQ = queue.Queue()

   def run(self):
      buffer = ""
      receivedData = ""

      #Standard TCP socket
      server = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
      server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
      ipaddress = socket.gethostbyname(socket.getfqdn())

      # by using an empty string we are saying any you could also use
      # localhost or socket.gethostname() if you want to expose the server
      # past your network granted you have the correct ports fowarded
      server.bind(("",self.TCPPort))

      # tell the socket to listen for incoming connections
      server.listen(2)

      # tell the socket not to block while waiting for connections
      server.setblocking(False)
      input = [server]

      while not(self.stopflag):
         input_ready,output_ready,errors = select.select(input, [], [])
         for sock in input_ready:
            if sock is server:
                  client,address = sock.accept()
                  print("Accepting socket from",address[0])
                  input.append(client)
            else:
               receivedData = sock.recv(2048)
               if receivedData:
                    # Check the receivedData
                    buffer = str(receivedData)
                    # Copy the valid command into the global buffer
                    self.outQ.put(buffer)
                    # Send back ACK to client
                    sock.send(b'OK\r\n')
                    # Check if is a termination request
                    if (buffer == "QUIT\r\n"):
                        sock.close()
                        input.remove(sock)
                        self.stopflag = 1
               else:
                  sock.close()
                  input.remove(sock)
                  print("Dropped connection",address[0])

            try:
                inmsg = self.inQ.get(True, 0.1)
                sock.send(inmsg)
            except queue.Empty as e:
                pass

      print ("Exit from run")
      return

   def stopserver(self):
      print ("(quitthread) Server shutdown!")
      self.stopflag = 1
      return