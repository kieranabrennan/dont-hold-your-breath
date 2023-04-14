from bleak import BleakScanner, BleakClient
import asyncio

# BLE Scanner – Scan for BLE devices and print out their details

async def main():
    devices = await BleakScanner.discover()
    for device in devices:
        print()
        print(f"Name: {device.name}")
        print(f"Address: {device.address}")
        print(f"Details: {device.details}")
        print(f"Metadata: {device.metadata}")
        print(f"RSSI: {device.rssi}")

    for device in devices:
        this_device = await BleakScanner.find_device_by_address(device.address)
        try:
            async with BleakClient(this_device) as client:
                print(f"Services found for device")
                print(f"Name: \033[92m{device.name}\033[0m")
                print(f"\tDevice Address:{device.address}")

                print("\tAll Services")
                for service in client.services:
                    print()
                    print(f"\t\tDescription: {service.description}")
                    print(f"\t\tService: {service}")
                
                print()
                print(f"\tService Characteristics:")
                for service in client.services:
                    print()
                    print(f"\t\tDescription: {service.description}")
                    print(f"\t\tService: {service}")

                    print(f"\t\tCharacteristics:")
                    for c in service.characteristics:
                        print()
                        print(f"\t\t\tUUID: {c.uuid}")
                        print(f"\t\t\tDescipriton: {c.description}")
                        print(f"\t\t\tHandle: {c.handle}")
                        print(f"\t\t\tProperties: {c.properties}")

                        print("\t\t\tDescriptors:")
                        for descrip in c.descriptors:
                            print(f"\t\t\t\t{descrip}")
        except Exception as e:
            print(f"Could not connect to device: {device}")
            print(f"Error: {e}")


asyncio.run(main())