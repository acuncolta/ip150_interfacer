import sys, os, json, requests, yaml
import urllib2
from core_functions import *
from parser import *
import random
import time
from time import sleep
from threading import Thread
from threading import Lock
from Queue import Queue
import thread
import globals;
from globals import *
from webserver import listen_http

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime
# import _thread

# Load config file
config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
try:
	with open(config_path, 'r') as file:
		config = yaml.load(file)
except:
	logmsg("Unable to load %s. Check the file exists and try again." % config_path)

paradoxUserCode = config["paradox"]["user_code"]
paradoxPassword = config["paradox"]["password"]
paradoxIP = config["paradox"]["ip_addr"]
paradoxPort = config["paradox"]["tcp_port"]
paradoxStatusInterval = config["paradox"]["status_interval"]
paradoxLoginMaxRetry = config["paradox"]["login_max_retry"]
paradoxLoginWaitTimeStart = config["paradox"]["login_wait_time_start"]
paradoxLoginWaitTimeMult = config["paradox"]["login_wait_time_mult"]
paradoxReadyWaitTime = config["paradox"]["ready_wait_time"]
# paradoxSleepTime = config["paradox"]["sleep_time"]
# paradoxStateCodes = config["paradox"]["state_codes"]
# paradoxDetOpenCodes = config["paradox"]["det_open_codes"]
# paradoxDetMemoryCodes = config["paradox"]["det_memory_codes"]
pushService = config["push"]["service"]
instapushAppID = config["push"]["instapush"]["appID"]
instapushAppSecret = config["push"]["instapush"]["appSecret"]
pushoverUserKey = config["push"]["pushover"]["userKey"]
pushoverAppToken = config["push"]["pushover"]["appToken"]
#KDB make sure sound is there for pushover, just in case an old config file is being used.
if "sound" in config["push"]["pushover"]:
	pushoverSound = config["push"]["pushover"]["sound"]
else:
	pushoverSound = "pushover"
iftttEventName = config["push"]["ifttt"]["eventName"]
iftttUserKey = config["push"]["ifttt"]["userKey"]
jeedomIP = config["push"]["jeedom"]["jeedomIP"]
jeedomDIY = config["push"]["jeedom"]["jeedomDIY"]
jeedomApiKey = config["push"]["jeedom"]["jeedomApiKey"]
jeedomZonesIDs = config["push"]["jeedom"]["jeedomZonesIDs"]
jeedomNbZones = len(jeedomZonesIDs)
jeedomAreasIDs = config["push"]["jeedom"]["jeedomAreasIDs"]
jeedomNbAreas = len(jeedomAreasIDs)
fromEmail = config["email"]["from"]
toEmail = config["email"]["to"]
smtpServer = config["email"]["server"]
subject = config["email"]["subject"]
text = config["email"]["text"]

def sendEmail(message):
	body = text.format(message)
	msg = "\r\n".join([
		"From: " + fromEmail,
		"To: " + toEmail,
		"Subject: " + subject,
		"",
		body
	])

	if (smtpServer == "gmail"):
		username = config["email"]["gmailUsername"]
		password = config["email"]["gmailPassword"]
		server = smtplib.SMTP('smtp.gmail.com:587')
		server.ehlo()
		server.starttls()
		server.login(username,password)
		server.sendmail(fromEmail, toEmail, msg)
		server.quit()
	elif (smtpServer == "localhost"):
		s = smtplib.SMTP("localhost")
		s.sendmail(fromEmail, toEmail, msg)
		s.quit()
		
	logmsg("Email sent to %s. Exiting script due to error." % toEmail)
	exit() # Exit Python since we have encountered an error. Added this in due to multiple emails being sent.


