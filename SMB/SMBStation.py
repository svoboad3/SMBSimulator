from SMB.GenericColumn import GenericColumn
from SMB.Component import Component
import copy as cp

class SMBStation:
    def __init__(self):
        # Initialize attributes
        self.zones = {}  # Dictionary to store zones and their columns
        self.zones[1] = []  # Columns in zone 1
        self.zones[2] = []  # Columns in zone 2
        self.zones[3] = []  # Columns in zone 3
        self.zones[4] = []  # Columns in zone 4

        self.cins = {}  # Dictionary to store inlet concentrations for each zone
        self.cins[1] = []  # Inlet concentrations for zone 1
        self.cins[2] = []  # Inlet concentrations for zone 2
        self.cins[3] = []  # Inlet concentrations for zone 3
        self.cins[4] = []  # Inlet concentrations for zone 4

        self.flowRates = {}  # Dictionary to store flow rates for each zone
        self.flowRates[1] = -1  # Flow rate for zone 1
        self.flowRates[2] = -1  # Flow rate for zone 2
        self.flowRates[3] = -1  # Flow rate for zone 3
        self.flowRates[4] = -1  # Flow rate for zone 4

        self.outVals = []  # List to store outlet concentrations
        self.settings = {}  # Dictionary to store simulation settings
        self.components = []  # List to store components
        self.switchingEnabled = False  # Flag to indicate if column rotation is enabled
        self.interval = -1  # Switch interval for column rotation
        self.countdown = -1  # Countdown timer for column rotation
        self.timer = 0  # Timer for simulation
        self.colCount = 0  # Number of columns
        self.switchState = 0  # Current state of column rotation

    def setFlowRateZone(self, zone, flowRate):
        # Set flow rate for a specific zone
        self.flowRates[zone] = flowRate

    def setSwitchInterval(self, s):
        # Set switch interval for column rotation
        self.interval = s
        self.countdown = s
        if s <= 0:
            self.switchingEnabled = False
        else:
            self.switchingEnabled = True

    def setdt(self, dt):
        # Set the time step for the simulation
        self.settings['dt'] = dt

    def setNx(self, Nx):
        # Set the number of grid points for the simulation
        self.settings['Nx'] = Nx

    def addColZone(self, zone, col, tube):
        # Add a column and a tube before it to a specific zone
        for comp in self.components:
            col.add(comp.copy())
            tube.add(comp.copy())
        self.zones[zone].append(tube)
        self.zones[zone].append(col)
        self.cins[zone].append([])
        self.cins[zone].append([])
        self.colCount += 1

    def delColZone(self, zone, idx):
        # Delete a column and a tube before it from a specific zone
        del self.zones[zone][idx]
        if idx%2 == 1:
            del self.zones[zone][idx-1]
        elif idx%2 == 0:
            del self.zones[zone][idx]
        self.colCount -= 1

    def createComponent(self, name, feedConc = 0, henryConst = -1, disperCoef = -1, langmuirConst = -1, saturCoef = -1):
        # Create a component to the SMB station
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
        # Delete a component from the SMB station
        del self.components[idx]
        for zone in self.zones:
            for col in self.zones[zone]:
                col.delByIdx(idx)

    def updateComponentByName(self, name, feedConc = 0, henryConst = -1, disperCoef = -1, langmuirConst = -1, saturCoef = -1):
        # Update the properties of a component based on its name
        # Finds component with given name and updates it
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
        # Creates component if it doesn't exists
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
        # Update the properties of a component based on its index
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
        # Set the porosity of all the columns in the SMB station
        for zone in self.zones:
            for col in self.zones[zone]:
                if isinstance(col, GenericColumn):
                    col.porosity = porosity

    def initCols(self):
        # Initialize the columns in the SMB station
        for zone in self.zones:
            for idx, col in enumerate(self.zones[zone]):
                col.init(self.flowRates[zone], self.settings['dt'], self.settings['Nx'])
                self.cins[zone][idx] = [0] * len(col.components)
                self.outVals = [0] * len(col.components)

    def step(self, steps = 1):
        # Perform one or more simulation steps
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
        # Rotate the columns in the SMB station based on the switch interval
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
        # Get information about each column in each zone
        info = {}
        for zone in self.zones:
            info[zone] = []
            for col in self.zones[zone]:
                info[zone].append(col.getInfo())
        return info

    def getCompInfo(self):
        # Get information about each component
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
        # Check if all zones have at least one column
        for zone in self.zones:
            if len(self.zones[zone]) == 0:
                return False
        return True

    def getSettingsInfo(self):
        # Get information about the settings of the station
        info = {}
        info['Flow Rate'] = self.flowRates
        info['dt'] = self.settings['dt']
        info['Nx'] = self.settings['Nx']
        info['Switch Interval'] = self.interval
        info['Countdown'] = self.countdown
        info['timer'] = self.timer
        return info

    def deepCopy(self):
        # Create a deep copy of the SMBStation object
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