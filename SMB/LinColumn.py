import numpy as np
import math
from scipy import linalg
from SMB.GenericColumn import GenericColumn

class LinColumn(GenericColumn):
    def __init__(self, length, diameter, porosity):
        GenericColumn.__init__(self, length, diameter, porosity)
        self.columnType = "EDM with Linear isotherm"

    def add(self, henryConst, disperCoef):
        self.henryConst = henryConst
        self.disperCoef = disperCoef

    def init(self, flowRate, dt, Nx):
        self.flowRate = flowRate
        self.Nx = Nx
        self.dt = dt
        self.flowSpeed = (self.flowRate * 1000 / 3600) / (math.pi * ((self.diameter / 2) ** 2) * self.porosity)
        self.x = np.linspace(0, self.length, self.Nx)
        self.dx = self.length/self.Nx # Calculating space step [mm]
        self.C1 = (1/self.disperCoef)+((1+self.porosity)*self.henryConst/(self.porosity*self.disperCoef))
        self.C2 = self.flowSpeed/self.disperCoef
        # c[0,0] = feed[0]
        # Crank-Nicolson matrixes preparation
        # A.c(t+1) = B.c(t)x, where c(t+1) and c(t) are vectors of c(x) values
        # Preparation of boudaries in matrix A
        self.A = np.zeros((self.Nx, self.Nx))  # A matrix data structure
        self.A[0, 0] = ((2 / (self.dx ** 2)) + (self.C1 / self.dt)) / (-(1 / (self.dx ** 2)) - (self.C2 / (2 * self.dx)))  # Left boundary
        self.A[0, 1] = 1 - (((1 / (self.dx ** 2)) - (self.C2 / (2 * self.dx))) / (-(1 / (self.dx ** 2)) - (self.C2 / (2 * self.dx))))  # Left boundary
        self.A[self.Nx - 1, self.Nx - 2] = (((1 / (self.dx ** 2)) + (self.C2 / (2 * self.dx))) / (
                    -(1 / (self.dx ** 2)) + (self.C2 / (2 * self.dx)))) - 1  # Right boundary
        self.A[self.Nx - 1, self.Nx - 1] = -((2 / (self.dx ** 2)) + (self.C1 / self.dt)) / (-(1 / (self.dx ** 2)) + (self.C2 / (2 * self.dx)))  # Right Boundary
        # Preparation of boudaries in matrix B
        self.B = np.zeros((self.Nx, self.Nx))  # B matrix data structure
        self.B[0, 0] = (2 * self.dx * self.flowSpeed) + ((self.C1 / self.dt) / (-(1 / (self.dx ** 2)) - (self.C2 / (2 * self.dx))))  # Left boundary
        self.B[self.Nx - 1, self.Nx - 1] = -((self.C1 / self.dt) / (-(1 / (self.dx ** 2)) + (self.C2 / (2 * self.dx))))  # Right boundary
        # Filling up Matrixes A and B
        for i in range(1, self.Nx - 1):
            self.A[i, i - 1] = - ((self.dt / (2 * self.dx)) * ((1 / (self.C1 * self.dx)) + (self.C2 / 2)))
            self.A[i, i] = 1 + (dt / (self.C1 * self.dx ** 2))
            self.A[i, i + 1] = - (self.dt / (2 * self.dx)) * ((1 / (self.C1 * self.dx)) - (self.C2 / 2))
            self.B[i, i - 1] = ((self.dt / (2 * self.dx)) * ((1 / (self.C1 * self.dx)) + (self.C2 / 2)))
            self.B[i, i] = 1 - (self.dt / (self.C1 * self.dx ** 2))
            self.B[i, i + 1] = (self.dt / (2 * self.dx)) * ((1 / (self.C1 * self.dx)) - (self.C2 / 2))
        self.A_diag = self.diagonal_form(self.A)
        self.Aabs = np.abs(self.A)
        self.Babs = np.abs(self.B)
        if not hasattr(self, 'c'):
            self.c = np.zeros(len(self.x))


    def step(self, cin, cprev = False):
        if cprev:
            self.c = cprev
        b = self.B.dot(self.c)
        b[0] = b[0] - (self.flowSpeed * 2 * self.dx * cin)  # From left boundary
        self.c = linalg.solve_banded((1, 1), self.A_diag, b)
        return self.c

    def diagonal_form(self, a, lower=1, upper=1):
        # Transforms banded matrix into diagonal ordered form
        # allows to use scipy.linalg.solve_banded
        n = a.shape[1]
        assert (np.all(a.shape == (n, n)))
        ab = np.zeros((2 * n - 1, n))
        for i in range(n):
            ab[i, (n - 1) - i:] = np.diagonal(a, (n - 1) - i)
        for i in range(n - 1):
            ab[(2 * n - 2) - i, :i + 1] = np.diagonal(a, i - (n - 1))
        mid_row_inx = int(ab.shape[0] / 2)
        upper_rows = [mid_row_inx - i for i in range(1, upper + 1)]
        upper_rows.reverse()
        upper_rows.append(mid_row_inx)
        lower_rows = [mid_row_inx + i for i in range(1, lower + 1)]
        keep_rows = upper_rows + lower_rows
        ab = ab[keep_rows, :]
        return ab