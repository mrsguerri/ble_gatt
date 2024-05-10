from typing import Optional, List
import statesman
import asyncio
import argparse
import logging
import struct
from bleak import BleakClient, BleakError, BleakScanner, BLEDevice, BleakGATTCharacteristic

from PyQt6.QtWidgets import QApplication, QGridLayout, QWidget, QLabel, QPushButton, QLineEdit, QTextBrowser
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
import sys

PRESSURE_UUID:str='00002a6d-0000-1000-8000-00805f9b34fb'
TEMPERATURE_UUID:str='00002a6e-0000-1000-8000-00805f9b34fb'

logger = logging.getLogger(__name__)

class Window(QWidget):

    txtStreamer: QTextBrowser = None

    def __init__(self):
        super().__init__()
        self.__present()

    def __test(self):
        self.txtStreamer.setText('wow')

    def __present(self):
        lblConnect = QLabel(text="Device name or address:")
        btnConnect = QPushButton('Connect')
        btnConnect.setEnabled(False)

        input = QLineEdit(self)

        txtStreamer = QTextBrowser(self)
        txtStreamer.setText("")
        
        grid = QGridLayout()
        grid.setSpacing(3)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(3)

        grid.addWidget(lblConnect, 0, 0)
        grid.addWidget(input, 1, 0)
        grid.addWidget(btnConnect, 1, 1)
        grid.addWidget(txtStreamer, 2, 0, 6, 2)
 
        self.setLayout(grid)
        self.setGeometry(300, 300, 350, 400)
        self.setWindowTitle('Streamer')
        self.show()

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

async def _examples():
    # Let's play.
    parser = argparse.ArgumentParser()
    device_group = parser.add_mutually_exclusive_group(required=True)
    device_group.add_argument('--name', metavar='<name>', type=str, help='The name of the bluetooth device to connect to.')
    device_group.add_argument('--address', metavar='<address>', type=str, help='The address of the bluetooth device to connect to.')
    parser.add_argument('--services', metavar='<uuid>', nargs='+')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = Window()
    sys.exit(app.exec())

    logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(name)-8s %(levelname)s: %(message)s')

    stateMachine = StateMachine()
    await stateMachine.start(args)


asyncio.run(_examples())