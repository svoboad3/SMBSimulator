import numpy as np
import math
from scipy import optimize
from SMB.GenericColumn import GenericColumn

class NonLinColumn(GenericColumn):
    def __init__(self, length, diameter, porosity):
        GenericColumn.__init__(self, length, diameter, porosity)
        self.columnType = "EDM with Noncompetetive Langmuir isotherm"

    def init(self, flowRate, dt, Nx):
        # Initialize column parameters
        self.flowRate = flowRate
        self.Nx = Nx
        self.dt = dt

        # Calculate flow speed
        self.flowSpeed = (self.flowRate * 1000 / 3600) / (math.pi * ((self.diameter / 2) ** 2) * self.porosity)

        # Create spatial grid
        self.x = np.linspace(0, self.length, self.Nx)
        self.dx = self.length/self.Nx # Calculating space step [mm]

        # Initialize component concentrations
        for comp in self.components:
            if not hasattr(comp, 'c'):
                comp.c = np.zeros(len(self.x))


    def step(self, cins):
        # Perform a step in the NonlinColumn by solving the system of equations
        output = []
        for comp, cin in zip(self.components, cins):
            # Solve the system of equations for each component
            sol = optimize.root(fun=self.function,
                                x0=comp.c,
                                method='hybr',
                                args=(comp.c, cin, self.porosity, comp.langmuirConst, comp.saturCoef, comp.disperCoef, self.flowSpeed))
            comp.c = sol.x
            output.append(comp.c.tolist())
        return output

    def function(self, c1, c0, feedCur, porosity, langmuirConst, saturCoef, disperCoef, flowSpeed):
        # Function solving matrix row for given input, used in optimization
        f = np.zeros(len(c0))  # Preparation of solution vector - will be optimized to 0
        for i in range(0, len(c0)):  # Main loop through all the vector's elements
            if i == 0:  # Left boundary
                # Apply boundary condition at the left boundary
                f[0] = ((((c0[1] - c0[0]) / self.dx) + ((c1[1] - c1[0]) / self.dx)) / 2) - (flowSpeed * (c1[0] - feedCur))
            elif i > 0 and i < self.Nx - 1:
                # Compute values for the interior points
                denominator0 = ((1 - porosity) * saturCoef * langmuirConst) / ((((-langmuirConst * c0[i] + 1) ** 2) * porosity) + 1)
                denominator1 = ((1 - porosity) * saturCoef * langmuirConst) / ((((-langmuirConst * c1[i] + 1) ** 2) * porosity) + 1)
                secondDer0 = (c0[i - 1] - 2 * c0[i] + c0[i + 1]) / (self.dx ** 2)
                secondDer1 = (c1[i - 1] - 2 * c1[i] + c1[i + 1]) / (self.dx ** 2)
                firstDer0 = (c0[i + 1] - c0[i - 1]) / (self.dx * 2)
                firstDer1 = (c1[i + 1] - c1[i - 1]) / (self.dx * 2)
                timeDer = (c1[i] - c0[i]) / self.dt
                disperElem = ((disperCoef / denominator0 * secondDer0) + (disperCoef / denominator1 * secondDer1)) / 2
                convElem = ((flowSpeed / denominator0 * firstDer0) + (flowSpeed / denominator1 * firstDer1)) / 2
                f[i] = disperElem - convElem - timeDer
            elif i == self.Nx - 1:  # Right boundary
                # Apply boundary condition at the right boundary
                f[self.Nx - 1] = ((((c0[self.Nx - 1] - c0[self.Nx - 2]) / self.dx) + ((c1[self.Nx - 1] - c1[self.Nx - 2]) / self.dx)) / 2)
        return f

    def deepCopy(self):
        # Create a deep copy of the NonLinColumn object
        copy = NonLinColumn(self.length, self.diameter, self.porosity)
        copy.columnType = self.columnType
        copy.flowRate = self.flowRate
        copy.Nx = self.Nx
        copy.dt = self.dt
        copy.flowSpeed = self.flowSpeed
        copy.x = self.x
        copy.dx = self.dx

        # Copy component data
        copy.components = [comp.copy() for comp in self.components]
        for comp, copycomp in zip(self.components, copy.components):
            copycomp.C1 = comp.C1
            copycomp.C2 = comp.C2
            copycomp.A = np.copy(comp.A)
            copycomp.B = np.copy(comp.B)
            copycomp.A_diag = np.copy(comp.A_diag)
            copycomp.Aabs = np.copy(comp.Aabs)
            copycomp.Babs = np.copy(comp.Babs)
            copycomp.c = np.copy(comp.c)

        return copy