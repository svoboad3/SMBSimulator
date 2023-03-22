

class GenericColumn:
    def __init__(self, length, diameter, porosity):
        self.length = length
        self.diameter = diameter
        self.porosity = porosity
        self.columnType = "Generic column"

    def init(self, flowRate, dt, Nx):
        pass

    def step(self, cins):
        pass

    def getInfo(self):
        info = {}
        info["Column Type"] = self.columnType
        info["Length"] = self.length
        info["Diameter"] = self.diameter
        info["Porority"] = self.porosity
        return info