# Send Push Notification
def sendPushNotification(notifyType, notifyInfo):
	# Change verbiage based on event type
	value = 0
	type = 0
	if (notifyType == "zone_active"):
		zoneName = str(Zones[notifyInfo]["name"])
		event = config["zones"]["messages"]["start"].format(zoneName)
		type = 1
		value = 1
		
	elif (notifyType == "zone_idle"):
		zoneName = str(Zones[notifyInfo]["name"])
		event = config["zones"]["messages"]["stop"].format(zoneName)
		type = 1
		
	elif (notifyType == "area_active"):
		areaName = str(Areas[notifyInfo]["name"])
		event = config["areas"]["messages"]["start"].format(areaName)
		type = 2
		value = 1
		
	elif (notifyType == "area_idle"):
		areaName = str(Areas[notifyInfo]["name"])
		event = config["areas"]["messages"]["stop"].format(areaName)
		type = 2
	else:
		event = notifyType  # just use the notify type - for simple messaging
	
	if (pushService == "instapush"):
		headers = {'Content-Type': 'application/json',
						'x-instapush-appid': instapushAppID,
						'x-instapush-appsecret': instapushAppSecret}
		payload = '{"event":"message","trackers":{"message":"' + event + '"}}'
					   
		ret = requests.post('http://api.instapush.im/post',
						headers = headers,
						data = payload)
		logmsg("Notification sent to %s. Message: %s. Return message: %s" % (pushService, event, ret))
		#print ret
	
	elif (pushService == "pushover"):
		payload = {
                "token": pushoverAppToken,
                "user" : pushoverUserKey,
                "sound": pushoverSound,
                "message": event }
		ret = requests.post("http://api.pushover.net/1/messages.json", data = payload)
		logmsg("Notification sent to %s. Message: %s. Return message: %s" % (pushService, event, ret))
		#print ret
		
	elif (pushService == "ifttt"):
		url = "http://maker.ifttt.com/trigger/" + iftttEventName + "/with/key/" + iftttUserKey
		payload = { 'value1': event }
		ret = requests.post(url, data = payload)
		logmsg("Notification sent to %s. Message: %s. Return message %s" % (pushService, event, ret))
		#print ret
		
	elif (pushService == "jeedom"):
		if (type == 1): 
		        if notifyInfo < jeedomNbZones:
			      jeedomCmdId = jeedomZonesIDs[notifyInfo]
		        else:
			      error = "Unable to send notification as the configured number of zones does not match Paradox information."
			      logmsg(error)
			      sendEmail(error)
			      return
		elif (type == 2): 
		        if notifyInfo < jeedomNbAreas:
			      jeedomCmdId = jeedomAreasIDs[notifyInfo]
		        else:
			      error = "Unable to send notification as the configured number of areas does not match Paradox information."
			      logmsg(error)
			      sendEmail(error)
			      return
		else:
			logmsg("No notification to be sent to %s." % (pushService))
			return
		
		url =  "http://" + jeedomIP + jeedomDIY + "/core/api/jeeApi.php?apikey=" + jeedomApiKey + "&type=virtual&id=" + str(jeedomCmdId) + "&value=" + str(value)
		ret = requests.post(url)
		logmsg("Notification sent to %s. URL: %s. Return message %s" % (pushService, url, ret))
		#print ret


def paradox_connector():
	global Zones
	global Areas
	a = 1
	queue = Queue()
	mutex = Lock()

	if globals.Verbose:
		logmsg("* <INTERFACER> : VERBOSE mode activated")

	#web_thread = Thread(target = listen_http, args = (queue, ))

	logmsg("* <INTERFACER> : Logging in to IP150...")
	loop_connect()

	logmsg("* <INTERFACER> : Launching keep alive thread...")
	thread.start_new_thread(keep_alive, ())

	logmsg("* <INTERFACER> : Retrieving equipment...")
	equipment = get_equipment()
	if not equipment:
		raise ValueError('Error while retrieving equipment informations')
	Zones = equipment[0]
	Areas = equipment[1]
        if globals.Verbose:
                logmsg("* <INTERFACER> : Zones = %s" % Zones)
                logmsg("* <INTERFACER> : Areas = %s" % Areas)
        
        for i in range(0, jeedomNbZones):
		if (pushService == "jeedom"):
			url =  "http://" + jeedomIP + jeedomDIY + "/core/api/jeeApi.php?apikey=" + jeedomApiKey + "&type=cmd&id=" + str(jeedomZonesIDs[i])
			ret = requests.post(url)
			if globals.Verbose:
				logmsg("Request sent to %s to initialise zones status. URL: %s. Return message %s" % (pushService, url, ret))
			Zones[i]["status"] = int(ret.text)
		else:
			Zones[i]["status"] = 0
	
	for i in range(0, jeedomNbAreas):
		if (pushService == "jeedom"):
			url =  "http://" + jeedomIP + jeedomDIY + "/core/api/jeeApi.php?apikey=" + jeedomApiKey + "&type=cmd&id=" + str(jeedomAreasIDs[i])
			ret = requests.post(url)
			if globals.Verbose:
				logmsg("Request sent to %s to initialise areas status. URL: %s. Return message %s" % (pushService, url, ret))
			Areas[i]["armed"] = int(ret.text) + 1
		else:
			Areas[i]["armed"] = 1
			
	# Launch web server
	if globals.Webserver:
		logmsg("* <INTERFACER> : Starting HTTP Server")
	        th = Thread(target=listen_http, args=(queue,mutex))
	        th.start()

	# Loop update
	i = 0
	while (1):
		a = update_status(queue, mutex)
		time.sleep(paradoxStatusInterval)

	logmsg("* <INTERFACER> : Logging out of IP150...")
	logout()

def do_request(location):
	html = urllib2.urlopen("http://" + paradoxIP + ":" + str(paradoxPort) + "/" + location).read()
	if globals.Verbose:
		logmsg("* <INTERFACER> : Making request to /%s" % location)
		# print html
	return html

