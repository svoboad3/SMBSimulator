from SMB.LinColumn import LinColumn
from SMB.NonlinColumn import NonLinColumn
from SMB.Tube import Tube

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
        self.outVal = 0
        self.settings = {}
        self.settings['Lin'] = {}
        self.settings['NonLin'] = {}
        self.switchingEnabled = False

    def setFlowRateZone(self, zone, flowRate):
        self.flowRates[zone] = flowRate

    def setSwitchInterval(self, s):
        self.switchingEnabled = True
        self.interval = s
        self.countdown = s

    def addColZone(self, zone, col, tube):
        self.zones[zone].append(tube)
        self.zones[zone].append(col)
        self.cins[zone].append(0)
        self.cins[zone].append(0)

    def addLinCols(self, henryConst, disperCoef):
        self.settings['Lin']['henryConst'] = henryConst
        self.settings['Lin']['disperCoef'] = disperCoef
        for zone in self.zones:
            for col in self.zones[zone]:
                if isinstance(col, LinColumn):
                    col.add(henryConst, disperCoef)

    def addNonLinCols(self, langmuirConst, saturCoef, disperCoef):
        self.settings['NonLin']['langmuirConst'] = langmuirConst
        self.settings['NonLin']['saturCoef'] = saturCoef
        self.settings['NonLin']['disperCoef'] = disperCoef
        for zone in self.zones:
            for col in self.zones[zone]:
                if isinstance(col, NonLinColumn):
                    col.add(langmuirConst, saturCoef, disperCoef)

    def addTubes(self):
        pass

    def initCols(self, dt, Nx):
        self.settings['Nx'] = Nx
        self.settings['dt'] = dt
        for zone in self.zones:
            for col in self.zones[zone]:
                col.init(self.flowRates[zone], dt, Nx)

    def step(self, cin, steps = 1):
        for x in range(steps):
            res = {}
            for zone in self.zones:
                res[zone] = []
                for i, col in enumerate(self.zones[zone]):
                    inVal = self.cins[zone][i]
                    self.cins[zone][i] = self.outVal
                    if i == 0 and zone == 3:
                        inVal = ((inVal * self.zones[2][-1].flowRate) + (cin * self.flowRates[3]))/col.flowRate
                    if i == 0 and zone == 1:
                        inVal = ((inVal * self.flowRates[3]))/col.flowRate
                    x = col.step(inVal)
                    self.outVal = x[-1]
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
        self.initCols(self.settings['dt'], self.settings['Nx'])