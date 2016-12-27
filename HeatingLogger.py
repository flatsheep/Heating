from pymysql import connect, err, sys, cursors
import Heating

LOG_DB = 'Heating'
LOG_USER = 'root'
LOG_PWD = 'raspberry'
LOG_QUERY = 'SELECT * FROM HeatingLog'
LOG_CMD_ADD = 'AddLog'

db = None
cur = None

def connectDB():
    global db, cur
    db = connect(host='localhost', user=LOG_USER, passwd=LOG_PWD, database=LOG_DB, autocommit=True)
    cur = db.cursor()

def Log(zoneID, what, was, now, data):
    if db == None:
        connectDB()

    cur.callproc(LOG_CMD_ADD, [zoneID, what, was, now, data])

def LogHeating(heating):
    if db == None:
        connectDB()

    cur.execute('INSERT INTO zonelog (HeatingJSON) VALUES (\'' + heating.asJSON('log') + '\')')
