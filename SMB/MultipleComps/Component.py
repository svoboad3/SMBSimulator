

class Component:
    def __init__(self, name):
        self.name = name
        self.henryConst = -1
        self.disperCoef = -1
        self.langmuirConst = -1
        self.saturCoef = -1
        self.feedConc = -1

    def copy(self):
        comp = Component(self.name)
        comp.henryConst = self.henryConst
        comp.disperCoef = self.disperCoef
        comp.langmuirConst = self.langmuirConst
        comp.saturCoef = self.saturCoef
        comp.feedConc = self.feedConc
        return comp