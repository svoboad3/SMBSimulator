import os
import threading
import time
import json
import random
import string
import flask_login
from flask import Flask, flash, request, redirect, url_for, send_file, render_template
from SMB.MultipleComps.SMBStation import SMBStation
from SMB.MultipleComps.LinColumn import LinColumn
from SMB.MultipleComps.NonlinColumn import NonLinColumn
from SMB.MultipleComps.Tube import Tube
import mongoengine as me
import paho.mqtt.client as mqtt
import requests
import datetime
import numpy as np
from WebServer.config import IED_IP
import scipy.integrate as integrate

def Web_Server():

    station_lock = threading.Lock()
    station = SMBStation()
    stationSaveState = {}
    formInfo = {}
    liveInfo = {}
    linCol = False
    nonLinCol = False
    running = False
    offlineSimDone = False
    offlineSimResult = {}
    onlineInitDone = False
    mqttConnection = False
    tagMap = {}
    onlineMemory_lock = threading.Lock()
    onlineMemory = {}
    latestTimePointInSec = 0

    tagIdMap = {
        "Data.feedFlowrate": "101",
        "Data.eluentFlowrate": "102",
        "Data.raffinateFlowrate": "103",
        "Data.extractFlowrate": "104",
        "Data.recycleFlowrate": "105",
        "Data.feedConcCompA": "106",
        "Data.feedConcCompB": "107",
        "Data.feedConcCompC": "108",
        "Data.raffinateConcCompA": "109",
        "Data.raffinateConcCompB": "110",
        "Data.raffinateConcCompC": "111",
        "Data.extractConcCompA": "112",
        "Data.extractConcCompB": "113",
        "Data.extractConcCompC": "114",
        "Data.switchTime": "115",
        "Data.timeToSwitch": "116",
        "Data.position": "117",
        "Data.feedPumpRunnig": "118",
        "Data.eluentPumpRunning": "119",
        "Data.raffinatePumpRunning": "120",
        "Data.extractPumpRunning": "121",
        "Data.recyclePumpRunning": "122",
        "Data.feedPumpSetpoint": "123",
        "Data.eluentPumpSetpoint": "124",
        "Data.raffinatePumpSetpoint": "125",
        "Data.extractPumpSetpoint": "126",
        "Data.recyclePumpSetpoint": "127"
    }

    api = Flask(__name__)
    api.config['SECRET_KEY'] = 'super secret key'
    api.config['SECURITY_PASSWORD_SALT'] = 'super secret salt'
    api.config['SESSION_TYPE'] = 'development'
    me.connect('ChroMo', host='192.168.1.42', port=27017)
    login_manager = flask_login.LoginManager()
    login_manager.init_app(api)

    live_data_lock = threading.Lock()
    live_dict = {}
    ext_dict = {}
    ext_labels = {}
    raf_dict = {}
    raf_labels = {}

    sim_data_lock = threading.Lock()
    sim_dict = {}

    IE_USERNAME = "admin"
    IE_PASSWORD = "admin"
    BASE_URL = "https://" + IED_IP
    timeStart = datetime.datetime.utcnow().isoformat() + "Z"
    timeDict = {}
    dataserviceThreadHandler = False
    event = threading.Event()
    event.set()\

    class User(flask_login.UserMixin):
        pass

    @login_manager.user_loader
    def load_user(username):
        if not username == IE_USERNAME:
            return
        user = User()
        user.id = username
        return user

    @login_manager.request_loader
    def request_loader(request):
        username = request.form.get('username')
        if not username == IE_USERNAME:
            return
        user = User()
        user.id = username
        return user

    @login_manager.unauthorized_handler
    def unauthorized_handler():
        return 'Unauthorized', 401

    def on_connect(client, userdata, flags, rc):
        nonlocal mqttConnection
        mqttConnection = True
        print("MQTT connection working")

    def on_message(client, userdata, message):
        nonlocal tagIdMap
        try:
            message = json.loads(message.payload.decode("utf-8"))
            for dataPoint in message["connections"][0]["dataPoints"][0]["dataPointDefinitions"]:
                tagIdMap[dataPoint.name] = dataPoint.id
        except:
            print("message not relevant")

    def calculate_latest_time_point():
        nonlocal ext_labels, raf_labels, latestTimePointInSec
        for key, val in ext_labels.items():
            if len(val) > 0 and val[-1] > latestTimePointInSec:
                latestTimePointInSec = val[-1]
        for key, val in raf_labels.items():
            if len(val) > 0 and val[-1] > latestTimePointInSec:
                latestTimePointInSec = val[-1]

    def check_dataservice_connection(cookies):
        r = requests.get(BASE_URL + '/DataService/Service/IsRunning', cookies=cookies, verify=False)
        if r.status_code == 200:
            return r.json()['isRunning']
        return False


    def calculate_purity_and_yield():
        nonlocal station, onlineMemory, formInfo, station_lock, onlineMemory_lock
        resultDict = {}
        resultDict["purity"] = {}
        resultDict["yield"] = {}
        resultDict["purity"]['horizon'] = {}
        resultDict["purity"]['simdata'] = {}
        resultDict["purity"]['livedata'] = {}
        resultDict["yield"]['horizon'] = {}
        resultDict["yield"]['simdata'] = {}
        resultDict["yield"]['livedata'] = {}
        resultDict["purity"]['horizon']["extract"] = []
        resultDict["purity"]['horizon']["raffinate"] = []
        resultDict["yield"]['horizon']["extract"] = []
        resultDict["yield"]['horizon']["raffinate"] = []
        resultDict["purity"]['simdata']["extract"] = []
        resultDict["purity"]['simdata']["raffinate"] = []
        resultDict["yield"]['simdata']["extract"] = []
        resultDict["yield"]['simdata']["raffinate"] = []
        resultDict["purity"]['livedata']["extract"] = []
        resultDict["purity"]['livedata']["raffinate"] = []
        resultDict["yield"]['livedata']["extract"] = []
        resultDict["yield"]['livedata']["raffinate"] = []
        station_lock.acquire()
        try:
            timeForYield = formInfo['switchInterval'] * station.colCount
            stationTimer = station.timer
            compInfo = station.getCompInfo()
        finally:
            station_lock.release()
        compList = list(compInfo.keys())
        onlineMemory_lock.acquire()
        try:
            for key in onlineMemory.keys():
                usedTime = timeForYield
                if key == "livedata":
                    continue
                elif key == "horizon":
                    timeSinceLastChange = stationTimer-formInfo["lastChange"]
                    if timeSinceLastChange < timeForYield:
                        usedTime = timeSinceLastChange
                elif key == "simdata":
                    timeSinceLastChange = (stationTimer - formInfo["horizon"]) - formInfo["lastChange"]
                    if timeSinceLastChange > 0 and timeSinceLastChange < timeForYield:
                        usedTime = timeSinceLastChange
                numOfPointsForYield = int(usedTime // formInfo['dt'])
                extConcIntegPerCycle = []
                for comp in onlineMemory[key]["data"]["extract"]:
                    if usedTime == 0:
                        extConcIntegPerCycle.append(0)
                    else:
                        integ = integrate.trapezoid(y=comp[-numOfPointsForYield:], dx=formInfo["dt"])
                        res = integ / usedTime
                        extConcIntegPerCycle.append(res)
                rafConcIntegPerCycle = []
                for comp in onlineMemory[key]["data"]["raffinate"]:
                    if usedTime == 0:
                        extConcIntegPerCycle.append(0)
                    else:
                        integ = integrate.trapezoid(y=comp[-numOfPointsForYield:], dx=formInfo["dt"])
                        res = integ / usedTime
                        rafConcIntegPerCycle.append(res)
                totalSumExt = 0
                totalSumRaf = 0
                for outExt, outRaf in zip(extConcIntegPerCycle, rafConcIntegPerCycle):
                    totalSumExt += outExt
                    totalSumRaf += outRaf
                for idx, outExt, outRaf in zip(range(len(extConcIntegPerCycle)), extConcIntegPerCycle, rafConcIntegPerCycle):
                    feedConc = compInfo[compList[idx]]["Feed Concentration"]
                    if not formInfo["flowRate3"] == 0 and not feedConc == 0:
                        resultDict["yield"][key]["extract"].append((formInfo["flowRate2"] * outExt) / (formInfo["flowRate3"] * feedConc))
                        resultDict["yield"][key]["raffinate"].append((formInfo["flowRate4"] * outRaf) / (formInfo["flowRate3"] * feedConc))
                    else:
                        resultDict["yield"][key]["extract"].append(0)
                        resultDict["yield"][key]["raffinate"].append(0)
                    if not totalSumExt == 0:
                        resultDict["purity"][key]["extract"].append(outExt / totalSumExt)
                    else:
                        resultDict["purity"][key]["extract"].append(0)
                    if not totalSumExt == 0:
                        resultDict["purity"][key]["raffinate"].append(outRaf / totalSumRaf)
                    else:
                        resultDict["purity"][key]["raffinate"].append(0)
            usedTime = timeForYield
            timeSinceLastChange = (stationTimer - formInfo["horizon"]) - formInfo["lastChange"]
            if timeSinceLastChange > 0 and timeSinceLastChange < timeForYield:
                usedTime = timeSinceLastChange
            extConcIntegPerCycle = []
            for idx, comp in enumerate(compList):
                if len(onlineMemory['livedata']["extlabels"][comp]) > 0:
                    numOfPoints = len(onlineMemory['livedata']["extlabels"][comp]) - np.searchsorted(onlineMemory['livedata']["extlabels"][comp], onlineMemory['livedata']["extlabels"][comp][-1]-usedTime)
                    integ = integrate.trapezoid(y=onlineMemory['livedata']["data"]["extract"][idx][-numOfPoints:], x=onlineMemory['livedata']["extlabels"][comp][-numOfPoints:])
                    res = integ / usedTime
                    extConcIntegPerCycle.append(res)
                else:
                    extConcIntegPerCycle.append(0)
            rafConcIntegPerCycle = []
            for idx, comp in enumerate(compList):
                if len(onlineMemory['livedata']["raflabels"][comp]) > 0:
                    numOfPoints = len(onlineMemory['livedata']["raflabels"][comp]) - np.searchsorted(onlineMemory['livedata']["raflabels"][comp], onlineMemory['livedata']["raflabels"][comp][-1]-usedTime)
                    integ = integrate.trapezoid(y=onlineMemory['livedata']["data"]["raffinate"][idx][-numOfPoints:], x=onlineMemory['livedata']["raflabels"][comp][-numOfPoints:])
                    res = integ / usedTime
                    rafConcIntegPerCycle.append(res)
                else:
                    rafConcIntegPerCycle.append(0)
        finally:
            onlineMemory_lock.release()
        totalSumExt = 0
        totalSumRaf = 0
        for outExt, outRaf in zip(extConcIntegPerCycle, rafConcIntegPerCycle):
            totalSumExt += outExt
            totalSumRaf += outRaf
        for idx, outExt, outRaf in zip(range(len(extConcIntegPerCycle)), extConcIntegPerCycle, rafConcIntegPerCycle):
            feedConc = compInfo[compList[idx]]["Feed Concentration"]
            try:
                resultDict["yield"]['livedata']["extract"].append((formInfo["flowRate2"] * outExt) / (formInfo["flowRate3"] * feedConc))
                resultDict["yield"]['livedata']["raffinate"].append((formInfo["flowRate4"] * outRaf) / (formInfo["flowRate3"] * feedConc))
                resultDict["purity"]['livedata']["extract"].append(outExt / totalSumExt)
                resultDict["purity"]['livedata']["raffinate"].append(outRaf / totalSumRaf)
            except Exception as e:
                print(e)
                resultDict["yield"]['livedata']["extract"].append(0)
                resultDict["yield"]['livedata']["raffinate"].append(0)
                resultDict["purity"]['livedata']["extract"].append(0)
                resultDict["purity"]['livedata']["raffinate"].append(0)
        return resultDict

    def get_new_horizon_data(label):
        nonlocal onlineMemory, formInfo, onlineMemory_lock
        resultDict = {}
        onlineMemory_lock.acquire()
        try:
            resultDict["labels"] = [x for x in onlineMemory['horizon']["labels"] if x > label]
            resultDict["data"] = {}
            resultDict["data"]["extract"] = []
            resultDict["data"]["raffinate"] = []
            for idx, comp in enumerate(onlineMemory['horizon']["data"]["extract"]):
                if len(resultDict["labels"]) > 0:
                    resultDict["data"]["extract"].append(comp[-len(resultDict["labels"]):])
                else:
                    resultDict["data"]["extract"].append([])
            for idx, comp in enumerate(onlineMemory['horizon']["data"]["raffinate"]):
                if len(resultDict["labels"]) > 0:
                    resultDict["data"]["raffinate"].append(comp[-len(resultDict["labels"]):])
                else:
                    resultDict["data"]["raffinate"].append([])
        finally:
            onlineMemory_lock.release()
        return resultDict

    def get_new_live_data(extlabels, raflabels):
        resultDict = {}
        resultDict["extlabels"] = {}
        resultDict["raflabels"] = {}
        resultDict["extract"] = []
        resultDict["raffinate"] = []
        resultDict["extractFormated"] = []
        resultDict["raffinateFormated"] = []
        onlineMemory_lock.acquire()
        try:
            for idx, comp in enumerate(onlineMemory['livedata']["extlabels"].keys()):
                resultDict["extlabels"][comp] = [x for x in onlineMemory['livedata']["extlabels"][comp] if x > float(extlabels[idx])]
            for idx, comp in enumerate(onlineMemory['livedata']["raflabels"].keys()):
                resultDict["raflabels"][comp] = [x for x in onlineMemory['livedata']["raflabels"][comp] if x > float(raflabels[idx])]
            compList = list(resultDict["extlabels"].keys())
            for idx, comp in enumerate(onlineMemory['livedata']["data"]["extract"]):
                if len(compList) > idx:
                    if len(resultDict["extlabels"][compList[idx]]) > 0:
                        resultDict["extract"].append(comp[-len(resultDict["extlabels"][compList[idx]]):])
                    else:
                        resultDict["extract"].append([])
            for idx, comp in enumerate(onlineMemory['livedata']["data"]["extractFormated"]):
                if len(compList) > idx:
                    if len(resultDict["extlabels"][compList[idx]]) > 0:
                        resultDict["extractFormated"].append(comp[-len(resultDict["extlabels"][compList[idx]]):])
                    else:
                        resultDict["extractFormated"].append([])
            compList = list(resultDict["raflabels"].keys())
            for idx, comp in enumerate(onlineMemory['livedata']["data"]["raffinate"]):
                if len(compList) > idx:
                    if len(resultDict["raflabels"][compList[idx]]) > 0:
                        resultDict["raffinate"].append(comp[-len(resultDict["raflabels"][compList[idx]]):])
                    else:
                        resultDict["raffinate"].append([])
            for idx, comp in enumerate(onlineMemory['livedata']["data"]["raffinateFormated"]):
                if len(compList) > idx:
                    if len(resultDict["raflabels"][compList[idx]]) > 0:
                        resultDict["raffinateFormated"].append(comp[-len(resultDict["raflabels"][compList[idx]]):])
                    else:
                        resultDict["raffinateFormated"].append([])
        finally:
            onlineMemory_lock.release()
        return resultDict

    def update_online_memory(responseDict):
        nonlocal onlineMemory, formInfo, onlineMemory_lock
        onlineMemory_lock.acquire()
        try:
            for idx, comp in enumerate(onlineMemory['horizon']["data"]["extract"]):
                onlineMemory['horizon']["data"]["extract"][idx] = comp + responseDict["data"]["extract"][idx]
                onlineMemory['simdata']["data"]["extract"][idx] = onlineMemory['simdata']["data"]["extract"][idx] + comp[:len(responseDict["data"]["extract"][idx])]
                onlineMemory['horizon']["data"]["extract"][idx] = onlineMemory['horizon']["data"]["extract"][idx][len(responseDict["data"]["extract"][idx]):]
                onlineMemory['simdata']["data"]["extract"][idx] = onlineMemory['simdata']["data"]["extract"][idx][len(responseDict["data"]["extract"][idx]):]
            for idx, comp in enumerate(onlineMemory['horizon']["data"]["raffinate"]):
                onlineMemory['horizon']["data"]["raffinate"][idx] = comp + responseDict["data"]["raffinate"][idx]
                onlineMemory['simdata']["data"]["raffinate"][idx] = onlineMemory['simdata']["data"]["raffinate"][idx] + comp[:len(responseDict["data"]["raffinate"][idx])]
                onlineMemory['horizon']["data"]["raffinate"][idx] = onlineMemory['horizon']["data"]["raffinate"][idx][len(responseDict["data"]["raffinate"][idx]):]
                onlineMemory['simdata']["data"]["raffinate"][idx] = onlineMemory['simdata']["data"]["raffinate"][idx][len(responseDict["data"]["raffinate"][idx]):]
            onlineMemory['horizon']["labels"] = onlineMemory['horizon']["labels"] + responseDict["labels"]
            onlineMemory['simdata']["labels"] = onlineMemory['simdata']["labels"] + onlineMemory['horizon']["labels"][:len(responseDict["labels"])]
            onlineMemory['horizon']["labels"] = onlineMemory['horizon']["labels"][len(responseDict["labels"]):]
            onlineMemory['simdata']["labels"] = onlineMemory['simdata']["labels"][len(responseDict["labels"]):]
            for comp, complabels in responseDict["livedata"]["extlabels"].items():
                if comp in onlineMemory['livedata']["extlabels"]:
                    onlineMemory['livedata']["extlabels"][comp] = onlineMemory['livedata']["extlabels"][comp] + responseDict["livedata"]["extlabels"][comp]
                else:
                    onlineMemory['livedata']["extlabels"][comp] = responseDict["livedata"]["extlabels"][comp]
                onlineMemory['livedata']["extlabels"][comp] = [x for x in onlineMemory['livedata']["extlabels"][comp] if x >= onlineMemory['livedata']["extlabels"][comp][-1] - formInfo['backhorizon']]
            for comp, complabels in responseDict["livedata"]["raflabels"].items():
                if comp in onlineMemory['livedata']["raflabels"]:
                    onlineMemory['livedata']["raflabels"][comp] = onlineMemory['livedata']["raflabels"][comp] + responseDict["livedata"]["raflabels"][comp]
                else:
                    onlineMemory['livedata']["raflabels"][comp] = responseDict["livedata"]["raflabels"][comp]
                onlineMemory['livedata']["raflabels"][comp] = [x for x in onlineMemory['livedata']["raflabels"][comp] if x >= onlineMemory['livedata']["raflabels"][comp][-1] - formInfo['backhorizon']]
            for idx, comp in enumerate(onlineMemory['livedata']["data"]["extract"]):
                onlineMemory['livedata']["data"]["extract"][idx] = comp + responseDict["livedata"]["extract"][idx]
                onlineMemory['livedata']["data"]["extract"][idx] = onlineMemory['livedata']["data"]["extract"][idx][-len(onlineMemory['livedata']["extlabels"][list(onlineMemory['livedata']["extlabels"].keys())[idx]]):]
            for idx, comp in enumerate(onlineMemory['livedata']["data"]["raffinate"]):
                onlineMemory['livedata']["data"]["raffinate"][idx] = comp + responseDict["livedata"]["raffinate"][idx]
                onlineMemory['livedata']["data"]["raffinate"][idx] = onlineMemory['livedata']["data"]["raffinate"][idx][-len(onlineMemory['livedata']["raflabels"][list(onlineMemory['livedata']["raflabels"].keys())[idx]]):]
            for idx, comp in enumerate(onlineMemory['livedata']["data"]["extractFormated"]):
                onlineMemory['livedata']["data"]["extractFormated"][idx] = comp + responseDict["livedata"]["extractFormated"][idx]
                onlineMemory['livedata']["data"]["extractFormated"][idx] = onlineMemory['livedata']["data"]["extractFormated"][idx][-len(onlineMemory['livedata']["extlabels"][list(onlineMemory['livedata']["extlabels"].keys())[idx]]):]
            for idx, comp in enumerate(onlineMemory['livedata']["data"]["raffinateFormated"]):
                onlineMemory['livedata']["data"]["raffinateFormated"][idx] = comp + responseDict["livedata"]["raffinateFormated"][idx]
                onlineMemory['livedata']["data"]["raffinateFormated"][idx] = onlineMemory['livedata']["data"]["raffinateFormated"][idx][-len(onlineMemory['livedata']["raflabels"][list(onlineMemory['livedata']["raflabels"].keys())[idx]]):]
        finally:
            onlineMemory_lock.release()

    def online_init():
        nonlocal station, formInfo, onlineMemory, onlineInitDone, sim_dict, sim_data_lock, station_lock
        responseDict = {}
        simDict = {}
        station_lock.acquire()
        try:
            responseDict["compList"] = list(station.getCompInfo().keys())
            responseDict["labels"] = []
            responseDict["data"] = {}
            simDict["labels"] = []
            simDict["data"] = {}
            for i in np.arange(0, formInfo["liveTime"]-formInfo["backhorizon"], formInfo["dt"]):
                station.step()
            responseDict["data"]["raffinate"] = []
            responseDict["data"]["extract"] = []
            simDict["data"]["raffinate"] = []
            simDict["data"]["extract"] = []
            for i in range(len(responseDict["compList"])):
                responseDict["data"]["raffinate"].append([])
                responseDict["data"]["extract"].append([])
                simDict["data"]["raffinate"].append([])
                simDict["data"]["extract"].append([])
            for i in np.arange(formInfo["liveTime"]-formInfo["backhorizon"], formInfo["liveTime"],
                               formInfo["dt"]):  # loop for each time step
                simDict["labels"].append(i)  # saving time lables
                res = station.step()  # step
                for idx, x in enumerate(res[1][-1]):  # loop through components in last column in zone 1
                    simDict["data"]["extract"][idx].append(x[-1])  # append last conc value of given component
                for idx, x in enumerate(res[3][-1]):  # loop through components in last column in zone 3
                    simDict["data"]["raffinate"][idx].append(x[-1])  # append last conc value of given component
            for i in np.arange(formInfo["liveTime"], formInfo["liveTime"] + formInfo["horizon"],
                               formInfo["dt"]):  # loop for each time step
                responseDict["labels"].append(i)  # saving time lables
                res = station.step()  # step
                for idx, x in enumerate(res[1][-1]):  # loop through components in last column in zone 1
                    responseDict["data"]["extract"][idx].append(x[-1])  # append last conc value of given component
                for idx, x in enumerate(res[3][-1]):  # loop through components in last column in zone 3
                    responseDict["data"]["raffinate"][idx].append(x[-1])  # append last conc value of given component
            formInfo["lastChange"] = station.timer
            formInfo["secondLastChange"] = station.timer
        finally:
            station_lock.release()
        onlineMemory_lock.acquire()
        try:
            onlineMemory["horizon"] = responseDict
            onlineMemory["simdata"] = simDict
            onlineMemory["livedata"] = {}
            onlineMemory["livedata"]["extlabels"] = {}
            onlineMemory["livedata"]["raflabels"] = {}
            onlineMemory["livedata"]["data"] = {}
            onlineMemory["livedata"]["data"]["raffinate"] = []
            onlineMemory["livedata"]["data"]["extract"] = []
            onlineMemory["livedata"]["data"]["raffinateFormated"] = []
            onlineMemory["livedata"]["data"]["extractFormated"] = []
            for comp in responseDict["compList"]:
                onlineMemory["livedata"]["data"]["raffinate"].append([])
                onlineMemory["livedata"]["data"]["extract"].append([])
                onlineMemory["livedata"]["data"]["raffinateFormated"].append([])
                onlineMemory["livedata"]["data"]["extractFormated"].append([])
        finally:
            onlineMemory_lock.release()
        sim_data_lock.acquire()
        try:
            sim_dict["compList"] = responseDict["compList"]
            sim_dict["labels"] = []
            sim_dict["data"] = {}
            sim_dict["data"]["raffinate"] = []
            sim_dict["data"]["extract"] = []
            for i in range(len(sim_dict["compList"])):
                sim_dict["data"]["raffinate"].append([])
                sim_dict["data"]["extract"].append([])
        finally:
            sim_data_lock.release()
        onlineInitDone = True

    def login_to_Dataservice():
        nonlocal BASE_URL, IE_USERNAME, IE_PASSWORD
        data = '{"username": "' + IE_USERNAME + '","password": "' + IE_PASSWORD + '"}'
        r = requests.post(BASE_URL + '/device/edge/api/v1/login/direct', data=data, verify=False)
        if r.status_code == 200:
            body = r.json()
            token = body["data"]["access_token"]
            expiration = body["data"]["expires_in"]
            return {'authToken': str(token), 'sessionExpiryTime': str(expiration)}
        return {}

    def get_PLC_variables(cookies):
        r = requests.get(BASE_URL + '/DataService/Variables', cookies=cookies, verify=False)
        if r.status_code == 200:
            return r.json()
        return {}

    def get_PLC_tags(cookies):
        variables = get_PLC_variables(cookies)
        tags = [var["variableName"] for var in variables["variables"]]
        return tags

    def get_data_all(tag, cookies, time):
        nonlocal timeStart, formInfo
        variables = get_PLC_variables(cookies)
        varID = ""
        for var in variables["variables"]:
            if var["variableName"] == tag:
                varID = var["variableId"]
                break
        if not varID:
            return "Tag not found"
        body = '[{"variableId": "' + varID + '","lastRequestTime": "' + time + '"}]'
        r = requests.post(BASE_URL + '/DataService/Data/Delta', data=body, cookies=cookies, verify=False)
        rdict = r.json()
        data3 = [d["value"] for d in rdict["data"][0]["values"]]
        labels = [(datetime.datetime.strptime(t["timestamp"][:-2]+"Z",'%Y-%m-%dT%H:%M:%S.%fZ')-datetime.datetime.strptime(timeStart[:-2]+"Z",'%Y-%m-%dT%H:%M:%S.%fZ')).total_seconds() + formInfo["liveTime"] for t in rdict["data"][0]["values"]]
        if "lastRequestTime" in rdict["data"][0]:
            return (data3, labels, rdict["data"][0]["lastRequestTime"])
        else:
            return (data3, labels, datetime.datetime.utcnow().isoformat() + "Z")

    def get_data_single(tag, cookies):
        nonlocal BASE_URL, IE_USERNAME, IE_PASSWORD
        variables = get_PLC_variables(cookies)
        varID = ""
        if "variables" in variables:
            for var in variables["variables"]:
                if var["variableName"] == tag:
                    varID = var["variableId"]
                    break
            if not varID:
                return "Tag not found"
            timeFrom = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat() + "Z"
            timeTo = datetime.datetime.utcnow().isoformat() + "Z"
            url = BASE_URL + '/DataService/Data/' + varID + '?from=' + timeFrom + '&to=' + timeTo + '&order=Descending'
            r = requests.get(url, cookies=cookies, verify=False)
            rdict = r.json()
            if len(rdict["data"][0]["values"]) > 0:
                data3 = rdict["data"][0]["values"][0]["value"]
                return data3
        return 0

    def update_live_data(cookies):
        nonlocal station, formInfo, liveInfo, timeDict, tagMap, ext_dict, raf_dict, raf_labels, ext_labels,\
            latestTimePointInSec, sim_dict, onlineInitDone, live_data_lock, sim_data_lock, station_lock
        for var, tag in tagMap.items():
            if tag == "NI" or var == "":
                continue
            if var.startswith("raffinate") and len(var) > 9 and not var.endswith("PumpSetpoint"):
                if not tag in timeDict:
                    timeDict[tag] = timeStart
                arr = get_data_all(tag, cookies, timeDict[tag])
                comp = var[len("raffinate"):]
                live_data_lock.acquire()
                try:
                    if comp in raf_dict:
                        raf_dict[comp] = raf_dict[comp] + arr[0]
                    else:
                        raf_dict[comp] = arr[0]
                    if comp in raf_labels:
                        raf_labels[comp] = raf_labels[comp] + arr[1]
                    else:
                        raf_labels[comp] = arr[1]
                finally:
                    live_data_lock.release()
                timeDict[tag] = arr[2]
            elif var.startswith("extract") and len(var) > 7 and not var.endswith("PumpSetpoint"):
                if not tag in timeDict:
                    timeDict[tag] = timeStart
                arr = get_data_all(tag, cookies, timeDict[tag])
                comp = var[len("extract"):]
                live_data_lock.acquire()
                try:
                    if comp in ext_dict:
                        ext_dict[comp] = ext_dict[comp] + arr[0]
                    else:
                        ext_dict[comp] = arr[0]
                    if comp in ext_labels:
                        ext_labels[comp] = ext_labels[comp] + arr[1]
                    else:
                        ext_labels[comp] = arr[1]
                finally:
                    live_data_lock.release()
                timeDict[tag] = arr[2]
            else:
                res = get_data_single(tag, cookies)
                liveInfo[var] = res
            calculate_latest_time_point()
            if onlineInitDone:
                station_lock.acquire()
                sim_data_lock.acquire()
                try:
                    sim_dict["compList"] = list(station.getCompInfo().keys())
                    while station.timer - formInfo["horizon"] < latestTimePointInSec:
                        if "countdown" in stationSaveState and stationSaveState["countdown"] < 0:
                            break
                        res = station.step()
                        if "countdown" in stationSaveState:
                            stationSaveState["countdown"] -= formInfo["dt"]
                        sim_dict["labels"].append(station.timer)
                        for idx, x in enumerate(res[1][-1]):
                            sim_dict["data"]["extract"][idx].append(x[-1])
                        for idx, x in enumerate(res[3][-1]):
                            sim_dict["data"]["raffinate"][idx].append(x[-1])
                finally:
                    sim_data_lock.release()
                    station_lock.release()

    def convert_data():
        nonlocal station, running, formInfo, tagMap, liveInfo, ext_dict, raf_dict, ext_labels, raf_labels,\
            stationSaveState, sim_dict, sim_data_lock, live_data_lock, onlineInitDone
        if onlineInitDone:
            sim_data_lock.acquire()
            try:
                responseDict = sim_dict
                responseDict["compList"] = list(station.getCompInfo().keys())
                sim_dict = {}
                sim_dict["compList"] = list(station.getCompInfo().keys())
                sim_dict["labels"] = []
                sim_dict["data"] = {}
                sim_dict["data"]["raffinate"] = []
                sim_dict["data"]["extract"] = []
                for i in range(len(sim_dict["compList"])):
                    sim_dict["data"]["raffinate"].append([])
                    sim_dict["data"]["extract"].append([])
            finally:
                sim_data_lock.release()
            responseDict["livedata"] = {}
            responseDict["livedata"]["raffinate"] = []
            responseDict["livedata"]["extract"] = []
            responseDict["livedata"]["raffinateFormated"] = []
            responseDict["livedata"]["extractFormated"] = []
            responseDict["livedata"]["state"] = formInfo["switchPosition"]
            sim_data_lock.acquire()
            try:
                for comp in responseDict["compList"]:
                    if comp in ext_dict and comp in ext_labels:
                        extdata4 = [{"x": b, "y": a} for a, b in zip(ext_dict[comp], ext_labels[comp])]
                        responseDict["livedata"]["extractFormated"].append(extdata4)
                        responseDict["livedata"]["extract"].append(ext_dict[comp])
                    else:
                        responseDict["livedata"]["extractFormated"].append([])
                        responseDict["livedata"]["extract"].append([])
                    if comp in raf_dict and comp in raf_labels:
                        rafdata4 = [{"x": b, "y": a} for a, b in zip(raf_dict[comp], raf_labels[comp])]
                        responseDict["livedata"]["raffinateFormated"].append(rafdata4)
                        responseDict["livedata"]["raffinate"].append(raf_dict[comp])
                    else:
                        responseDict["livedata"]["raffinateFormated"].append([])
                        responseDict["livedata"]["raffinate"].append([])
                    raf_dict[comp] = []
                    ext_dict[comp] = []
                responseDict["livedata"]["extlabels"] = ext_labels
                ext_labels = {}
                responseDict["livedata"]["raflabels"] = raf_labels
                raf_labels = {}
            finally:
                sim_data_lock.release()
            update_online_memory(responseDict)
    def update_station():
        nonlocal formInfo, station
        station.setFlowRateZone(1, formInfo["flowRate1"]*formInfo["flowRateUnits"])
        station.setFlowRateZone(2, formInfo["flowRate2"]*formInfo["flowRateUnits"])
        station.setFlowRateZone(3, formInfo["flowRate3"]*formInfo["flowRateUnits"])
        station.setFlowRateZone(4, formInfo["flowRate4"]*formInfo["flowRateUnits"])
        station.setSwitchInterval(formInfo["switchInterval"])
        station.initCols()

    def update_feed_concentrations():
        nonlocal formInfo, tagMap, station, station_lock
        print("calling update feed concentrations")
        if not stationSaveState:
            cookies = login_to_Dataservice()
            station_lock.acquire()
            try:
                compList = list(station.getCompInfo().keys())
                for comp in compList:
                    feedConc = get_data_single(tagMap["feed" + comp], cookies)
                    print("changing feed of", comp, "to", feedConc*formInfo["concUnits"])
                    station.updateComponentByName(comp, feedConc=feedConc*formInfo["concUnits"])
                station.initCols()
            finally:
                station_lock.release()
    def fix_flowrates():
        nonlocal formInfo
        formInfo["flowRate1"] = formInfo["flowRateRecycle"] + formInfo["flowRateEluent"]
        formInfo["flowRate2"] = formInfo["flowRate1"] - formInfo["flowRateExtract"]
        formInfo["flowRate3"] = formInfo["flowRate2"] + formInfo["flowRateFeed"]
        formInfo["flowRate4"] = formInfo["flowRate3"] - formInfo["flowRateRaffinate"]
        if(formInfo["flowRate4"]-formInfo["flowRateRecycle"] > 0.1):
            print("flow rates dont match up")

    def add_column(request):
        nonlocal station, linCol, nonLinCol, formInfo, station_lock
        formInfo["zone"] = int(request.form.get("zone"))
        formInfo["isotherm"] = request.form.get("isotherm")
        formInfo["colLength"] = float(request.form.get("colLength"))
        formInfo["colDiameter"] = float(request.form.get("colDiameter"))
        formInfo["porosity"] =  float(request.form.get("porosity"))
        formInfo["deadVol"] =  float(request.form.get("deadVol"))
        station_lock.acquire()
        try:
            if formInfo["isotherm"] == "Lin":
                if formInfo["zone"] == 5:
                    for zone in range(1, 5):
                        station.addColZone(zone,
                                           LinColumn(formInfo["colLength"], formInfo["colDiameter"], formInfo["porosity"]),
                                           Tube(formInfo["deadVol"]))
                else:
                    station.addColZone(formInfo["zone"], LinColumn(formInfo["colLength"], formInfo["colDiameter"], formInfo["porosity"]), Tube(formInfo["deadVol"]))
                linCol = True
            elif formInfo["isotherm"] == "Nonlin":
                if formInfo["zone"] == 5:
                    for zone in range(1, 5):
                        station.addColZone(zone,
                                           NonLinColumn(formInfo["colLength"], formInfo["colDiameter"], formInfo["porosity"]),
                                           Tube(formInfo["deadVol"]))
                else:
                    station.addColZone(formInfo["zone"], NonLinColumn(formInfo["colLength"], formInfo["colDiameter"], formInfo["porosity"]), Tube(formInfo["deadVol"]))
                nonLinCol = True
        finally:
            station_lock.release()

    def add_component(request):
        nonlocal station, formInfo
        name = request.form.get("name")
        feedConc = float(request.form.get("feedConc"))
        henryConst = -1
        if linCol:
            henryConst = float(request.form.get("henryConst"))
        langmuirConst = -1
        saturCoef = -1
        if nonLinCol:
            langmuirConst = float(request.form.get("langmuirConst"))
            saturCoef = float(request.form.get("saturCoef"))
        disperCoef = float(request.form.get("disperCoef"))
        station_lock.acquire()
        try:
            station.addComponent(name, feedConc=feedConc, henryConst=henryConst, disperCoef=disperCoef, langmuirConst=langmuirConst, saturCoef=saturCoef)
        finally:
            station_lock.release()

    def periodic_task(func, period, *args):
        nonlocal event
        while not event.is_set():
            print("period", period)
            func(*args)
            time.sleep(period)

    class DBExperiment(me.Document):
        uniquename = me.StringField(required=True, unique=True)
        name = me.StringField(required=True)
        experiment = me.StringField(required=True)

    class DBResult(me.Document):
        thr_id = me.IntField(required=True, unique=True)
        name = me.StringField(required=True)
        experiments = me.ListField(me.ReferenceField(DBExperiment))
        results = me.DictField(required=True)


    @api.route('/smbstation/components/simconfig/simulation', methods=['DELETE'])
    @flask_login.login_required
    def delete_simulation_data():
        nonlocal station, formInfo, linCol, nonLinCol, offlineSimDone, offlineSimResult, onlineInitDone, stationSaveState, \
            liveInfo, running, mqttConnection, tagMap, onlineMemory, ext_dict, ext_labels, raf_dict, raf_labels, timeDict, \
            dataserviceThreadHandler, event, station_lock, live_data_lock, sim_data_lock, sim_dict
        event.set()
        dataserviceThreadHandler = False
        station_lock.acquire()
        try:
            del station
            station = SMBStation()
        finally:
            station_lock.release()
        live_data_lock.acquire()
        try:
            ext_dict = {}
            ext_labels = {}
            raf_dict = {}
            raf_labels = {}
        finally:
            live_data_lock.release()
        sim_data_lock.acquire()
        try:
            sim_dict = {}
        finally:
            sim_data_lock.release()
        timeDict = {}
        del formInfo
        formInfo = {}
        linCol = False
        nonLinCol = False
        offlineSimDone = False
        offlineSimResult = {}
        onlineInitDone = False
        stationSaveState = {}
        liveInfo = {}
        running = False
        onlineInitDone = False
        mqttConnection = False
        tagMap = {}
        onlineMemory = {}
        return url_for('get_main_page')

    @api.route('/offline/smbstation/components/simconfig/simulation/data', methods=['GET'])
    @flask_login.login_required
    def get_simulation_offline_data():
        nonlocal station, offlineSimDone, offlineSimResult, station_lock
        if not offlineSimDone:
            responseDict = {}
            responseDict["compList"] = list(station.getCompInfo().keys())
            responseDict["labels"] = []
            responseDict["data"] = {}
            responseDict["data"]["raffinate"] = []
            responseDict["data"]["extract"] = []
            responseDict["data"]["purities"] = {}
            responseDict["data"]["purities"]["raffinate"] = []
            responseDict["data"]["purities"]["extract"] = []
            responseDict["data"]["yields"] = {}
            responseDict["data"]["yields"]["raffinate"] = []
            responseDict["data"]["yields"]["extract"] = []
            for i in range(len(responseDict["compList"])):
                responseDict["data"]["raffinate"].append([])
                responseDict["data"]["extract"].append([])
            station_lock.acquire()
            try:
                compInfo = station.getCompInfo()
                for i in np.arange(0, formInfo["simtime"], formInfo["dt"]): # loop for each time step
                    responseDict["labels"].append(i) # saving time lables
                    res = station.step() # step
                    for idx, x in enumerate(res[1][-1]): # loop through components in last column in zone 1
                        responseDict["data"]["extract"][idx].append(x[-1]) # append last conc value of given component
                    for idx, x in enumerate(res[3][-1]): # loop through components in last column in zone 3
                        responseDict["data"]["raffinate"][idx].append(x[-1]) # append last conc value of given component
                responseDict["data"]["final"] = res # saves last state of station
                timeForYield = formInfo['switchInterval']*station.colCount
            finally:
                station_lock.release()
            numOfPointsForYield = int(timeForYield//formInfo['dt'])
            extConcIntegPerCycle = []
            for comp in responseDict["data"]["extract"]:
                integ = integrate.trapezoid(y=comp[-numOfPointsForYield:], dx=formInfo["dt"])
                res = integ/timeForYield
                extConcIntegPerCycle.append(res)
            rafConcIntegPerCycle = []
            for comp in responseDict["data"]["raffinate"]:
                integ = integrate.trapezoid(y=comp[-numOfPointsForYield:], dx=formInfo["dt"])
                res = integ/timeForYield
                rafConcIntegPerCycle.append(res)
            totalSumExt = 0
            totalSumRaf = 0
            for outExt, outRaf in zip(extConcIntegPerCycle, rafConcIntegPerCycle):
                totalSumExt += outExt
                totalSumRaf += outRaf
            for idx, outExt, outRaf in zip(range(len(extConcIntegPerCycle)), extConcIntegPerCycle, rafConcIntegPerCycle):
                feedConc = compInfo[responseDict["compList"][idx]]["Feed Concentration"]
                feedFlowRate = formInfo["flowRate3"] - formInfo["flowRate2"]
                extFlowRate = formInfo["flowRate1"] - formInfo["flowRate2"]
                rafFlowRate = formInfo["flowRate3"] - formInfo["flowRate4"]
                responseDict["data"]["yields"]["extract"].append((extFlowRate*outExt)/(feedFlowRate*feedConc))
                responseDict["data"]["yields"]["raffinate"].append((rafFlowRate*outRaf)/(feedFlowRate*feedConc))
                responseDict["data"]["purities"]["extract"].append(outExt/totalSumExt)
                responseDict["data"]["purities"]["raffinate"].append(outRaf/totalSumRaf)
            offlineSimResult = responseDict
            offlineSimDone = True
            return json.dumps(responseDict)
        else:
            return json.dumps(offlineSimResult)

    @api.route('/online/smbstation/components/simconfig/simulation/initData', methods=['GET'])
    def get_simulation_online_init():
        nonlocal station, running, formInfo, onlineInitDone, onlineMemory
        if not onlineInitDone:
            online_init()
            return json.dumps(onlineMemory)
        else:
            return json.dumps(onlineMemory)

    @api.route('/online/smbstation/components/simconfig/simulation/data', methods=['POST'])
    def get_simulation_online_data():
        nonlocal station, running, formInfo, tagMap, liveInfo, ext_dict, raf_dict, ext_labels, raf_labels,\
            stationSaveState, sim_dict, sim_data_lock, live_data_lock
        body = request.get_json()
        simLabel = float(body["simLabel"])
        responseDict = get_new_horizon_data(simLabel)
        liveExtLabels = body["liveExtLabels"]
        liveRafLabels = body["liveRafLabels"]
        responseDict["livedata"] = get_new_live_data(liveExtLabels, liveRafLabels)
        responseDict["data"]["state"] = station.switchState
        responseDict["data"]["timeToSwitch"] = station.countdown
        responseDict["keepChangesAnswerRequest"] = False
        if "countdown" in stationSaveState and stationSaveState["countdown"] <= 0:
            responseDict["keepChangesAnswerRequest"] = True
        responseDict["liveInfo"] = liveInfo
        responseDict["compList"] = list(station.getCompInfo().keys())
        return json.dumps(responseDict)

    @api.route('/online/smbstation/components/simconfig/simulation/changesCommited', methods=['GET'])
    def get_simulation_online_change_commit():
        responseDict = {}
        if "countdown" in stationSaveState and stationSaveState["countdown"] <= 0:
            responseDict["commit"] = False
        else:
            responseDict["commit"] = True
        return json.dumps(responseDict)

    @api.route('/online/smbstation/components/simconfig/simulation/purityandyield', methods=['GET'])
    def get_simulation_online_purity_and_yield():
        responseDict = calculate_purity_and_yield()
        return json.dumps(responseDict)

    @api.route('/online/smbstation/components/simconfig/simulation', methods=['GET'])
    def get_simulation_online():
        nonlocal station, running, formInfo
        if running:
            return render_template('OnlineSimulationPage.html', formInfo=formInfo, compInfo=station.getCompInfo(), auth=flask_login.current_user.is_authenticated)
        return "No simulation running"

    @api.route('/offline/smbstation/components/simconfig/export', methods=['GET'])
    @flask_login.login_required
    def get_export():
        nonlocal station, formInfo, station_lock
        export = {}
        station_lock.acquire()
        try:
            export['col'] = station.getColInfo()
            export['comp'] = station.getCompInfo()
            export['settings'] = station.getSettingsInfo()
        finally:
            station_lock.release()
        return json.dumps(export)

    @api.route('/offline/import', methods=['GET'])
    @flask_login.login_required
    def get_import():
        return render_template('Import.html', online=False)

    @api.route('/offline/import', methods=['POST'])
    @flask_login.login_required
    def post_import():
        nonlocal station, linCol, nonLinCol, station_lock
        try:
            data = json.loads(request.form.get("importString"))
            station_lock.acquire()
            try:
                for zone in data['col']:
                    for i in range(0,len(data['col'][zone]),2):
                        length = data['col'][zone][i + 1]['Length']
                        diameter = data['col'][zone][i + 1]['Diameter']
                        porosity = data['col'][zone][i + 1]['Porority']
                        deadVolume = data['col'][zone][i]['deadVolume']
                        if data['col'][zone][i+1]['Column Type'] == 'EDM with Linear isotherm':
                            station.addColZone(int(zone), LinColumn(length, diameter, porosity), Tube(deadVolume))
                            linCol = True
                        if data['col'][zone][i + 1]['Column Type'] == 'EDM with Noncompetetive Langmuir isotherm':
                            station.addColZone(int(zone), NonLinColumn(length, diameter, porosity), Tube(deadVolume))
                            nonLinCol = True
                for comp in data['comp']:
                    feedConc = data['comp'][comp]['Feed Concentration']
                    henryConst = data['comp'][comp]['Henry Constant']
                    langmuirConst = data['comp'][comp]['Langmuir Constant']
                    saturCoef = data['comp'][comp]['Saturation Coefficient']
                    disperCoef = data['comp'][comp]['Dispersion Coefficient']
                    station.addComponent(comp, feedConc=feedConc, henryConst=henryConst, disperCoef=disperCoef, langmuirConst=langmuirConst, saturCoef=saturCoef)
                formInfo["flowRate1"] = data['settings']['Flow Rate']['1']
                station.setFlowRateZone(1, data['settings']['Flow Rate']['1'])
                formInfo["flowRate2"] = data['settings']['Flow Rate']['2']
                station.setFlowRateZone(2, data['settings']['Flow Rate']['2'])
                formInfo["flowRate3"] = data['settings']['Flow Rate']['3']
                station.setFlowRateZone(3, data['settings']['Flow Rate']['3'])
                formInfo["flowRate4"] = data['settings']['Flow Rate']['4']
                station.setFlowRateZone(4, data['settings']['Flow Rate']['4'])
                formInfo["switchInterval"] = data['settings']['Switch Interval']
                station.setSwitchInterval(data['settings']['Switch Interval'])
                formInfo["dt"] = data['settings']['dt']
                station.setdt(data['settings']['dt'])
                formInfo["Nx"] = data['settings']['Nx']
                station.setNx(data['settings']['Nx'])
                formInfo["simtime"] = data['settings']['timer']
            finally:
                station_lock.release()
            return redirect(url_for('get_SMB'))
        except:
            return render_template('Import.html', importLink = url_for('post_import'), error="Something went wrong with import - Try again")

    @api.route('/online/import', methods=['GET'])
    @flask_login.login_required
    def get_import_online():
        return render_template('Import.html', online=True)

    @api.route('/online/import', methods=['POST'])
    @flask_login.login_required
    def post_import_online():
        nonlocal station, linCol, nonLinCol, station_lock
        try:
            data = json.loads(request.form.get("importString"))
            station_lock.acquire()
            try:
                for zone in data['col']:
                    for i in range(0,len(data['col'][zone]),2):
                        length = data['col'][zone][i + 1]['Length']
                        diameter = data['col'][zone][i + 1]['Diameter']
                        porosity = data['col'][zone][i + 1]['Porority']
                        deadVolume = data['col'][zone][i]['deadVolume']
                        if data['col'][zone][i+1]['Column Type'] == 'EDM with Linear isotherm':
                            station.addColZone(int(zone), LinColumn(length, diameter, porosity), Tube(deadVolume))
                            linCol = True
                        if data['col'][zone][i + 1]['Column Type'] == 'EDM with Noncompetetive Langmuir isotherm':
                            station.addColZone(int(zone), NonLinColumn(length, diameter, porosity), Tube(deadVolume))
                            nonLinCol = True
                for comp in data['comp']:
                    henryConst = data['comp'][comp]['Henry Constant']
                    langmuirConst = data['comp'][comp]['Langmuir Constant']
                    saturCoef = data['comp'][comp]['Saturation Coefficient']
                    disperCoef = data['comp'][comp]['Dispersion Coefficient']
                    station.addComponent(comp, henryConst=henryConst, disperCoef=disperCoef, langmuirConst=langmuirConst, saturCoef=saturCoef)
                formInfo["dt"] = data['settings']['dt']
                station.setdt(data['settings']['dt'])
                formInfo["Nx"] = data['settings']['Nx']
                station.setNx(data['settings']['Nx'])
            finally:
                station_lock.release()
            return redirect(url_for('get_SMB_online'))
        except:
            return render_template('Import.html', online=True, error="Something went wrong with import - Try again")


    @api.route('/offline/smbstation/components', methods=['GET'])
    @flask_login.login_required
    def get_components():
        nonlocal station, formInfo, running
        return render_template('AddingComponents.html', compInfo=station.getCompInfo(), linCol=linCol,
                               nonLinCol=nonLinCol, running=running, online=False)

    @api.route('/offline/smbstation/components', methods=['POST'])
    @flask_login.login_required
    def post_add_component():
        add_component(request)
        return redirect(url_for('get_components'))

    @api.route('/online/smbstation/components', methods=['GET'])
    @flask_login.login_required
    def get_components_online():
        nonlocal station, formInfo, running
        return render_template('AddingComponents.html', compInfo=station.getCompInfo(), linCol=linCol,
                               nonLinCol=nonLinCol, running=running, online=True)

    @api.route('/online/smbstation/components', methods=['POST'])
    @flask_login.login_required
    def post_add_component_online():
        add_component(request)
        return redirect(url_for('get_components_online'))

    @api.route('/offline/peimport', methods=['GET'])
    @flask_login.login_required
    def get_pe_import():
        return render_template('ImportPE.html', importUrl=url_for('post_pe_import'))

    @api.route('/offline/peimport', methods=['POST'])
    @flask_login.login_required
    def post_pe_import():
        nonlocal station, running, linCol, nonLinCol, station_lock
        try:
            resData = json.loads(request.form.get("resImportString"))
            expData = json.loads(request.form.get("expImportString"))
            station_lock.acquire()
            try:
                station.setPorosity(resData['results']['porosity'])
                for comp in resData['results']['compparams'].keys():
                    if len(resData['results']['compparams'][comp]) == 2:
                        station.updateComponentByName(comp, henryConst=resData['results']['compparams'][comp][0],
                                                      disperCoef=resData['results']['compparams'][comp][1])
                    else:
                        station.updateComponentByName(comp, langmuirConst=resData['results']['compparams'][comp][0],
                                                      disperCoef=resData['results']['compparams'][comp][1],
                                                      saturCoef=resData['results']['compparams'][comp][2])
                for comp in expData["components"]:
                    station.updateComponentByName(comp["name"], feedConc=comp["feedConcentration"])
                for zone in range(1, 5):
                    station.addColZone(zone, LinColumn(expData["columnLength"], expData["columnDiameter"], resData['results']["porosity"]),
                                       Tube(expData["deadVolume"]))
            except Exception as e:
                return render_template('ImportPE.html', importUrl=url_for('post_pe_import'), error="Bad Import")
            finally:
                station_lock.release()
            return redirect(url_for('get_SMB'))
        except Exception as e:
            return render_template('ImportPE.html', importUrl=url_for('post_pe_import'), error="Bad Import")

    @api.route('/online/peimport', methods=['GET'])
    @flask_login.login_required
    def get_pe_import_online():
        return render_template('ImportPE.html', importUrl=url_for('post_pe_import_online'))

    @api.route('/online/peimport', methods=['POST'])
    @flask_login.login_required
    def post_pe_import_online():
        nonlocal station, running, linCol, nonLinCol, station_lock
        try:
            resData = json.loads(request.form.get("resImportString"))
            expData = json.loads(request.form.get("expImportString"))
            station_lock.acquire()
            try:
                station.setPorosity(resData['results']['porosity'])
                for comp in resData['results']['compparams'].keys():
                    if len(resData['results']['compparams'][comp]) == 2:
                        station.updateComponentByName(comp, henryConst=resData['results']['compparams'][comp][0],
                                                      disperCoef=resData['results']['compparams'][comp][1])
                    else:
                        station.updateComponentByName(comp, langmuirConst=resData['results']['compparams'][comp][0],
                                                      disperCoef=resData['results']['compparams'][comp][1],
                                                      saturCoef=resData['results']['compparams'][comp][2])
                for zone in range(1, 5):
                    station.addColZone(zone, LinColumn(expData["columnLength"], expData["columnDiameter"], resData['results']["porosity"]),
                                       Tube(expData["deadVolume"]))
            except Exception as e:
                return render_template('ImportPE.html', importUrl=url_for('post_pe_import_online'), error="Bad Import")
            finally:
                station_lock.release()
            return redirect(url_for('get_SMB_online'))
        except Exception as e:
            return render_template('ImportPE.html', importUrl=url_for('post_pe_import_online'), error="Bad Import")

    @api.route('/smbstation/components/<idx>', methods=['DELETE'])
    @flask_login.login_required
    def delete_component(idx):
        nonlocal station, linCol, nonLinCol, formInfo, station_lock
        station_lock.acquire()
        try:
            station.delComponent(int(idx))
        finally:
            station_lock.release()
        return ("", 204)

    @api.route('/logout')
    @flask_login.login_required
    def logout():
        flask_login.logout_user()
        return redirect(url_for('get_main_page'))

    @api.route('/login', methods=['GET', 'POST'])
    def get_login_page():
        nonlocal IE_PASSWORD, IE_USERNAME, api
        if request.method == 'GET':
            if flask_login.current_user.is_authenticated:
                return redirect(url_for("get_main_page"))
            return render_template('login.html')
        username = request.form['username']
        password = request.form['password']
        if username == IE_USERNAME and password == IE_PASSWORD:
            api.config['SECRET_KEY'] = ''.join(random.choices(string.ascii_lowercase, k=32))
            user = User()
            user.id = username
            flask_login.login_user(user)
            return redirect(url_for("get_main_page"))
        return render_template('login.html', badLogin=True)

    @api.route('/', methods=['GET'])
    def get_main_page():
        return render_template('Index.html', auth=flask_login.current_user.is_authenticated)

    @api.route('/offline/smbstation', methods=['GET'])
    @flask_login.login_required
    def get_SMB():
        nonlocal station, formInfo, running
        return render_template('SMBStation.html', stationInfo=station.getColInfo(), readyNext=station.getZoneReady(),
                               formInfo=formInfo, running=running)

    @api.route('/offline/smbstation/components/simconfig', methods=['GET'])
    @flask_login.login_required
    def get_SMB_config():
        nonlocal station, formInfo, running
        return render_template('SimulationDefinition.html', stationInfo=station.getColInfo(), readyNext=station.getZoneReady(), formInfo=formInfo, running=running)

    @api.route('/offline/smbstation/components/simconfig', methods=['POST'])
    @flask_login.login_required
    def post_create_SMB():
        nonlocal station, station_lock
        formInfo["flowRate1"] = float(request.form.get("flowRate1"))
        formInfo["flowRate2"] = float(request.form.get("flowRate2"))
        formInfo["flowRate3"] = float(request.form.get("flowRate3"))
        formInfo["flowRate4"] = float(request.form.get("flowRate4"))
        formInfo["switchInterval"] = float(request.form.get("switchInterval"))
        formInfo["dt"] = float(request.form.get("dt"))
        formInfo["Nx"] = int(request.form.get("Nx"))
        formInfo["simtime"] = int(request.form.get("simtime"))
        station_lock.acquire()
        try:
            station.setFlowRateZone(1, formInfo["flowRate1"])
            station.setFlowRateZone(2, formInfo["flowRate2"])
            station.setFlowRateZone(3, formInfo["flowRate3"])
            station.setFlowRateZone(4, formInfo["flowRate4"])
            station.setSwitchInterval(formInfo["switchInterval"])
            station.setdt(formInfo["dt"])
            station.setNx(formInfo["Nx"])
        finally:
            station_lock.release()
        return redirect(url_for('get_simulation'))

    @api.route('/offline/column', methods=['POST'])
    @flask_login.login_required
    def post_add_column():
        add_column(request)
        return redirect(url_for('get_SMB'))

    @api.route('/column/<zone>/<idx>', methods=['DELETE'])
    @flask_login.login_required
    def delete_column(zone, idx):
        nonlocal station, linCol, nonLinCol, formInfo
        station.delColZone(int(zone), int(idx))
        return ("", 204)

    @api.route('/online/smbstation/components/plcmaping', methods=['GET'])
    @flask_login.login_required
    def get_online_plcmaping():
        nonlocal formInfo, station
        try:
            tags = get_PLC_tags(login_to_Dataservice())
            return render_template("tagMapping.html", formInfo=formInfo, plcTags=tags, compList=list(station.getCompInfo().keys()))
        except:
            return render_template("tagMapping.html", formInfo=formInfo, plcTags=[], compList=list(station.getCompInfo().keys()), error="Failed to establish connection to Dataservice.")


    @api.route('/online/smbstation/components/plcmaping', methods=['POST'])
    @flask_login.login_required
    def post_online_plcmaping():
        nonlocal tagMap, timeStart, dataserviceThreadHandler, formInfo, event, running, station_lock
        compList = list(station.getCompInfo().keys())
        cookies = login_to_Dataservice()
        formInfo["flowRateUnits"] = float(request.form.get("flowRateUnits"))
        tagMap["flowRateEluent"] = request.form.get("flowRateEluent")
        tagMap["flowRateExtract"] = request.form.get("flowRateExtract")
        tagMap["flowRateFeed"] = request.form.get("flowRateFeed")
        tagMap["flowRateRaffinate"] = request.form.get("flowRateRaffinate")
        tagMap["flowRateRecycle"] = request.form.get("flowRateRecycle")
        tagMap["eluent"] = request.form.get("eluent")
        while True:
            formInfo["flowRateEluent"] = get_data_single(request.form.get("eluent"), cookies)
            if not formInfo["flowRateEluent"] == 0:
                break
        tagMap["extract"] = request.form.get("extract")
        while True:
            formInfo["flowRateExtract"] = get_data_single(request.form.get("extract"), cookies)
            if not formInfo["flowRateExtract"] == 0:
                break
        tagMap["feed"] = request.form.get("feed")
        while True:
            formInfo["flowRateFeed"] = get_data_single(request.form.get("feed"), cookies)
            if not formInfo["flowRateFeed"] == 0:
                break
        tagMap["raffinate"] = request.form.get("raffinate")
        while True:
            formInfo["flowRateRaffinate"] = get_data_single(request.form.get("raffinate"), cookies)
            if not formInfo["flowRateRaffinate"] == 0:
                break
        tagMap["recycle"] = request.form.get("recycle")
        while True:
            formInfo["flowRateRecycle"] = get_data_single(request.form.get("recycle"), cookies)
            if not formInfo["flowRateRecycle"] == 0:
                break
        fix_flowrates()
        tagMap["switchPosition"] = request.form.get("switchPosition")
        formInfo["switchPosition"] = get_data_single(request.form.get("switchPosition"), cookies)
        tagMap["switchInterval"] = request.form.get("switchIntervalTag")
        tagMap["timeToSwitch"] = request.form.get("timeToSwitchTag")
        formInfo["switchInterval"] = get_data_single(request.form.get("switchIntervalTag"), cookies)/1000
        formInfo["dt"] = float(request.form.get("dt"))
        formInfo["Nx"] = int(request.form.get("Nx"))
        formInfo["horizon"] = int(request.form.get("horizon"))
        formInfo["backhorizon"] = int(request.form.get("backhorizon"))
        formInfo["liveTime"] = int(request.form.get("liveTime"))
        formInfo["concUnits"] = float(request.form.get("concUnits"))
        station_lock.acquire()
        try:
            for comp in compList:
                tagMap["extract" + comp] = request.form.get("extract" + comp)
                formInfo["extract" + comp] = get_data_single(request.form.get("extract" + comp), cookies)
                tagMap["feed" + comp] = request.form.get("feed" + comp)
                feedConc = get_data_single(request.form.get("feed" + comp), cookies)
                station.updateComponentByName(comp, feedConc=feedConc*formInfo["concUnits"])
                tagMap["raffinate" + comp] = request.form.get("raffinate" + comp)
                formInfo["raffinate" + comp] = get_data_single(request.form.get("raffinate" + comp), cookies)
            print
            station.setFlowRateZone(1, formInfo["flowRate1"]*formInfo["flowRateUnits"])
            station.setFlowRateZone(2, formInfo["flowRate2"]*formInfo["flowRateUnits"])
            station.setFlowRateZone(3, formInfo["flowRate3"]*formInfo["flowRateUnits"])
            station.setFlowRateZone(4, formInfo["flowRate4"]*formInfo["flowRateUnits"])
            station.setSwitchInterval(formInfo["switchInterval"])
            station.setdt(formInfo["dt"])
            station.setNx(formInfo["Nx"])
            station.initCols()
        finally:
            station_lock.release()
        running = True
        timeStart = datetime.datetime.utcnow().isoformat() + "Z"
        event.clear()
        dataserviceThreadHandler = threading.Thread(target=periodic_task, args=(update_live_data, 5, login_to_Dataservice()), daemon=True, name="BackgroundUpdateData")
        dataserviceThreadHandler.start()
        threading.Thread(target=periodic_task, args=(update_feed_concentrations, 30), daemon=True,
                         name="BackgroundUpdateData2").start()
        threading.Thread(target=periodic_task, args=(convert_data, 5), daemon=True,
                         name="BackgroundUpdateData3").start()
        #stationUpdateHandler = threading.Thread(target=periodic_task, args=(update_station, 5), daemon=True, name="BackgroundUpdateStation")
        #stationUpdateHandler.start()
        return redirect(url_for("get_simulation_online"))

    @api.route('/online/smbstation', methods=['GET'])
    @flask_login.login_required
    def get_SMB_online():
        nonlocal station, formInfo, running
        return render_template('SMBStation.html', stationInfo=station.getColInfo(), readyNext=station.getZoneReady(),
                               formInfo=formInfo, running=running, online=True)

    @api.route('/online/connection', methods=['GET'])
    def get_dataservice_connection():
        if check_dataservice_connection(login_to_Dataservice()):
            return "Yes"
        return "No"
    @api.route('/online/column', methods=['POST'])
    @flask_login.login_required
    def post_add_column_online():
        add_column(request)
        return redirect(url_for('get_SMB_online'))

    '''
    @api.route('/smbstation/components/simconfig/simulation/data', methods=['GET'])
    def get_simulation_data():
        nonlocal station
        responseDict = {}
        responseDict["compList"] = list(station.getCompInfo().keys())
        resList10 = []
        for ii in range(10):
            res = station.step()
            resList10.append(res)
        responseDict["data"] = resList10
        return json.dumps(responseDict)'''

    @api.route('/offline/smbstation/components/simconfig/simulation/flowrate', methods=['POST'])
    @flask_login.login_required
    def post_simulation_flowrate():
        nonlocal station, formInfo, station_lock
        try:
            formInfo["zone"] = int(request.form.get("flowRateZone"))
            formInfo["flowRate" + str(formInfo["zone"])] = float(request.form.get("flowRate"))
            station_lock.acquire()
            try:
                station.setFlowRateZone(formInfo["zone"], formInfo["flowRate" + str(formInfo["zone"])])
                station.initCols()
            finally:
                station_lock.release()
            return ("Success", 200)
        except Exception as e:
            print(e)
            return ("Fail", 400)

    @api.route('/offline/smbstation/components/simconfig/simulation/switch', methods=['POST'])
    @flask_login.login_required
    def post_simulation_switch():
        nonlocal station, formInfo, station_lock
        try:
            formInfo["switch"] = float(request.form.get("switch"))
            station_lock.acquire()
            try:
                station.setSwitchInterval(formInfo["switch"])
                station.initCols()
            finally:
                station_lock.release()
            return ("Success", 200)
        except Exception as e:
            print(e)
            return ("Fail", 400)

    @api.route('/online/smbstation/components/simconfig/simulation/change', methods=['POST'])
    @flask_login.login_required
    def post_simulation_change_online():
        nonlocal station, formInfo, stationSaveState, station_lock
        stationSaveState["horizon"] = formInfo["horizon"]
        stationSaveState["countdown"] = formInfo["horizon"]
        stationSaveState["flowRate1"] = formInfo["flowRate1"]
        stationSaveState["flowRate2"] = formInfo["flowRate2"]
        stationSaveState["flowRate3"] = formInfo["flowRate3"]
        stationSaveState["flowRate4"] = formInfo["flowRate4"]
        stationSaveState["switchInterval"] = formInfo["switchInterval"]
        formInfo["flowRateEluent"] = float(request.form.get("flowRateEluent"))
        formInfo["flowRateExtract"] = float(request.form.get("flowRateExtract"))
        formInfo["flowRateFeed"] = float(request.form.get("flowRateFeed"))
        formInfo["flowRateRaffinate"] = float(request.form.get("flowRateRaffinate"))
        formInfo["flowRateRecycle"] = float(request.form.get("flowRateRecycle"))
        formInfo["switchInterval"] = int(request.form.get("switch"))
        try:
            fix_flowrates()
        except:
            return "Flow Rates don't match."
        station_lock.acquire()
        try:
            formInfo["lastChange"] = station.timer
            stationSaveState["station"] = station.deepCopy()
            compList = list(station.getCompInfo().keys())
            for comp in compList:
                station.updateComponentByName(name=comp, feedConc=float(request.form.get("feedConc"+comp))*formInfo["concUnits"])
            update_station()
        finally:
            station_lock.release()
        return ("Success", 200)

    @api.route('/online/smbstation/components/simconfig/simulation/forcechange', methods=['POST'])
    @flask_login.login_required
    def post_simulation_force_change_online():
        nonlocal station, formInfo, stationSaveState, station_lock
        formInfo["flowRateEluent"] = float(request.form.get("flowRateEluent"))
        formInfo["flowRateExtract"] = float(request.form.get("flowRateExtract"))
        formInfo["flowRateFeed"] = float(request.form.get("flowRateFeed"))
        formInfo["flowRateRaffinate"] = float(request.form.get("flowRateRaffinate"))
        formInfo["flowRateRecycle"] = float(request.form.get("flowRateRecycle"))
        formInfo["switchInterval"] = int(request.form.get("switch"))
        station_lock.acquire()
        try:
            formInfo["lastChange"] = station.timer
            formInfo["secondLastChange"] = station.timer
            compList = list(station.getCompInfo().keys())
            for comp in compList:
                station.updateComponentByName(name=comp, feedConc=float(request.form.get("feedConc"+comp))*formInfo["concUnits"])
            fix_flowrates()
            update_station()
        finally:
            station_lock.release()
        send_to_PLC()
        return ("Success", 200)

    MQTT_USER = "edge"
    MQTT_PASSWORD = "edge"
    MQTT_IP = "ie-databus"
    MQTT_PORT = 1883
    TOPIC = "ie/d/j/simatic/v1/s7c1/dp/w/PLC0"
    TOPIC2 = "ie/m/j/simatic/v1/s7c1/dp"
    mqtt_sequence = 1
    '''client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_IP, port=MQTT_PORT)
    client.subscribe(TOPIC2)
    client.loop_start()'''

    @api.route('/online/smbstation/components/simconfig/simulation/change/keep', methods=['POST'])
    @flask_login.login_required
    def post_simulation_change_keep_online():
        nonlocal station, formInfo, stationSaveState
        formInfo["secondLastChange"] = formInfo["lastChange"]
        send_to_PLC()
        stationSaveState = {}
        return ("Success", 200)

    def send_to_PLC():
        nonlocal mqtt_sequence, station, formInfo, tagMap, tagIdMap, TOPIC#, client
        message = {"seq": mqtt_sequence, "vals": []}
        mqtt_sequence += 1
        timeStamp = datetime.datetime.utcnow().isoformat() + "Z"
        message["vals"].append({"id": tagIdMap[tagMap["eluent"]], "val": formInfo["flowRateEluent"], "ts": timeStamp, "qc": 3})
        message["vals"].append({"id": tagIdMap[tagMap["extract"]], "val": formInfo["flowRateExtract"], "ts": timeStamp, "qc": 3})
        message["vals"].append({"id": tagIdMap[tagMap["feed"]], "val": formInfo["flowRateFeed"], "ts": timeStamp, "qc": 3})
        message["vals"].append({"id": tagIdMap[tagMap["raffinate"]], "val": formInfo["flowRateRaffinate"], "ts": timeStamp, "qc": 3})
        message["vals"].append({"id": tagIdMap[tagMap["recycle"]], "val": formInfo["flowRateRecycle"], "ts": timeStamp, "qc": 3})
        message["vals"].append({"id": tagIdMap[tagMap["switchInterval"]], "val": formInfo["switchInterval"]*1000, "ts": timeStamp, "qc": 3})
        compInfo = station.getCompInfo()
        for comp, info in compInfo.items():
            message["vals"].append({"id": tagIdMap[tagMap["feed" + comp]], "val": info["Feed Concentration"], "ts": timeStamp, "qc": 3})
        print(json.dumps(message))
        #client.publish(TOPIC, json.dumps(message))

    @api.route('/online/smbstation/components/simconfig/simulation/change/notkeep', methods=['POST'])
    @flask_login.login_required
    def post_simulation_change_notkeep_online():
        nonlocal station, formInfo, stationSaveState, station_lock
        formInfo["flowRate1"] = stationSaveState["flowRate1"]
        formInfo["flowRate2"] = stationSaveState["flowRate2"]
        formInfo["flowRate3"] = stationSaveState["flowRate3"]
        formInfo["flowRate4"] = stationSaveState["flowRate4"]
        formInfo["switchInterval"] = stationSaveState["switchInterval"]
        station_lock.acquire()
        try:
            formInfo["lastChange"] = formInfo["secondLastChange"]
            station = stationSaveState["station"]
            responseDict = {}
            responseDict["compList"] = list(station.getCompInfo().keys())
            responseDict["data"] = {}
            responseDict["data"]["raffinate"] = []
            responseDict["data"]["extract"] = []
            for i in range(len(responseDict["compList"])):
                responseDict["data"]["raffinate"].append([])
                responseDict["data"]["extract"].append([])
            for i in np.arange(0, stationSaveState["horizon"] - stationSaveState["countdown"], formInfo["dt"]):  # loop for each time step
                res = station.step()  # step
                for idx, x in enumerate(res[1][-1]):  # loop through components in last column in zone 1
                    responseDict["data"]["extract"][idx].append(x[-1])  # append last conc value of given component
                for idx, x in enumerate(res[3][-1]):  # loop through components in last column in zone 3
                    responseDict["data"]["raffinate"][idx].append(x[-1])  # append last conc value of given component
        finally:
            station_lock.release()
        onlineMemory["horizon"]["data"] = responseDict["data"]
        stationSaveState = {}
        return json.dumps(responseDict)


    @api.route('/offline/smbstation/components/simconfig/simulation', methods=['GET'])
    @flask_login.login_required
    def get_simulation():
        nonlocal station, running, formInfo
        station.initCols()
        running = True
        return render_template('OfflineSimulationPage.html', formInfo=formInfo, colInfo=station.getColInfo())

    port = int(os.environ.get('PORT', 5000))
    api.run(debug=True, host='0.0.0.0', port=port)