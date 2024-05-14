from typing import Optional, List
import statesman
import asyncio
import argparse
import logging
from bleak import BleakClient, BleakError, BleakScanner, BLEDevice, BleakGATTCharacteristic

from PyQt6.QtWidgets import QApplication, QGridLayout, QWidget, QLabel, QPushButton, QLineEdit, QTextBrowser
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
import sys
from qasync import QEventLoop, asyncSlot

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
    async def start(self, args: argparse.Namespace):
        if args.name is not None:
            self.name = args.name
        else:
            self.addr = args.address
        
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
                            '''if 'read' in char.properties:
                                try:
                                    value = await client.read_gatt_char(char.uuid)
                                    print('Array of length', len(value), value)
                                    logger.info('  [Characteristic] %s (%s), value: %r', char, ','.join(char.properties), value)

                                    #print(value.decode(encoding='ascii'))
                                    #logger.info('Characteristic: %s Value: %s', char, value)
                                    #print(int.from_bytes(value, 'little'))
                                    #print(struct.unpack('f', value))
                                except Exception as ex:
                                    logger.error('Characteristic read error: %s', ex)'''
                            if 'notify' in char.properties:
                                #https://stackoverflow.com/questions/65120622/use-python-and-bleak-library-to-notify-a-bluetooth-gatt-device-but-the-result-i
                                #logger.info('  [Characteristic] %s (%s)', char, ','.join(char.properties))
                                await client.start_notify(char.uuid, self.notify)
                                await asyncio.sleep(1)
                                await client.stop_notify(char.uuid)

                            '''for descriptor in char.descriptors:
                                value = await client.read_gatt_descriptor(descriptor.handle)
                                logger.info('     [Descriptor] %s, Value: %r', descriptor, value)
                                print(value)
                                #print(struct.unpack('b', value))'''

        except BleakError as ex:
            logger.error(ex)
        
        """ async with BleakClient(address_or_ble_device=device, disconnected_callback=self.disconnected) as client:
            logger.info('Connected!')

            for service in client.services:
                logger.info('[Service] %s', service)
                for char in service.characteristics:
                    if 'read' in char.properties:
                        try:
                            value = await client.read_gatt_char(char.uuid)
                            logger.info('  [Characteristic] %s (%s), value: %r', char, ','.join(char.properties), value)
                        except Exception as ex:
                            logger.error('  [Characteristic] %s (%s), Error: %s', char, ','.join(char.properties), ex)
                    else:
                        logger.info('  [Characteristic] %s (%s)', char, ','.join(char.properties))

                    for descriptor in char.descriptors:
                        try:
                            value = await client.read_gatt_descriptor(descriptor.handle)
                            logger.info('     [Descriptor] %s, Value: %r', descriptor, value)
                        except Exception as ex:
                            logger.error('     [Descriptor] %s, Error: %s', descriptor, ex)
        await self.stop() """

    @statesman.before_event('execute')
    async def _print_status(self) -> None:
        print('Connected to device!')

    @statesman.event(source=States.__any__, target=States.stopping)
    async def stop(self):
        print('stop')

class Window(QWidget):

    txtStreamer: QTextBrowser = None
    stateMachine: StateMachine = None
    input: QLineEdit = None
    btnConnect: QPushButton = None
    loop: asyncio.AbstractEventLoop = None

    def __init__(self):
        super().__init__()
        self.__present()
        self.stateMachine = StateMachine()
        self.loop = asyncio.get_event_loop()
    
    def __textChanged(self):
        if len(self.input.text()) == 0:
            self.btnConnect.setEnabled(False)
        else:
            self.btnConnect.setEnabled(True)

    @asyncSlot()
    async def test(self):
        self.txtStreamer.setText('wow')

    #https://stackoverflow.com/questions/67152552/how-do-i-add-asyncio-task-to-pyqt5-event-loop-so-that-it-runs-and-avoids-the-nev
    async def __click(self):
        await self.test()
        #loop = asyncio.new_event_loop()
        #loop.call_soon_threadsafe(self.stateMachine.start(self.input.text()))
        #asyncio.run_coroutine_threadsafe(self.stateMachine.start(self.input.text()), loop)
        #asyncio.run(self.stateMachine.start(self.input.text()))

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
        self.show()

def main():
    #parser = argparse.ArgumentParser()
    #device_group = parser.add_mutually_exclusive_group(required=True)
    #device_group.add_argument('--name', metavar='<name>', type=str, help='The name of the bluetooth device to connect to.')
    #device_group.add_argument('--address', metavar='<address>', type=str, help='The address of the bluetooth device to connect to.')
    #parser.add_argument('--services', metavar='<uuid>', nargs='+')
    #args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(name)-8s %(levelname)s: %(message)s')

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = Window()
    #sys.exit(app.exec())
    with loop:
        loop.run_forever()

"""     stateMachine = StateMachine()
    await stateMachine.start(args) """

if __name__ == "__main__":
    main()
    #asyncio.run(main())