from typing import Optional, List
import statesman
import asyncio
import argparse
import logging
from bleak import BleakClient, BleakScanner, BLEDevice

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
            await self.execute()
    
    @statesman.event(source=States.connecting, target=States.executing)
    async def execute(self):
        async with BleakClient(self.device) as client:
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
        await self.stop()

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

    logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(name)-8s %(levelname)s: %(message)s')

    stateMachine = StateMachine()
    await stateMachine.start(args)

asyncio.run(_examples())