def get_status():
	return {"test":"1"}

def arm():
	do_request("statuslive.html?area=00&value=r")

def desarm():
	do_request("statuslive.html?area=00&value=d")

def partiel():
	do_request("statuslive.html?area=00&value=s")

def login():
	html = do_request("login_page.html")
	js = js_from_html(html)
	logmsg("* <INTERFACER> : Looking for someone connected...")
	if someone_connected(js):
		raise ValueError('Unable to login : someone is already connected')
	ses = parse_ses(js)
	if ses == False:
		raise ValueError('Unable to login : No SES value found')
	logmsg("* <INTERFACER> : SES Value found, encrypting credentials...")
	credentials = login_encrypt(ses, paradoxUserCode, paradoxPassword)
	logmsg("* <INTERFACER> : Sending auth request...")
	html = do_request("default.html?u=" + str(credentials['user']) + "&p=" + str(credentials['password']))

def logout():
	do_request("logout.html")

def loop_connect():
	retry 	= True
	i 		= 0
	while retry: 
		try:
			login()
			retry = False
		except:
			i += 1
			if (i < paradoxLoginMaxRetry):
				logmsg("* <INTERFACER> : Unable to login, someone is probably already connected, waiting %s seconds before retring..." % str(paradoxLoginWaitTimeStart * paradoxLoginWaitTimeMult * i))
				time.sleep(paradoxLoginWaitTimeStart * paradoxLoginWaitTimeMult * i)
			else:
				logmsg("* <INTERFACER> : /!\ Sorry, %s login failure, I will stop now..." % str(i))
				raise ValueError('Unable to login after ' + str(i) + ' attempts.')
	retry = True
	while retry:
		try:
			do_request("index.html")
			logmsg("* <INTERFACER> : Seems ready.")
			retry = False
		except:
			logmsg("* <INTERFACER> : Not yet ready...")
		time.sleep(paradoxReadyWaitTime)


def get_status():
	html = do_request("statuslive.html")
	js = js_from_html(html)
	return parse_status(js)

def get_equipment():
	html = do_request("index.html")
	js = js_from_html(html)
	return parse_equipment(js)

def keep_alive():
	while (1):
		#generate random id
		rand = random.randint(1000000000000000,9999999999999999)
		#print "* <INTERFACER> : <<< KEEP ALIVE : msgid=1&" + str(rand) + " >>>"
		do_request("keep_alive.html?msgid=1&" + str(rand))
		time.sleep(2.5)

def update_status(queue, mutex):
	global Zones
	global Areas

	#print "* <INTERFACER> : Retrieving status"
	status = get_status()
	if not status:
		raise ValueError('Error while retrieving status informations')
	alarm_states = status[1]
	zones_status = status[0]
	if globals.Verbose:
                logmsg("* <INTERFACER> : Alarm States = %s" % alarm_states)
                logmsg("* <INTERFACER> : Zones Status = %s" % zones_status)
	if len(zones_status) == len(Zones):
		#print "* <INTERFACER> : All okay, updating status"
		for i in range(0, len(zones_status)):
						
			if Zones[i]["status"] != zones_status[i]:
				Zones[i]["status"] = zones_status[i]	
				
				if Zones[i]["status"] == 0 and config["zones"]["notify"]["stop"] == "yes":
					logmsg("Zone has gone idle: %s" % i)
					sendPushNotification("zone_idle", i)
					
				elif config["zones"]["notify"]["start"] == "yes":
					logmsg("Zone has gone active: %s" % i)
					sendPushNotification("zone_active", i)
	else:
		logmsg("* <INTERFACER> : /!\ Erf, status (%s) != zones (%s)..." % (str(len(zones_status)), str(len(Zones))))

	if len(alarm_states) == len(Areas):
		#print "* <INTERFACER> : All okay, updating states"
		for i in range(0, len(alarm_states)):
						
			if Areas[i]["armed"] != alarm_states[i]:
				Areas[i]["armed"] = alarm_states[i]
			
				if Areas[i]["armed"] == 1 and config["areas"]["notify"]["stop"] == "yes":
					logmsg("Area has gone idle: %s" % i)
					sendPushNotification("area_idle", i)
					
				elif Areas[i]["armed"] == 2 and config["areas"]["notify"]["start"] == "yes":
					logmsg("Area has gone active: %s" % i)
					sendPushNotification("area_active", i)
						
		mutex.acquire()
		if not queue.empty():
			#print "* <INTERFACER> : Clearing the queue..."
			queue.queue.clear()
		#print "* <INTERFACER> : Putting updates in queue..."
		queue.put((Zones,Areas))
		mutex.release()
	else:
		logmsg("* <INTERFACER> : /!\ Erf, states (%s) != areas (%s)..." % (str(len(states)), str(len(Areas))))


