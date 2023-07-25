from pythonfmu import Fmi2Causality, Fmi2Slave, Integer, Real, String
try:
    from SMB.SMBStation import SMBStation
    from SMB.LinColumn import LinColumn
    from SMB.Tube import Tube
except ImportError:  # Trick to be able to generate the FMU
    SMBStation, LinColumn, Tube = None, None, None

class FMUSlave(Fmi2Slave):

    author = "Adam Svoboda"
    description = "Test FMU"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.flowRate1 = 180
        self.flowRate2 = 140
        self.flowRate3 = 220
        self.flowRate4 = 120
        self.register_variable(Real("flowRate1", causality=Fmi2Causality.input))
        self.register_variable(Real("flowRate2", causality=Fmi2Causality.input))
        self.register_variable(Real("flowRate3", causality=Fmi2Causality.input))
        self.register_variable(Real("flowRate4", causality=Fmi2Causality.input))


        self.columnLength = 200
        self.columnDiameter = 16
        self.porosity = 0.4
        self.deadVolume = 2
        self.register_variable(Real("columnLength", causality=Fmi2Causality.input))
        self.register_variable(Real("columnDiameter", causality=Fmi2Causality.input))
        self.register_variable(Real("porosity", causality=Fmi2Causality.input))
        self.register_variable(Real("deadVolume", causality=Fmi2Causality.input))

        self.componentName1 = "Man"
        self.feedConcentration1 = 15
        self.henryConstant1 = 2
        self.dispersionCoefficient1 = 5
        self.register_variable(String("componentName1", causality=Fmi2Causality.input))
        self.register_variable(Real("feedConcentration1", causality=Fmi2Causality.input))
        self.register_variable(Real("henryConstant1", causality=Fmi2Causality.input))
        self.register_variable(Real("dispersionCoefficient1", causality=Fmi2Causality.input))

        self.componentName2 = "Gal"
        self.feedConcentration2 = 10
        self.henryConstant2 = 5
        self.dispersionCoefficient2 = 8
        self.register_variable(String("componentName2", causality=Fmi2Causality.input))
        self.register_variable(Real("feedConcentration2", causality=Fmi2Causality.input))
        self.register_variable(Real("henryConstant2", causality=Fmi2Causality.input))
        self.register_variable(Real("dispersionCoefficient2", causality=Fmi2Causality.input))

        self.switchInterval = 500
        self.dt = 1e-3
        self.Nx = 60
        self.register_variable(Real("dt", causality=Fmi2Causality.input))
        self.register_variable(Integer("switchInterval", causality=Fmi2Causality.input))
        self.register_variable(Integer("Nx", causality=Fmi2Causality.input))

        self.extractOutput1 = 0
        self.extractOutput2 = 0
        self.raffinateOutput1 = 0
        self.raffinateOutput2 = 0
        self.register_variable(Real("extractOutput1", causality=Fmi2Causality.output))
        self.register_variable(Real("extractOutput2", causality=Fmi2Causality.output))
        self.register_variable(Real("raffinateOutput1", causality=Fmi2Causality.output))
        self.register_variable(Real("raffinateOutput2", causality=Fmi2Causality.output))

    def enter_initialization_mode(self):
        flowRates = {
            1: self.flowRate1,
            2: self.flowRate2,
            3: self.flowRate3,
            4: self.flowRate4
        }

        self.station = SMBStation()
        for zone in range(1,5):
            self.station.addColZone(zone, LinColumn(self.columnLength, self.columnDiameter, self.porosity), Tube(self.deadVolume))
            self.station.setFlowRateZone(zone, flowRates[zone])
        self.station.createComponent(name=self.componentName1, feedConc=self.feedConcentration1, henryConst=self.henryConstant1, disperCoef=self.dispersionCoefficient1)
        self.station.createComponent(name=self.componentName2, feedConc=self.feedConcentration2, henryConst=self.henryConstant2, disperCoef=self.dispersionCoefficient2)
        self.station.setSwitchInterval(self.switchInterval)
        self.station.setdt(self.dt)
        self.station.setNx(self.Nx)

    def exit_initialization_mode(self):
        self.station.initCols()


    def do_step(self, current_time, step_size):
        if step_size != self.dt:
            self.dt = step_size
            self.station.setdt(self.dt)
            self.station.initCols()
        stationResult = self.station.step()
        self.extractOutput1 = stationResult[1][-1][0][-1]
        self.extractOutput2 = stationResult[1][-1][1][-1]
        self.raffinateOutput1 = stationResult[3][-1][0][-1]
        self.raffinateOutput2 = stationResult[3][-1][1][-1]
        return True