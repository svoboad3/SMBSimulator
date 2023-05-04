import numpy as np
import scipy.interpolate as spi
from SMB.MultipleComps.Component import Component

class Tube:
    def __init__(self, deadVolume):
        self.deadVolume = deadVolume
        self.columnType = "Connecting Tube"
        self.components = []

    def add(self, comp):
        self.components.append(comp)

    def delByIdx(self, idx):
        del self.components[idx]

    def updateByIdx(self, idx, comp):
        self.components[idx].update(comp)

    def init(self, flowRate, dt, dummyVal = 0):
        self.flowRate = flowRate
        self.dt = dt
        self.t = (self.deadVolume/self.flowRate)*3600
        self.deadSteps = int(self.t//self.dt)
        remainder = self.t%self.dt
        if remainder >= dt/2:
            self.deadSteps += 1
        for comp in self.components:
            if not hasattr(comp, 'c'):
                comp.c = np.zeros(self.deadSteps)
            else:
                x = np.linspace(0, len(comp.c), len(comp.c))
                f = spi.CubicSpline(x, comp.c)
                xnew = np.linspace(0, len(comp.c), self.deadSteps)
                cnew = f(xnew)
                intgOld = np.trapz(comp.c, x)
                intgNew = np.trapz(cnew, xnew)
                massDiff = 1
                if intgNew != 0:
                    massDiff = intgOld/intgNew
                cnew = np.multiply(cnew, massDiff)
                comp.c = cnew


    def step(self, cins):
        output = []
        for comp, cin in zip(self.components, cins):
            comp.c = np.roll(comp.c, 1)
            comp.c[0] = cin
            output.append(comp.c.tolist())
        return output

    def getInfo(self):
        info = {}
        info["columnType"] = self.columnType
        info["deadVolume"] = self.deadVolume
        return info

    def deepCopy(self):
        copy = Tube(self.deadVolume)
        copy.columnType = self.columnType
        copy.flowRate = self.flowRate
        copy.dt = self.dt
        copy.t = self.t
        copy.deadSteps = self.deadSteps
        copy.components = [comp.copy() for comp in self.components]
        for comp, copycomp in zip(self.components, copy.components):
            copycomp.c = np.copy(comp.c)
        return copy