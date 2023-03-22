from WebServer.WebServer import Web_Server

from SMB.MultipleComps.SMBStation import SMBStation
from SMB.MultipleComps.LinColumn import LinColumn
from SMB.MultipleComps.NonlinColumn import NonLinColumn
from SMB.MultipleComps.Tube import Tube
#from SMB.SMBStation import SMBStation
#from SMB.LinColumn import LinColumn
#from SMB.NonlinColumn import NonLinColumn
#from SMB.Tube import Tube
# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    Web_Server()
    '''tube = Tube(2)
    tube.init(150, 4)
    for i in range(24):
        tube.step(math.sin(i))
    plt.plot(tube.c)
    print(tube.c)
    tube.init(75, 4)
    print(tube.c)
    plt.plot(tube.c)
    plt.show()'''
    '''compCnt = 0
    smb = SMBStation()
    smb.setFlowRateZone(1, 140)
    smb.setFlowRateZone(2, 100)
    smb.setFlowRateZone(3, 180)
    smb.setFlowRateZone(4, 100)
    smb.setSwitchInterval(200)
    smb.addColZone(1, NonLinColumn(235, 16, 0.4), Tube(2))
    smb.addColZone(2, NonLinColumn(235, 16, 0.4), Tube(2))
    smb.addColZone(3, NonLinColumn(235, 16, 0.4), Tube(2))
    smb.addColZone(4, NonLinColumn(235, 16, 0.4), Tube(2))
    smb.addComponent("Sac", langmuirConst=1.5, saturCoef=5, disperCoef=3)
    smb.addComponent("Glc", langmuirConst=1.2, saturCoef=4, disperCoef=5)
    compCnt += 2
    smb.setdt(2)
    smb.setNx(30)
    smb.initCols()
    feedConc = [150e-3, 100e-3]
    stepCounter = 0
    steps = 1
    while True:
        res = smb.step(feedConc, steps)
        resLists = []
        for i in range(compCnt):
            resLists.append(np.array([]))
        for i in range(1, 5):
            for x in res[i]:
                for i2 in range(compCnt):
                    resLists[i2] = np.concatenate((resLists[i2], x[i2]))
        plt.axis([0, len(resLists[0]), 0, 0.5])
        for i in range(compCnt):
            plt.plot(resLists[i])
        plt.pause(0.05)
        plt.clf()
        stepCounter += steps
        if stepCounter > 3600:
            feedConc = 0'''
    '''compCnt = 0
    smb = SMBStation()
    smb.setFlowRateZone(1, 140)
    smb.setFlowRateZone(2, 100)
    smb.setFlowRateZone(3, 180)
    smb.setFlowRateZone(4, 100)
    smb.setSwitchInterval(200)
    smb.addColZone(1, NonLinColumn(235, 16, 0.4), Tube(2))
    smb.addColZone(2, NonLinColumn(235, 16, 0.4), Tube(2))
    smb.addColZone(3, NonLinColumn(235, 16, 0.4), Tube(2))
    smb.addColZone(4, NonLinColumn(235, 16, 0.4), Tube(2))
    smb.addNonLinCols(1.5, 5, 3)
    smb.addTubes()
    compCnt += 1
    smb.initCols(2, 30)
    feedConc = 150e-3
    stepCounter = 0
    steps = 1
    while True:
        res = smb.step(feedConc, steps)
        resList = np.array([])
        for i in range(1, 5):
            for x in res[i]:
                resList = np.concatenate((resList, x))
        plt.axis([0, len(resList), 0, 0.5])
        plt.plot(resList)
        plt.pause(0.05)
        plt.clf()
        stepCounter += steps
        if stepCounter > 3600:
            feedConc = 0'''

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
