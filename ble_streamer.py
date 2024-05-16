from typing import Optional, List
import asyncio
import logging
from bleak import BleakClient, BleakError, BleakScanner, BLEDevice, BleakGATTCharacteristic

from PySide6.QtWidgets import QApplication, QGridLayout, QWidget, QLabel, QPushButton, QLineEdit, QTextBrowser
import PySide6.QtAsyncio as QtAsyncio
from PySide6.QtCore import QTimer
import sys
import json

PRESSURE_UUID:str='00002a6d-0000-1000-8000-00805f9b34fb'
TEMPERATURE_UUID:str='00002a6e-0000-1000-8000-00805f9b34fb'

logger = logging.getLogger(__name__)

class BleConnector:

    names: list = []
    devices: list = []
    streamer: QTextBrowser = None
    prefix: str = None

    def add(self, name: str) -> None:
        self.names.append(name)

    async def find(self) -> None:
        for n in self.names:
            device: BLEDevice = None
            device = await BleakScanner.find_device_by_name(n, cb=dict(use_bdaddr=True))
            if device is None:
                logger.error('Could not find device with name $s', n)
                print('device does not exist')
            else:
                self.devices.append(device)

    async def connect(self, streamer: QTextBrowser):
        self.streamer = streamer
        await self.find()
        if len(self.devices) == 0:
            print('No devices to connect to.')
        else:
            await self.execute()
    
    def disconnected(self, client):
        print('disconnected')

    async def notify(self, sender: BleakGATTCharacteristic, data: bytearray):
        value:int = int.from_bytes(data, 'little')
        if sender.uuid == PRESSURE_UUID:
            print('Pressure:', value/10)
            self.streamer.append(self.prefix + ' Pressure: ' + str(value/10))
        elif sender.uuid == TEMPERATURE_UUID:
            print('Temperature:', value/100)
            self.streamer.append(self.prefix + ' Temperature: ' + str(value/100))

    async def execute(self):
        clients = []
        for d in self.devices:
            client = BleakClient(address_or_ble_device=d, disconnected_callback=self.disconnected)
            clients.append(client)
            try:
                await client.connect()
                print('Client', client, ' is connected')
            except BleakError as ex:
                print(ex)

        while 1:
            for c in clients:
                if c.is_connected:
                      self.prefix = str(c.address)
                      for service in client.services:
                        for char in service.characteristics:
                            if 'notify' in char.properties:
                                #https://stackoverflow.com/questions/65120622/use-python-and-bleak-library-to-notify-a-bluetooth-gatt-device-but-the-result-i
                                #logger.info('  [Characteristic] %s (%s)', char, ','.join(char.properties))
                                await c.start_notify(char.uuid, self.notify)
                                await asyncio.sleep(1)
                                await c.stop_notify(char.uuid)                  

    async def stop(self):
        print('stop')

class Window(QWidget):

    txtStreamer: QTextBrowser = None
    input: QLineEdit = None
    btnConnect: QPushButton = None
    timer: QTimer = None
    connector: BleConnector = None

    def __init__(self):
        super().__init__()
        #self.timer = QTimer()
        #self.timer.timeout.connect(self.__checkQueue)
        #self.timer.start(1000)
        self.connector = BleConnector()
        self.__present()
    
    def __textChanged(self):
        if len(self.input.text()) == 0:
            self.btnConnect.setEnabled(False)
        else:
            self.btnConnect.setEnabled(True)

    #https://stackoverflow.com/questions/67152552/how-do-i-add-asyncio-task-to-pyqt5-event-loop-so-that-it-runs-and-avoids-the-nev
    async def __click(self):
        try:
            file = open(self.input.text())
            jsonData = json.load(file)
            for n in jsonData['names']:
                self.connector.add(n)
            await self.connector.connect(self.txtStreamer)
        except OSError as ex:
            print(ex)

    def closeEvent(self, event):
        print('exit')

    def __present(self):
        lblConnect = QLabel(text="Json file:")
        self.btnConnect = QPushButton('Connect')
        self.btnConnect.setEnabled(False)
        self.btnConnect.clicked.connect(lambda: asyncio.ensure_future(self.__click()))

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

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(name)-8s %(levelname)s: %(message)s')

    app = QApplication(sys.argv)
    window = Window()
    QtAsyncio.run()

if __name__ == "__main__":
    main()