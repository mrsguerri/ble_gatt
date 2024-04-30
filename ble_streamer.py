import argparse
import asyncio
import logging
from bleak import BleakClient, BleakScanner, BLEDevice

logger = logging.getLogger(__name__)

async def findByName(args: argparse.Namespace) -> BLEDevice:
    device = await BleakScanner.find_device_by_name(args.name, cb=dict(use_bdaddr=True))
    if device is None:
        logger.error('Could not find device with name $s', args.name)
    return device

async def findByAddress(args: argparse.Namespace) -> BLEDevice:
    device = await BleakScanner.find_device_by_address(args.address, cb=dict(use_bdaddr=True))
    if device is None:
        logger.error('Could not find device with address %s', args.address)
    return device

async def connect(args: argparse.Namespace, numTries: int = 2) -> BLEDevice:
    foundDevice = None
    for i in range(1, numTries + 1):
        logger.info(f'Connection attempt {i} out of {numTries}...')
        if args.name is not None:
            foundDevice = await findByName(args)
        else:
            foundDevice = await findByAddress(args)
        if foundDevice is None:
            await asyncio.sleep(2)
        else:
            return foundDevice
        raise FileNotFoundError('No device with this name or address')

async def connected(device: BLEDevice, args: argparse.Namespace):
    async with BleakClient(device, services=args.services) as client:
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
    logger.info('Disconnecting')

async def main(args: argparse.Namespace):
    logger.info('Scanning...')
    device = None
    try:
        device = await connect(args)
    except FileNotFoundError as err:
        logger.error(err)
        return

    if device is not None:
        logger.info('Connecting...')
        await connected(device, args)
        logger.info('Disconnected')

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    device_group = parser.add_mutually_exclusive_group(required=True)
    device_group.add_argument('--name', metavar='<name>', help='The name of the bluetooth device to connect to.')
    device_group.add_argument('--address', metavar='<address>', help='The address of the bluetooth device to connect to.')
    parser.add_argument('--services', metavar='<uuid>', nargs='+')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(name)-8s %(levelname)s: %(message)s')

    asyncio.run(main(args))