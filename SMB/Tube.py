import numpy as np
import scipy.interpolate as spi

class Tube:
    def __init__(self, deadVolume):
        self.deadVolume = deadVolume
        self.columnType = "Connecting Tube"

    def init(self, flowRate, dt, dummyVal = 0):
        self.flowRate = flowRate
        self.dt = dt
        self.t = (self.deadVolume/self.flowRate)*3600
        self.deadSteps = int(self.t//self.dt)
        remainder = self.t%self.dt
        if remainder >= dt/2:
            self.deadSteps += 1
        if not hasattr(self, 'c'):
            self.c = np.zeros(self.deadSteps)
        else:
            x = np.linspace(0, len(self.c), len(self.c))
            f = spi.CubicSpline(x, self.c)
            xnew = np.linspace(0, len(self.c), self.deadSteps)
            cnew = f(xnew)
            intgOld = np.trapz(self.c, x)
            intgNew = np.trapz(cnew, xnew)
            massDiff = 1
            if intgNew != 0:
                massDiff = intgOld / intgNew
            cnew = np.multiply(cnew, massDiff)
            self.c = cnew


    def step(self, cin, cprev = False):
        if cprev:
            self.c = cprev
        self.c = np.roll(self.c, 1)
        self.c[0] = cin
        return self.c

    def getInfo(self):
        info = {}
        info["columnType"] = self.columnType
        info["deadVolume"] = self.deadVolume
        return info