from SMB.MultipleComps.LinColumn import LinColumn
from SMB.MultipleComps.NonlinColumn import NonLinColumn
from SMB.MultipleComps.Tube import Tube
from SMB.GenericColumn import GenericColumn
from SMB.MultipleComps.Component import Component
import copy as cp

class SMBStation:
    def __init__(self):
        self.zones = {}
        self.zones[1] = []
        self.zones[2] = []
        self.zones[3] = []
        self.zones[4] = []
        self.cins = {}
        self.cins[1] = []
        self.cins[2] = []
        self.cins[3] = []
        self.cins[4] = []
        self.flowRates = {}
        self.flowRates[1] = -1
        self.flowRates[2] = -1
        self.flowRates[3] = -1
        self.flowRates[4] = -1
        self.outVals = []
        self.settings = {}
        self.components = []
        self.switchingEnabled = False
        self.interval = -1
        self.countdown = -1
        self.timer = 0
        self.colCount = 0
        self.switchState = 0

    def setFlowRateZone(self, zone, flowRate):
        self.flowRates[zone] = flowRate

    def setSwitchInterval(self, s):
        self.interval = s
        self.countdown = s
        if s <= 0:
            self.switchingEnabled = False
        else:
            self.switchingEnabled = True

    def setdt(self, dt):
        self.settings['dt'] = dt

    def setNx(self, Nx):
        self.settings['Nx'] = Nx

    # adds column and a tube before it
    def addColZone(self, zone, col, tube):
        for comp in self.components:
            col.add(comp.copy())
            tube.add(comp.copy())
        self.zones[zone].append(tube)
        self.zones[zone].append(col)
        self.cins[zone].append([])
        self.cins[zone].append([])
        self.colCount += 1


    # deletes column and a tube before it
    def delColZone(self, zone, idx):
        del self.zones[zone][idx]
        if idx%2 == 1:
            del self.zones[zone][idx-1]
        elif idx%2 == 0:
            del self.zones[zone][idx]
        self.colCount -= 1

    def addComponent(self, name, feedConc = 0, henryConst = -1, disperCoef = -1, langmuirConst = -1, saturCoef = -1):
        comp = Component(name)
        comp.feedConc = feedConc
        comp.henryConst = henryConst
        comp.disperCoef = disperCoef
        comp.langmuirConst = langmuirConst
        comp.saturCoef = saturCoef
        self.components.append(comp)
        for zone in self.zones:
            for col in self.zones[zone]:
                col.add(comp.copy())

    def delComponent(self, idx):
        del self.components[idx]
        for zone in self.zones:
            for col in self.zones[zone]:
                col.delByIdx(idx)

    def updateComponentByName(self, name, feedConc = 0, henryConst = -1, disperCoef = -1, langmuirConst = -1, saturCoef = -1):
        print(name, feedConc)
        for idx, comp in enumerate(self.components):
            if comp.name == name:
                if feedConc > 0:
                    comp.feedConc = feedConc
                if henryConst > 0:
                    comp.henryConst = henryConst
                if disperCoef > 0:
                    comp.disperCoef = disperCoef
                if langmuirConst > 0:
                    comp.langmuirConst = langmuirConst
                if saturCoef > 0:
                    comp.saturCoef = saturCoef
                for zone in self.zones:
                    for col in self.zones[zone]:
                        col.updateByIdx(idx, comp)
                return
        comp = Component(name)
        comp.feedConc = feedConc
        comp.henryConst = henryConst
        comp.disperCoef = disperCoef
        comp.langmuirConst = langmuirConst
        comp.saturCoef = saturCoef
        self.components.append(comp)
        for zone in self.zones:
            for col in self.zones[zone]:
                col.add(comp.copy())

    def updateComponentByIndex(self, idx, feedConc = 0, henryConst = -1, disperCoef = -1, langmuirConst = -1, saturCoef = -1):
        comp = self.components[idx]
        if feedConc > 0:
            comp.feedConc = feedConc
        if henryConst > 0:
            comp.henryConst = henryConst
        if disperCoef > 0:
            comp.disperCoef = disperCoef
        if langmuirConst > 0:
            comp.langmuirConst = langmuirConst
        if saturCoef > 0:
            comp.saturCoef = saturCoef
        for zone in self.zones:
            for col in self.zones[zone]:
                col.updateByIdx(idx, comp)

    def setPorosity(self, porosity):
        for zone in self.zones:
            for col in self.zones[zone]:
                if isinstance(col, GenericColumn):
                    col.porosity = porosity

    def initCols(self):
        for zone in self.zones:
            for idx, col in enumerate(self.zones[zone]):
                col.init(self.flowRates[zone], self.settings['dt'], self.settings['Nx'])
                self.cins[zone][idx] = [0] * len(col.components)
                self.outVals = [0] * len(col.components)

    def step(self, steps = 1):
        cins = [comp.feedConc for comp in self.components]
        for x in range(steps):
            self.timer += self.settings['dt']
            res = {}
            for zone in self.zones:
                res[zone] = []
                for i, col in enumerate(self.zones[zone]):
                    inVals = self.cins[zone][i]
                    self.cins[zone][i] = self.outVals
                    self.outVals = []
                    if i == 0 and zone == 3:
                        for idx, inVal in enumerate(inVals):
                            inVals[idx] = ((inVal * self.flowRates[2]) + (cins[idx] * self.flowRates[3]))/col.flowRate
                    if i == 0 and zone == 1:
                        for idx, inVal in enumerate(inVals):
                            inVals[idx] = (inVal * self.flowRates[2])/col.flowRate
                    x = col.step(inVals)
                    for x1 in x:
                        self.outVals.append(x1[-1])
                    res[zone].append(x)
            if self.switchingEnabled:
                self.countdown -= self.settings['dt']
                if self.countdown <= 0:
                    self.countdown += self.interval
                    self.rotate()
        return res

    def rotate(self):
        tmptube = self.zones[1][0]
        tmpcol = self.zones[1][1]
        self.zones[1].pop(0)
        self.zones[1].pop(0)
        self.zones[1].append(self.zones[2][0])
        self.zones[1].append(self.zones[2][1])
        self.zones[2].pop(0)
        self.zones[2].pop(0)
        self.zones[2].append(self.zones[3][0])
        self.zones[2].append(self.zones[3][1])
        self.zones[3].pop(0)
        self.zones[3].pop(0)
        self.zones[3].append(self.zones[4][0])
        self.zones[3].append(self.zones[4][1])
        self.zones[4].pop(0)
        self.zones[4].pop(0)
        self.zones[4].append(tmptube)
        self.zones[4].append(tmpcol)
        self.initCols()
        self.switchState = (self.switchState+1)%self.colCount

    def getColInfo(self):
        info = {}
        for zone in self.zones:
            info[zone] = []
            for col in self.zones[zone]:
                info[zone].append(col.getInfo())
        return info

    def getCompInfo(self):
        info = {}
        for comp in self.components:
            info[comp.name] = {}
            info[comp.name]["Feed Concentration"] = comp.feedConc
            info[comp.name]["Henry Constant"] = comp.henryConst
            info[comp.name]["Langmuir Constant"] = comp.langmuirConst
            info[comp.name]["Saturation Coefficient"] = comp.saturCoef
            info[comp.name]["Dispersion Coefficient"] = comp.disperCoef
        return info

    def getZoneReady(self):
        for zone in self.zones:
            if len(self.zones[zone]) == 0:
                return False
        return True

    def getSettingsInfo(self):
        info = {}
        info['Flow Rate'] = self.flowRates
        info['dt'] = self.settings['dt']
        info['Nx'] = self.settings['Nx']
        info['Switch Interval'] = self.interval
        info['Countdown'] = self.countdown
        info['timer'] = self.timer
        return info

    def deepCopy(self):
        copy = SMBStation()
        for zone in self.zones:
            for col in self.zones[zone]:
                copy.zones[zone].append(col.deepCopy())
        copy.cins = cp.deepcopy(self.cins)
        copy.flowRates = cp.deepcopy(self.flowRates)
        copy.outVals = cp.deepcopy(self.outVals)
        copy.settings = cp.deepcopy(self.settings)
        copy.components = [comp.copy() for comp in self.components]
        copy.outVals = cp.deepcopy(self.outVals)
        copy.switchingEnabled = self.switchingEnabled
        copy.timer = self.timer
        copy.colCount = self.colCount
        copy.switchState = self.switchState
        copy.interval = self.interval
        copy.countdown = self.countdown
        return copy