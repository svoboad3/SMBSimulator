import numpy as np
import scipy.interpolate as spi

# Class representing connecting tube between columns
class Tube:
    def __init__(self, deadVolume):
        # Initialize Tube object with a dead volume
        self.deadVolume = deadVolume
        self.columnType = "Connecting Tube"
        self.components = []

    def add(self, comp):
        # Add a component to the tube
        self.components.append(comp)

    def delByIdx(self, idx):
        # Delete a component from the tube based on its index
        del self.components[idx]

    def updateByIdx(self, idx, comp):
        # Update a component in the tube based on its index
        self.components[idx].update(comp)

    def init(self, flowRate, dt, dummyVal=0):
        # Initialize the tube with flow rate, time step, and optional dummy value
        self.flowRate = flowRate
        self.dt = dt
        self.t = (self.deadVolume / self.flowRate) * 3600
        self.deadSteps = int(self.t // self.dt)
        remainder = self.t % self.dt
        if remainder >= dt / 2:
            self.deadSteps += 1
        for comp in self.components:
            if not hasattr(comp, 'c'):
                # Initializes concentration vector if not yet present
                comp.c = np.zeros(self.deadSteps)
            else:
                # Recalculates length and concentrations of vector when flow rate or time step changes
                x = np.linspace(0, len(comp.c), len(comp.c))
                f = spi.CubicSpline(x, comp.c)
                xnew = np.linspace(0, len(comp.c), self.deadSteps)
                cnew = f(xnew)
                intgOld = np.trapz(comp.c, x)
                intgNew = np.trapz(cnew, xnew)
                massDiff = 1
                if intgNew != 0:
                    massDiff = intgOld / intgNew
                cnew = np.multiply(cnew, massDiff)
                comp.c = cnew

    def step(self, cins):
        # Perform a step in the tube with input concentrations
        output = []
        for comp, cin in zip(self.components, cins):
            comp.c = np.roll(comp.c, 1)
            comp.c[0] = cin
            output.append(comp.c.tolist())
        return output

    def getInfo(self):
        # Get information about the tube
        info = {}
        info["columnType"] = self.columnType
        info["deadVolume"] = self.deadVolume
        return info

    def deepCopy(self):
        # Create a deep copy of the Tube object
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