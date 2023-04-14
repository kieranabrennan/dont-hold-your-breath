from bleak import BleakClient
import asyncio
import time
import numpy as np
import math

class PolarH10:
    ## HEART RATE SERVICE
    HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
    # Characteristics
    HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"    # notify
    BODY_SENSOR_LOCATION_UUID = "00002a38-0000-1000-8000-00805f9b34fb"      # read

    ## USER DATA SERVICE
    USER_DATA_SERVICE_UUID = "0000181c-0000-1000-8000-00805f9b34fb"
    # Charateristics
    # ...

    ## DEVICE INFORMATION SERVICE
    DEVICE_INFORMATION_SERVICE = "0000180a-0000-1000-8000-00805f9b34fb"
    MANUFACTURER_NAME_UUID = "00002a29-0000-1000-8000-00805f9b34fb"
    MODEL_NBR_UUID = "00002a24-0000-1000-8000-00805f9b34fb"
    SERIAL_NUMBER_UUID = "00002a25-0000-1000-8000-00805f9b34fb"
    HARDWARE_REVISION_UUID = "00002a27-0000-1000-8000-00805f9b34fb"
    FIRMWARE_REVISION_UUID = "00002a26-0000-1000-8000-00805f9b34fb"
    SOFTWARE_REVISION_UUID = "00002a28-0000-1000-8000-00805f9b34fb"
    SYSTEM_ID_UUID = "00002a23-0000-1000-8000-00805f9b34fb"

    ## BATERY SERIVCE
    BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
    BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

    ## UNKNOWN 1 SERVICE
    U1_SERVICE_UUID = "6217ff4b-fb31-1140-ad5a-a45545d7ecf3"
    U1_CHAR1_UUID = "6217ff4c-c8ec-b1fb-1380-3ad986708e2d"      # read
    U1_CHAR2_UUID = "6217ff4d-91bb-91d0-7e2a-7cd3bda8a1f3"      # write-without-response, indicate

    ## Polar Measurement Data (PMD) Service
    PMD_SERVICE_UUID = "fb005c80-02e7-f387-1cad-8acd2d8df0c8"
    PMD_CHAR1_UUID = "fb005c81-02e7-f387-1cad-8acd2d8df0c8" #read, write, indicate – Request stream settings?
    PMD_CHAR2_UUID = "fb005c82-02e7-f387-1cad-8acd2d8df0c8" #notify – Start the notify stream?

    # POLAR ELECTRO Oy SERIVCE
    ELECTRO_SERVICE_UUID = "0000feee-0000-1000-8000-00805f9b34fb"
    ELECTRO_CHAR1_UUID = "fb005c51-02e7-f387-1cad-8acd2d8df0c8" #write-without-response, write, notify
    ELECTRO_CHAR2_UUID = "fb005c52-02e7-f387-1cad-8acd2d8df0c8" #notify
    ELECTRO_CHAR3_UUID = "fb005c53-02e7-f387-1cad-8acd2d8df0c8" #write-without-response, write

    # START PMD STREAM REQUEST
    HR_ENABLE = bytearray([0x01, 0x00])
    HR_DISABLE = bytearray([0x00, 0x00])

    # ECG and ACC Notify Requests
    ECG_WRITE = bytearray([0x02, 0x00, 0x00, 0x01, 0x82, 0x00, 0x01, 0x01, 0x0E, 0x00])
    ACC_WRITE = bytearray([0x02, 0x02, 0x00, 0x01, 0xC8, 0x00, 0x01, 0x01, 0x10, 0x00, 0x02, 0x01, 0x08, 0x00])

    ACC_SAMPLING_FREQ = 200
    ECG_SAMPLING_FREQ = 130

    def __init__(self, bleak_device):
        self.bleak_device = bleak_device
        self.acc_stream_values = []
        self.acc_stream_times = []
        self.acc_stream_start_time = None
        self.ibi_stream_values = []
        self.ibi_stream_times = []
        self.ecg_stream_values = []
        self.ecg_stream_times = []
        self.acc_data = None
        self.ibi_data = None
    
    def hr_data_conv(self, sender, data):  
        """
        `data` is formatted according to the GATT Characteristic and Object Type 0x2A37 Heart Rate Measurement which is one of the three characteristics included in the "GATT Service 0x180D Heart Rate".
        `data` can include the following bytes:
        - flags
            Always present.
            - bit 0: HR format (uint8 vs. uint16)
            - bit 1, 2: sensor contact status
            - bit 3: energy expenditure status
            - bit 4: RR interval status
        - HR
            Encoded by one or two bytes depending on flags/bit0. One byte is always present (uint8). Two bytes (uint16) are necessary to represent HR > 255.
        - energy expenditure
            Encoded by 2 bytes. Only present if flags/bit3.
        - inter-beat-intervals (IBIs)
            One IBI is encoded by 2 consecutive bytes. Up to 18 bytes depending on presence of uint16 HR format and energy expenditure.
        """
        byte0 = data[0] # heart rate format
        uint8_format = (byte0 & 1) == 0
        energy_expenditure = ((byte0 >> 3) & 1) == 1
        rr_interval = ((byte0 >> 4) & 1) == 1

        if not rr_interval:
            return

        first_rr_byte = 2
        if uint8_format:
            hr = data[1]
            pass
        else:
            hr = (data[2] << 8) | data[1] # uint16
            first_rr_byte += 1
        
        if energy_expenditure:
            # ee = (data[first_rr_byte + 1] << 8) | data[first_rr_byte]
            first_rr_byte += 2

        for i in range(first_rr_byte, len(data), 2):
            ibi = (data[i + 1] << 8) | data[i]
            # Polar H7, H9, and H10 record IBIs in 1/1024 seconds format.
            # Convert 1/1024 sec format to milliseconds.
            # TODO: move conversion to model and only convert if sensor doesn't
            # transmit data in milliseconds.
            ibi = np.ceil(ibi / 1024 * 1000)
            self.ibi_stream_values.extend([ibi])
            self.ibi_stream_times.extend([time.time_ns()/1.0e9])
            
    def acc_data_conv(self, sender, data): 
    # [02 EA 54 A2 42 8B 45 52 08 01 45 FF E4 FF B5 03 45 FF E4 FF B8 03 ...]
    # 02=ACC, 
    # EA 54 A2 42 8B 45 52 08 = last sample timestamp in nanoseconds, 
    # 01 = ACC frameType, 
    # sample0 = [45 FF E4 FF B5 03] x-axis(45 FF=-184 millig) y-axis(E4 FF=-28 millig) z-axis(B5 03=949 millig) , 
    # sample1, sample2,

        if data[0] == 0x02:
            if not bool(self.acc_stream_values):
                self.acc_stream_start_time = time.time_ns()/1.0e9
            
            timestamp = PolarH10.convert_to_unsigned_long(data, 1, 8)/1.0e9 # timestamp of the last sample
            frame_type = data[9]
            resolution = (frame_type + 1) * 8 # 16 bit
            time_step = 0.005 # 200 Hz sample rate
            step = math.ceil(resolution / 8.0)
            samples = data[10:] 
            n_samples = math.floor(len(samples)/(step*3))
            sample_timestamp = timestamp - (n_samples-1)*time_step
            offset = 0
            while offset < len(samples):
                x = PolarH10.convert_array_to_signed_int(samples, offset, step)
                offset += step
                y = PolarH10.convert_array_to_signed_int(samples, offset, step) 
                offset += step
                z = PolarH10.convert_array_to_signed_int(samples, offset, step) 
                offset += step
                # mag = np.linalg.norm([x, y, z])
                self.acc_stream_values.extend([[x, y, z]])
                self.acc_stream_times.extend([sample_timestamp])
                sample_timestamp += time_step
    
    def ecg_data_conv(self, sender, data):
    # [00 EA 1C AC CC 99 43 52 08 00 68 00 00 58 00 00 46 00 00 3D 00 00 32 00 00 26 00 00 16 00 00 04 00 00 ...]
    # 00 = ECG; EA 1C AC CC 99 43 52 08 = last sample timestamp in nanoseconds; 00 = ECG frameType, sample0 = [68 00 00] microVolts(104) , sample1, sample2, ....
        if data[0] == 0x00:
            timestamp = PolarH10.convert_to_unsigned_long(data, 1, 8)/1.0e9
            step = 3
            time_step = 1.0/ self.ECG_SAMPLING_FREQ
            samples = data[10:]
            n_samples = math.floor(len(samples)/step)
            offset = 0
            sample_timestamp = timestamp - (n_samples-1)*time_step
            while offset < len(samples):
                ecg = PolarH10.convert_array_to_signed_int(samples, offset, step)       
                offset += step
                self.ecg_stream_values.extend([ecg])
                self.ecg_stream_times.extend([sample_timestamp])
                sample_timestamp += time_step

    @staticmethod
    def convert_array_to_signed_int(data, offset, length):
        return int.from_bytes(
            bytearray(data[offset : offset + length]), byteorder="little", signed=True,
        )
    @staticmethod
    def convert_to_unsigned_long(data, offset, length):
        return int.from_bytes(
            bytearray(data[offset : offset + length]), byteorder="little", signed=False,
        )
    
    async def connect(self):
        self.bleak_client = BleakClient(self.bleak_device)
        await self.bleak_client.connect()
    
    async def disconnect(self):
        await self.bleak_client.disconnect()

    async def get_device_info(self):
        self.model_number = await self.bleak_client.read_gatt_char(PolarH10.MODEL_NBR_UUID)
        self.manufacturer_name = await self.bleak_client.read_gatt_char(PolarH10.MANUFACTURER_NAME_UUID)
        self.serial_number = await self.bleak_client.read_gatt_char(PolarH10.SERIAL_NUMBER_UUID)
        self.battery_level = await self.bleak_client.read_gatt_char(PolarH10.BATTERY_LEVEL_UUID)
        self.firmware_revision = await self.bleak_client.read_gatt_char(PolarH10.FIRMWARE_REVISION_UUID)
        self.hardware_revision = await self.bleak_client.read_gatt_char(PolarH10.HARDWARE_REVISION_UUID)
        self.software_revision = await self.bleak_client.read_gatt_char(PolarH10.SOFTWARE_REVISION_UUID)
    
    async def print_device_info(self):
        BLUE = "\033[94m"
        RESET = "\033[0m"
        print(f"Model Number: {BLUE}{''.join(map(chr, self.model_number))}{RESET}\n"
            f"Manufacturer Name: {BLUE}{''.join(map(chr, self.manufacturer_name))}{RESET}\n"
            f"Serial Number: {BLUE}{''.join(map(chr, self.serial_number))}{RESET}\n"
            f"Address: {BLUE}{self.bleak_device.address}{RESET}\n"
            f"Battery Level: {BLUE}{int(self.battery_level[0])}%{RESET}\n"
            f"Firmware Revision: {BLUE}{''.join(map(chr, self.firmware_revision))}{RESET}\n"
            f"Hardware Revision: {BLUE}{''.join(map(chr, self.hardware_revision))}{RESET}\n"
            f"Software Revision: {BLUE}{''.join(map(chr, self.software_revision))}{RESET}")

    async def start_acc_stream(self):
        await self.bleak_client.write_gatt_char(PolarH10.PMD_CHAR1_UUID, PolarH10.ACC_WRITE, response=True)
        await self.bleak_client.start_notify(PolarH10.PMD_CHAR2_UUID, self.acc_data_conv)
        print("Collecting ACC data...", flush=True)

    async def stop_acc_stream(self):
        await self.bleak_client.stop_notify(PolarH10.PMD_CHAR2_UUID)
        print("Stopping ACC data...", flush=True)

    async def start_hr_stream(self):
        await self.bleak_client.start_notify(PolarH10.HEART_RATE_MEASUREMENT_UUID, self.hr_data_conv)
        print("Collecting HR data...", flush=True)

    async def stop_hr_stream(self):
        await self.bleak_client.stop_notify(PolarH10.HEART_RATE_MEASUREMENT_UUID)
        print("Stopping HR data...", flush=True)
    
    def get_acc_data(self):
        
        acc_times = np.array(self.acc_stream_times)
        acc_times = acc_times - acc_times[0] # rel to start of acc session
        self.acc_data = {'times': acc_times, 'values': np.array(self.acc_stream_values)}

        return self.acc_data
    
    def get_ibi_data(self):

        ibi_times = np.array(self.ibi_stream_times)
        ibi_times = ibi_times - self.acc_stream_start_time # rel to start of acc session time in unix s
        self.ibi_data = {'times': ibi_times, 'values': np.array(self.ibi_stream_values)}

        return self.ibi_data
