from typing import Optional, List
import statesman
import asyncio
import argparse
import logging
from bleak import BleakClient, BleakError, BleakScanner, BLEDevice, BleakGATTCharacteristic

from PySide6.QtWidgets import QApplication, QGridLayout, QWidget, QLabel, QPushButton, QLineEdit, QTextBrowser
import PySide6.QtAsyncio as QtAsyncio
from PySide6.QtCore import QTimer
import sys
from queue import Queue
from threading import Thread

PRESSURE_UUID:str='00002a6d-0000-1000-8000-00805f9b34fb'
TEMPERATURE_UUID:str='00002a6e-0000-1000-8000-00805f9b34fb'

logger = logging.getLogger(__name__)

class StateMachine(statesman.StateMachine):
    class States(statesman.StateEnum):
        starting='starting...'
        connecting='connecting'
        executing='executing'
        stopping='stopping'
    
    name: str = None
    addr: str = None

    async def find(self) -> BLEDevice:
        device: BLEDevice = None
        if self.name is not None:
            device = await BleakScanner.find_device_by_name(self.name, cb=dict(use_bdaddr=True))
            if device is None:
                logger.error('Could not find device with name $s', self.name)
        else:
            device = await BleakScanner.find_device_by_address(self.addr, cb=dict(use_bdaddr=True))
            if device is None:
                logger.error('Could not find device with address $s', self.addr)
        
        return device

    @statesman.event(None, States.starting)
    async def start(self, name: str):
        #if args.name is not None:
        #    self.name = args.name
        #else:
        #    self.addr = args.address
        self.name = name
        
        print('start')
        await self.connect()

    async def after_transition(self, transition: statesman.Transition) -> None:
        print('Transition from ', transition.source, ' to ', transition.target)

    @statesman.event(source=States.starting, target=States.connecting)
    async def connect(self):
        device = await self.find()
        if device is None:
            await self.stop()
        else:
            await self.execute(device)
    
    def disconnected(self, client):
        print('disconnected')

    async def notify(self, sender: BleakGATTCharacteristic, data: bytearray):
        value:int = int.from_bytes(data, 'little')
        if sender.uuid == PRESSURE_UUID:
            print('Pressure:', value/10)
        elif sender.uuid == TEMPERATURE_UUID:
            print('Temperature:', value/100)

    @statesman.event(source=States.connecting, target=States.executing)
    async def execute(self, device: BLEDevice):
        client = BleakClient(address_or_ble_device=device, disconnected_callback=self.disconnected)
        try:
            await client.connect()
            if client.is_connected:
                logger.info('Connected!')
                while 1:
                    for service in client.services:
                        for char in service.characteristics:
                            if 'notify' in char.properties:
                                #https://stackoverflow.com/questions/65120622/use-python-and-bleak-library-to-notify-a-bluetooth-gatt-device-but-the-result-i
                                #logger.info('  [Characteristic] %s (%s)', char, ','.join(char.properties))
                                await client.start_notify(char.uuid, self.notify)
                                await asyncio.sleep(1)
                                await client.stop_notify(char.uuid)

        except BleakError as ex:
            logger.error(ex)

    @statesman.before_event('execute')
    async def __print_status(self) -> None:
        print('Connected to device!')

    @statesman.event(source=States.__any__, target=States.stopping)
    async def stop(self):
        print('stop')

class Window(QWidget):

    txtStreamer: QTextBrowser = None
    input: QLineEdit = None
    btnConnect: QPushButton = None
    subscriptions: Queue = None
    publications: Queue = None
    timer: QTimer = None

    def __checkQueue(self):
        if not self.publications.empty():
            value = self.publications.get(block = True)
            self.txtStreamer.append(value)

    def __init__(self, subscriptions: Queue, publications: Queue):
        super().__init__()
        self.subscriptions = subscriptions
        self.publications = publications
        self.timer = QTimer()
        self.timer.timeout.connect(self.__checkQueue)
        self.timer.start(1000)
        self.__present()
    
    def __textChanged(self):
        if len(self.input.text()) == 0:
            self.btnConnect.setEnabled(False)
        else:
            self.btnConnect.setEnabled(True)

    #https://stackoverflow.com/questions/67152552/how-do-i-add-asyncio-task-to-pyqt5-event-loop-so-that-it-runs-and-avoids-the-nev
    def __click(self):
        self.subscriptions.put(self.input.text())
        print(self.subscriptions.qsize())

    def closeEvent(self, event):
        self.subscriptions.put('quit')

    def __present(self):
        lblConnect = QLabel(text="Device name or address:")
        self.btnConnect = QPushButton('Connect')
        self.btnConnect.setEnabled(False)
        self.btnConnect.clicked.connect(self.__click)

        self.input = QLineEdit(self)
        self.input.textChanged[str].connect(self.__textChanged)

        self.txtStreamer = QTextBrowser(self)
        self.txtStreamer.setText("")
        
        grid = QGridLayout()
        grid.setSpacing(3)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(3)

        grid.addWidget(lblConnect, 0, 0)
        grid.addWidget(self.input, 1, 0)
        grid.addWidget(self.btnConnect, 1, 1)
        grid.addWidget(self.txtStreamer, 2, 0, 6, 2)
 
        self.setLayout(grid)
        self.setGeometry(300, 300, 350, 400)
        self.setWindowTitle('Streamer')

        #Display after setting up the display elements
        self.show()

async def test(sub: Queue, pub: Queue):
    stop = False
    while not stop:
        if not sub.empty():
            value = sub.get(block=True)
            print(value)
            if value == 'quit':
                stop = True
            else:
                stateMachine = StateMachine()
                await stateMachine.start(value)

def bleMachine(subscriptions: Queue, publications: Queue):
    asyncio.run(test(subscriptions, publications))

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(name)-8s %(levelname)s: %(message)s')

    #Cross-thread communication
    subscriptions = Queue()
    publications = Queue()

    #Connections
    thread = Thread(target=bleMachine, args=(subscriptions, publications))
    thread.start()

    #GUI
    app = QApplication(sys.argv)
    window = Window(subscriptions, publications)
    QtAsyncio.run()




"""     stateMachine = StateMachine()
    await stateMachine.start(args) """

if __name__ == "__main__":
    main()