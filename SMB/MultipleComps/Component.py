

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

    def update(self, comp):
        if comp.henryConst > 0:
            self.henryConst = comp.henryConst
        if comp.disperCoef > 0:
            self.disperCoef = comp.disperCoef
        if comp.langmuirConst > 0:
            self.langmuirConst = comp.langmuirConst
        if comp.saturCoef > 0:
            self.saturCoef = comp.saturCoef
        if comp.feedConc > 0:
            self.feedConc = comp.feedConc