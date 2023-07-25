
class Component:
    """Class representing component of separating mixture.
    Contains:
    henryConst (float) - Henry constant parameter of EDM with linear isotherm.
    langmuirConst (float) - Langmuir constant parameter of EDM with langmuir isotherm.
    disperCoef (float) - Dispersion coeficient parameter of EDM.
    saturCoef (float) - Saturation coeficient parameter of EDM with langmuir isotherm.
    feedConc (float) - Feed concentration parameter of component.
    """
    def __init__(self, name):
        """Initialize a Component object with a given name"""
        self.name = name
        self.henryConst = -1  # Initialize Henry's constant with a default value of -1
        self.disperCoef = -1  # Initialize dispersion coefficient with a default value of -1
        self.langmuirConst = -1  # Initialize Langmuir's constant with a default value of -1
        self.saturCoef = -1  # Initialize saturation coefficient with a default value of -1
        self.feedConc = -1  # Initialize feed concentration with a default value of -1

    def copy(self):
        """Create a copy of the Component object"""
        comp = Component(self.name)
        comp.henryConst = self.henryConst
        comp.disperCoef = self.disperCoef
        comp.langmuirConst = self.langmuirConst
        comp.saturCoef = self.saturCoef
        comp.feedConc = self.feedConc
        return comp

    def update(self, comp):
        """Update the Component object with the values from another Component object"""
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