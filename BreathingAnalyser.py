import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, find_peaks
import numpy as np

# BreathingAnalyser – Class to analyse breathing rate and heart rate variability from accelerometer and interbeat interval (IBI) data

class BreathingAnalyser:
    def __init__(self, acc_data, ibi_data):
        self.acc_times, self.acc_values = acc_data['times'], acc_data['values']/100.0
        self.ibi_times, self.ibi_values = ibi_data['times'], ibi_data['values']
        self.acc_values_norm = np.linalg.norm(self.acc_values, axis=1)
        self.acc_low_pass = []
        self.acc_low_pass_norm = []
        self.acc_values_filt = []
        self.acc_values_filt_norm = []
        self.breathing_signal = []
        self.br_values = []
        self.br_times = []
        self.br_values_smooth = []
        self.breath_peaks = []
        self.hrv_values = []
        self.hrv_times = []
        self.hrv_values_interp = []
        self.ibi_extremes_idx = []

        self.calculate_breathing_signal()
        self.calculate_breathing_rate()
        self.calculate_heart_rate_variability()

    def calculate_breathing_signal(self):
        # Gravity Filter
        cutoff_freq = 0.04  # Hz
        filter_order = 2
        nyquist_freq = 0.5 * 200 # PolarH10.ACC_SAMPLING_FREQ
        cutoff_norm = cutoff_freq / nyquist_freq
        b, a = butter(filter_order, cutoff_norm, btype='low')
        self.acc_low_pass = np.zeros_like(self.acc_values)
        for i in range(3):
            self.acc_low_pass[:, i] = filtfilt(b, a, self.acc_values[:, i])
        
        self.acc_low_pass_norm = np.linalg.norm(self.acc_low_pass, axis=1)
        self.acc_values_filt = self.acc_values - self.acc_low_pass
        self.acc_values_filt_norm = np.linalg.norm(self.acc_values_filt, axis=1)

        # Noise Filter
        nyquist_freq = 0.5 * 200 #PolarH10.ACC_SAMPLING_FREQ  
        cutoff_freq = 0.5  
        filter_order = 2  
        b, a = butter(filter_order, cutoff_freq / nyquist_freq, btype='low')
        self.breathing_signal = filtfilt(b, a, self.acc_values_filt_norm)

    def calculate_breathing_rate(self):

        # Breathing rate
        peak_threshold = 0.02 #0.04
        breathing_peak_signal = -self.breathing_signal # More reliable to low acceleration points, i.e. mid-inhale and mid-exhale
        breath_peaks_all, _ = find_peaks(breathing_peak_signal)
        # Iterate through each peak index
        for i in range(len(breath_peaks_all)):
            peak_val = breathing_peak_signal[breath_peaks_all[i]]

            if i == 0:
                self.breath_peaks.append(breath_peaks_all[i])
            else: 
                # Use the previous peak as the starting point to search for the preceding trough
                start_idx = breath_peaks_all[i-1]
                end_idx = breath_peaks_all[i]
                trough_idx = np.argmin(breathing_peak_signal[start_idx:end_idx]) + start_idx
                trough_val = breathing_peak_signal[trough_idx]
                
                if peak_val - trough_val >= peak_threshold:
                    # If the peak meets the criteria, add it to the list of valid peaks
                    self.breath_peaks.append(breath_peaks_all[i])

        # Calculate breathing rate from valid peaks
        self.br_values = 60/(np.diff(self.acc_times[self.breath_peaks])*2)
        self.br_times = self.acc_times[self.breath_peaks[1:]]
        window_size = 3
        self.br_values_smooth = np.zeros_like(self.br_values)
        for i in range(len(self.br_values)):
            if i < window_size:
                self.br_values_smooth[i] = np.mean(self.br_values[0:i+window_size])
            elif i > len(self.br_values) - window_size:
                self.br_values_smooth[i] = np.mean(self.br_values[i-window_size:])
            else:
                self.br_values_smooth[i] = np.mean(self.br_values[i-window_size:i+window_size])

    def calculate_heart_rate_variability(self):

        # Heart rate variability
        ibi_peaks_idx, _ = find_peaks(self.ibi_values)
        ibi_troughs_idx, _ = find_peaks(-self.ibi_values)
        ibi_extremes_raw_idx = np.append(ibi_peaks_idx, ibi_troughs_idx)
        ibi_extremes_raw_idx = np.sort(ibi_extremes_raw_idx)
        p2p_buffer = np.zeros(3)
        for i in range(len(ibi_extremes_raw_idx)):
            p2p_threshold = 0.15*np.amax(p2p_buffer) # peak-to-peak must be greater than 30% of max of the last 3
            if i == 0:
                self.ibi_extremes_idx.append(ibi_extremes_raw_idx[i])
            else:
                p2p = abs(self.ibi_values[ibi_extremes_raw_idx[i]] - self.ibi_values[ibi_extremes_raw_idx[i-1]])
                if p2p > p2p_threshold: 
                    self.ibi_extremes_idx.append(ibi_extremes_raw_idx[i])
                    p2p_buffer = np.roll(p2p_buffer, -1)
                    p2p_buffer[-1] = p2p
        
        ibi_extreme_times = self.ibi_times[self.ibi_extremes_idx]
        ibi_extreme_values = self.ibi_values[self.ibi_extremes_idx]

        self.hrv_values = abs(np.diff(ibi_extreme_values))
        self.hrv_times = ibi_extreme_times[1:]
        self.hrv_values_interp = np.interp(self.br_times, self.hrv_times, self.hrv_values)

    def show_breathing_signal(self):

        fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(10, 7))
        axes[0].plot(self.acc_times, self.acc_values[:, 0], color='r', marker='o', label='x', markersize=0.3, linewidth=0.05)
        axes[0].plot(self.acc_times, self.acc_low_pass[:, 0], color='gray', marker='o', label='gravity', markersize=0.3, linewidth=0.5)
        axes[0].legend()
        axes[0].set_ylabel('X Acceleration')

        axes[1].plot(self.acc_times, self.acc_values[:, 1], color='g', marker='o', label='y', markersize=0.3, linewidth=0.05)
        axes[1].plot(self.acc_times, self.acc_low_pass[:, 1], color='gray', marker='o', label='y', markersize=0.3, linewidth=0.5)
        axes[1].set_ylabel('Y Acceleration')

        axes[2].plot(self.acc_times, self.acc_values[:, 2], color='b', marker='o', label='z', markersize=0.3, linewidth=0.05)
        axes[2].plot(self.acc_times, self.acc_low_pass[:, 2], color='gray', marker='o', label='z', markersize=0.3, linewidth=0.5)
        axes[2].set_ylabel('Z Acceleration')

        axes[3].plot(self.acc_times, self.acc_values_norm, color='k', marker='o', label='z', markersize=0.3, linewidth=0.05)
        axes[3].plot(self.acc_times, self.acc_low_pass_norm, color='gray', marker='o', label='z', markersize=0.3, linewidth=0.5)
        axes[3].set_ylabel('Norm')
        axes[3].set_xlabel('Time')
        plt.tight_layout()
        plt.gcf().canvas.manager.set_window_title("Accelerometer & Low Pass data")
        plt.show(block=False)

        # Filtered
        plt.figure()
        plt.plot(self.acc_times, self.acc_values_filt[:, 0], color='r', marker='o', label='x', markersize=0.2, linewidth = 0.1)
        plt.plot(self.acc_times, self.acc_values_filt[:, 1], color='g', marker='o', label='y', markersize=0.2, linewidth = 0.1)
        plt.plot(self.acc_times, self.acc_values_filt[:, 2], color='b', marker='o', label='z', markersize=0.2, linewidth = 0.1)
        plt.gcf().canvas.manager.set_window_title("Filtered Data")
        plt.legend()
        plt.xlabel('Time')
        plt.ylabel('Acceleration (filtered)')
        plt.show(block=False)

    def show_heart_rate_variability(self):

        # Breath peaks and IBI peaks
        fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(11, 6), sharex=True)
        axes[0].plot(self.acc_times, self.acc_values_filt_norm, color='k', marker='o', label='norm', markersize=0.05, linewidth = 0)
        axes[0].plot(self.acc_times, self.breathing_signal, color='b', marker='o', label='x', markersize=0.5, linewidth = 0.3)
        axes[0].vlines(self.acc_times[self.breath_peaks], ymin=np.min(self.breathing_signal), ymax=np.max(self.breathing_signal), color='b', linewidth=0.2)
        axes[0].set_ylim(0.9*np.min(self.breathing_signal), 1.1*np.max(self.breathing_signal))
        fig.suptitle(f"Average breath rate: {np.average(self.br_values):.1f} bpm")
        axes[0].set_xlabel('Time')
        axes[0].set_ylabel('Breathing Acc Mag.', color='b')
        axes[0].tick_params(axis='y', labelcolor='b')
        axes[1].plot(self.ibi_times, self.ibi_values, color='r', marker='o', label='y', markersize=3, linewidth=2)
        axes[1].vlines(self.ibi_times[self.ibi_extremes_idx], ymin=np.min(self.ibi_values), ymax=np.max(self.ibi_values), color='r', linewidth=0.2)
        axes[1].set_ylabel('Interbeat interval', color='r')
        axes[1].tick_params(axis='y', labelcolor='r')
        plt.show(block=False)

        # BR and HRV over time
        fig, ax1 = plt.subplots(figsize=(11, 6))
        ax2 = ax1.twinx()
        ax1.plot(self.br_times, self.br_values, color='b', marker='o', label='x', markersize=3, linewidth=1)
        ax1.plot(self.br_times, self.br_values_smooth, color='b', marker='o', label='x', markersize=0, linewidth=2, linestyle='--')
        ax1.set_xlabel('Time')
        ax1.set_ylabel('Breath rate (bpm)', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax2.plot(self.hrv_times, self.hrv_values, color='r', marker='o', label='hrv', markersize=3, linewidth=2)
        ax2.plot(self.br_times, self.hrv_values_interp, color='gray', marker='o', label='hrv_interp', markersize=0, linewidth=1, linestyle='--')
        ax2.set_ylabel('HRV (ms)', color='r')
        ax2.tick_params(axis='y', labelcolor='r')
        ax2.set_xlabel('Time')
        plt.show(block=False)

        # Breathing rate vs hrv
        plt.figure()
        plt.plot(self.br_values_smooth, self.hrv_values_interp, color='k', marker='o', label='y', markersize=3, linewidth=0)
        plt.xlabel('Breath rate')
        plt.ylabel('HRV')
        plt.show() 