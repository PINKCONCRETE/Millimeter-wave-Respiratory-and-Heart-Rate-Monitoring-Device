import matplotlib.pyplot as plt
import numpy as np

# A simple script to draw an example Heart Rate and Breath wave
t = np.linspace(0, 10, 500)
# Breath 0.3 Hz
breath = np.sin(2 * np.pi * 0.3 * t)
# Heart 1.2 Hz, much smaller amplitude
heart = 0.2 * np.sin(2 * np.pi * 1.2 * t)
signal = breath + heart

plt.figure(figsize=(10, 4))
plt.plot(t, signal, label='Mixed Signal', color='black')
plt.plot(t, breath, label='Breath (0.3Hz)', linestyle='--', color='blue')
plt.plot(t, heart, label='Heart (1.2Hz)', color='red')
plt.title('Simulated MMWave Radar Phase Signal')
plt.xlabel('Time (s)')
plt.ylabel('Amplitude')
plt.legend()
plt.tight_layout()
plt.savefig('paint/simulated_signal.png')
print('Chart generated at paint/simulated_signal.png')
