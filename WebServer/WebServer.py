import os
import json
from flask import Flask, flash, request, redirect, url_for, send_file, render_template
from SMB.MultipleComps.SMBStation import SMBStation
from SMB.MultipleComps.LinColumn import LinColumn
from SMB.MultipleComps.NonlinColumn import NonLinColumn
from SMB.MultipleComps.Tube import Tube
import mongoengine as me
import numpy as np

def Web_Server():

    station = SMBStation()
    formInfo = {}
    linCol = False
    nonLinCol = False
    running = False

    api = Flask(__name__)
    api.config['SECRET_KEY'] = 'super secret key'
    api.config['SECURITY_PASSWORD_SALT'] = 'super secret salt'
    api.config['SESSION_TYPE'] = 'development'
    me.connect('ChroMo', host='192.168.1.42', port=27017)

    class DBExperiment(me.Document):
        uniquename = me.StringField(required=True, unique=True)
        name = me.StringField(required=True)
        experiment = me.StringField(required=True)

    class DBResult(me.Document):
        thr_id = me.IntField(required=True, unique=True)
        name = me.StringField(required=True)
        experiments = me.ListField(me.ReferenceField(DBExperiment))
        results = me.DictField(required=True)

    @api.route('/smbstation/components/simulation', methods=['DELETE'])
    def delete_simulation_data():
        nonlocal station, formInfo, linCol, nonLinCol, running
        del station
        station = SMBStation()
        del formInfo
        formInfo = {}
        linCol = False
        nonLinCol = False
        running = False
        return url_for('get_main_page')

    @api.route('/smbstation/components/simulation/data', methods=['GET'])
    def get_simulation_data():
        nonlocal station
        responseDict = {}
        responseDict["compList"] = list(station.getCompInfo().keys())
        resList10 = []
        for ii in range(10):
            res = station.step()
            resList10.append(res)
        responseDict["data"] = resList10
        return json.dumps(responseDict)

    @api.route('/smbstation/components/simulation', methods=['GET'])
    def get_simulation():
        nonlocal station, running
        station.initCols()
        running = True
        return render_template('SimulationPage.html', dataLink = url_for('get_simulation_data'), exportLink = url_for('get_export'))

    @api.route('/smbstation/components/export', methods=['GET'])
    def get_export():
        nonlocal station, formInfo
        export = {}
        export['col'] = station.getColInfo()
        export['comp'] = station.getCompInfo()
        export['settings'] = station.getSettingsInfo()
        return json.dumps(export)

    @api.route('/import', methods=['GET'])
    def get_import():
        return render_template('Import.html', importLink = url_for('post_import'))

    @api.route('/import', methods=['POST'])
    def post_import():
        nonlocal station
        try:
            data = json.loads(request.form.get("importString"))
            for zone in data['col']:
                for i in range(0,len(data['col'][zone]),2):
                    length = data['col'][zone][i + 1]['Length']
                    diameter = data['col'][zone][i + 1]['Diameter']
                    porosity = data['col'][zone][i + 1]['Porority']
                    deadVolume = data['col'][zone][i]['deadVolume']
                    if data['col'][zone][i+1]['Column Type'] == 'EDM with Linear isotherm':
                        station.addColZone(int(zone), LinColumn(length, diameter, porosity), Tube(deadVolume))
                    if data['col'][zone][i + 1]['Column Type'] == 'EDM with Noncompetetive Langmuir isotherm':
                        station.addColZone(int(zone), NonLinColumn(length, diameter, porosity), Tube(deadVolume))
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
            return redirect(url_for('get_SMB'))
        except:
            return render_template('Import.html', importLink = url_for('post_import'), error="Something went wrong with import - Try again")


    @api.route('/smbstation/components', methods=['GET'])
    def get_components():
        nonlocal station, formInfo, running
        return render_template('AddingComponents.html', compInfo=station.getCompInfo(), linCol=linCol, nonLinCol=nonLinCol, running=running)

    @api.route('/smbstation/components', methods=['POST'])
    def post_add_component():
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
        station.addComponent(name, feedConc=feedConc, henryConst=henryConst, disperCoef=disperCoef, langmuirConst=langmuirConst, saturCoef=saturCoef)
        return redirect(url_for('get_components'))

    @api.route('/smbstation/components/<idx>', methods=['DELETE'])
    def delete_component(idx):
        nonlocal station, linCol, nonLinCol, formInfo
        station.delComponent(int(idx))
        return ("", 204)

    @api.route('/', methods=['GET', 'POST'])
    def get_main_page():
        return render_template('Index.html')

    @api.route('/smbstation', methods=['GET'])
    def get_SMB():
        nonlocal station, formInfo, running
        return render_template('SMBStation.html', stationInfo=station.getColInfo(), readyNext=station.getZoneReady(), formInfo=formInfo, running=running)

    @api.route('/smbstation', methods=['POST'])
    def post_create_SMB():
        nonlocal station
        formInfo["flowRate1"] = float(request.form.get("flowRate1"))
        formInfo["flowRate2"] = float(request.form.get("flowRate2"))
        formInfo["flowRate3"] = float(request.form.get("flowRate3"))
        formInfo["flowRate4"] = float(request.form.get("flowRate4"))
        formInfo["switchInterval"] = float(request.form.get("switchInterval"))
        formInfo["dt"] = float(request.form.get("dt"))
        formInfo["Nx"] = int(request.form.get("Nx"))
        station.setFlowRateZone(1, formInfo["flowRate1"])
        station.setFlowRateZone(2, formInfo["flowRate2"])
        station.setFlowRateZone(3, formInfo["flowRate3"])
        station.setFlowRateZone(4, formInfo["flowRate4"])
        station.setSwitchInterval(formInfo["switchInterval"])
        station.setdt(formInfo["dt"])
        station.setNx(formInfo["Nx"])
        return redirect(url_for('get_components'))

    @api.route('/column', methods=['POST'])
    def post_add_column():
        nonlocal station, linCol, nonLinCol, formInfo
        formInfo["zone"] = int(request.form.get("zone"))
        formInfo["isotherm"] = request.form.get("isotherm")
        formInfo["colLength"] = float(request.form.get("colLength"))
        formInfo["colDiameter"] = float(request.form.get("colDiameter"))
        formInfo["porosity"] =  float(request.form.get("porosity"))
        formInfo["deadVol"] =  float(request.form.get("deadVol"))
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
        return redirect(url_for('get_SMB'))

    @api.route('/column/<zone>/<idx>', methods=['DELETE'])
    def delete_column(zone, idx):
        nonlocal station, linCol, nonLinCol, formInfo
        station.delColZone(int(zone), int(idx))
        return ("", 204)

    @api.route('/api/smbstation', methods=['GET'])
    def api_get_SMB():
        nonlocal station
        try:
            export = {}
            export['col'] = station.getColInfo()
            export['comp'] = station.getCompInfo()
            export['settings'] = station.getSettingsInfo()
            return json.dumps(export)
        except:
            return ("SMB station not created", 404)

    @api.route('/api/smbstation', methods=['POST'])
    def api_post_SMB():
        nonlocal station, running
        try:
            data = request.json
            for zone in data['col']:
                for i in range(0,len(data['col'][zone]),2):
                    length = data['col'][zone][i + 1]['Length']
                    diameter = data['col'][zone][i + 1]['Diameter']
                    porosity = data['col'][zone][i + 1]['Porority']
                    deadVolume = data['col'][zone][i]['deadVolume']
                    if data['col'][zone][i+1]['Column Type'] == 'EDM with Linear isotherm':
                        station.addColZone(int(zone), LinColumn(length, diameter, porosity), Tube(deadVolume))
                    if data['col'][zone][i + 1]['Column Type'] == 'EDM with Noncompetetive Langmuir isotherm':
                        station.addColZone(int(zone), NonLinColumn(length, diameter, porosity), Tube(deadVolume))
            for comp in data['comp']:
                feedConc = data['comp'][comp]['Feed Concentration']
                henryConst = data['comp'][comp]['Henry Constant']
                langmuirConst = data['comp'][comp]['Langmuir Constant']
                saturCoef = data['comp'][comp]['Saturation Coefficient']
                disperCoef = data['comp'][comp]['Dispersion Coefficient']
                station.addComponent(comp, feedConc=feedConc, henryConst=henryConst, disperCoef=disperCoef, langmuirConst=langmuirConst, saturCoef=saturCoef)
            station.setFlowRateZone(1, data['settings']['Flow Rate']['1'])
            station.setFlowRateZone(2, data['settings']['Flow Rate']['2'])
            station.setFlowRateZone(3, data['settings']['Flow Rate']['3'])
            station.setFlowRateZone(4, data['settings']['Flow Rate']['4'])
            station.setSwitchInterval(data['settings']['Switch Interval'])
            station.setdt(data['settings']['dt'])
            station.setNx(data['settings']['Nx'])
            return (url_for('api_get_data'), 201)
        except Exception as e:
            print(e)
            return (e, 400)

    @api.route('/api/smbstation/data', methods=['GET'])
    def api_get_data():
        nonlocal station, running
        if station.getZoneReady() and len(station.getCompInfo().keys()) > 0:
            station.initCols()
            running = True
            responseDict = {}
            responseDict["compList"] = list(station.getCompInfo().keys())
            resList10 = []
            for ii in range(10):
                res = station.step()
                resList10.append(res)
            responseDict["data"] = resList10
            return (json.dumps(responseDict), 200)
        else:
            return ("SMB station not created", 404)

    @api.route('/api/smbstation/dbresult', methods=['POST'])
    def api_post_smbstation_dbresults():
        nonlocal station, running
        if station.getZoneReady():
            try:
                data = request.json
                station.setPorosity(data['results']['porosity'])
                for comp in data['results']['compparams'].keys():
                    if len(data['results']['compparams'][comp]) == 2:
                        station.updateComponentByName(comp, henryConst=data['results']['compparams'][comp][0],
                                                      disperCoef=data['results']['compparams'][comp][1])
                    else:
                        station.updateComponentByName(comp, langmuirConst=data['results']['compparams'][comp][0],
                                                      disperCoef=data['results']['compparams'][comp][1],
                                                      saturCoef=data['results']['compparams'][comp][2])
                return ("", 200)
            except Exception as e:
                print(e)
                return (e, 400)
        return ("SMB station not created", 404)

    @api.route('/api/dbresult', methods=['GET'])
    def api_get_dbresults():
        return DBResult.objects.to_json()

    @api.route('/api/dbresult/<id>', methods=['GET'])
    def api_get_dbresult(id):
        for dbresult in DBResult.objects:
            if dbresult.thr_id == int(id):
                return dbresult.to_json()
        return ("", 404)

    port = int(os.environ.get('PORT', 5000))
    api.run(debug=True, host='0.0.0.0', port=port)