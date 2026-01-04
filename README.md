# Non-contact Vital Signs Monitoring System Based on Millimeter-Wave Radar

## Quick Start

### Prerequisites
- **Python**: 3.9+
- **Node.js**: 16+
- **Operating System**: Windows (Tested), Linux/macOS (Compatible)

### Backend Setup
1. Open a terminal in the project root.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the backend pipeline:
   ```bash
   python src/main_process.py
   ```
   *Note: Ensure the millimeter-wave radar device is connected via serial port (default: COM7). Check `src/config.py` to configure the port.*

### Frontend Setup
1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development application:
   ```bash
   npm run electron:dev
   ```

---

## Abstract
This project presents a non-contact vital signs monitoring system utilizing Frequency Modulated Continuous Wave (FMCW) millimeter-wave radar technology. The system is capable of real-time monitoring of human respiration and heart rate without physical contact, ensuring user comfort and privacy. By employing advanced signal processing algorithms—including FFT-based phase extraction, Seismocardiogram (SCG) waveform reconstruction, and autocorrelation-based heart rate estimation—the system achieves high accuracy and robustness. The software architecture adopts a decoupled frontend-backend design: a high-performance Python multiprocessing backend for data acquisition and signal processing, and an Electron-based Vue 3 frontend for real-time visualization and user interaction.

## 1. Introduction
Traditional vital signs monitoring requires contact sensors (e.g., ECG electrodes, pulse oximeters), which can be uncomfortable for long-term monitoring. Millimeter-wave radar offers a promising alternative by detecting minute chest wall displacements caused by cardiopulmonary activities. This system integrates radar hardware with a sophisticated software stack to provide a comprehensive health monitoring solution, suitable for home healthcare and elderly care scenarios.

## 2. System Architecture

The system follows a modular architecture designed for performance and scalability.

### 2.1 Hardware Layer
- **Sensor**: 24GHz/60GHz Millimeter-Wave Radar.
- **Interface**: UART (Serial Communication).
- **Data Format**: IQ (In-phase and Quadrature) signal frames containing range-bin data.

### 2.2 Backend (Python)
The backend is built using Python's `multiprocessing` module to handle high-frequency radar data (20Hz-200Hz) efficiently. Key components include:
- **Radar Acquisition Process (`mmw_radar.py`)**: Reads raw bytes from the serial port, decodes the frame structure, and extracts IQ data.
- **Broadcaster Process**: Distributes raw data to specialized processing units.
- **Signal Processing Processes**:
  - **SCG Process (`mmw_scg_grade.py`)**: Reconstructs SCG waveforms using phase differentiation and evaluates signal quality.
  - **Respiration Process (`mmw_breath.py`)**: Extracts respiratory waveforms using phase unwrapping and bandpass filtering.
  - **Heart Rate Process (`mmw_heart_rate.py`)**: Computes heart rate and Heart Rate Variability (HRV) metrics (SDNN, RMSSD, pNN50).
  - **Real-time Analysis (`mmw_realtime_analysis.py`)**: Performs instantaneous arrhythmia detection.
- **Data Management**:
  - **Database Writers (`mmw_database.py`)**: Asynchronously persists data to a local SQLite/MySQL database using Flask-SQLAlchemy.
  - **IPC Worker (`ipc_worker.py`)**: Streams processed data to the frontend via UDP/TCP sockets.

### 2.3 Frontend (Electron + Vue 3)
The frontend provides a user-friendly dashboard for visualization:
- **Framework**: Electron (Cross-platform desktop container) + Vue 3 (Reactive UI).
- **Visualization**: Apache ECharts for rendering real-time waveforms (SCG, Respiration, Heart Rate).
- **Communication**: Receives JSON payloads from the backend via Inter-Process Communication (IPC).

## 3. Methodology

### 3.1 Signal Preprocessing
Raw radar data undergoes Fast Fourier Transform (FFT) to generate Range Profiles. The target bin (range gate) corresponding to the subject's chest is dynamically selected based on energy maximization.

### 3.2 Respiration Monitoring
- **Phase Extraction**: The phase of the complex signal at the target bin is extracted.
- **Unwrapping**: Phase discontinuities are corrected using unwrapping algorithms.
- **Filtering**: A bandpass filter (0.1-0.5 Hz) isolates the respiratory component.
- **Smoothing**: Reflection padding is applied to minimize edge effects in real-time processing.

### 3.3 Heart Rate & HRV Estimation
- **SCG Reconstruction**: The second derivative of the phase signal is computed to obtain the Seismocardiogram (SCG), which reflects cardiac mechanical activity.
- **Peak Detection**: An adaptive peak detection algorithm identifies heartbeat fiducial points.
- **HR Calculation**: Heart rate is derived from the inter-beat intervals (IBI).
- **HRV Metrics**: Time-domain metrics (SDNN, RMSSD) are calculated from valid RR intervals to assess autonomic nervous system function.

## 4. File Structure

```
root
├── frontend/                # Electron + Vue 3 Frontend
│   ├── src/
│   │   ├── components/      # Visualization Cards (SCG, Breath, HR)
│   │   └── utils/           # IPC Communication Logic
│   └── electron/            # Main Electron Process
├── src/                     # Python Backend Source
│   ├── main_process.py      # Entry Point & Process Orchestrator
│   ├── mmw_radar.py         # Radar Data Acquisition
│   ├── mmw_breath.py        # Respiration Algorithm
│   ├── mmw_scg_grade.py     # SCG & Signal Quality Algorithm
│   ├── mmw_heart_rate.py    # Heart Rate & HRV Algorithm
│   ├── mmw_database.py      # Database Operations
│   └── config.py            # System Configuration
├── requirements.txt         # Python Dependencies
└── README.md                # Project Documentation
```

## 5. Technology Stack
- **Languages**: Python, TypeScript, HTML/CSS.
- **Libraries (Backend)**: `multiprocessing`, `numpy`, `scipy`, `pyserial`, `flask-sqlalchemy`.
- **Libraries (Frontend)**: `Vue.js`, `Element Plus`, `ECharts`, `Electron`.
- **Database**: SQLite (Default) / MySQL.

## 6. Conclusion
The developed system successfully demonstrates the feasibility of non-contact vital signs monitoring using millimeter-wave radar. The multi-process architecture ensures high real-time performance, while the integration of advanced signal processing algorithms guarantees data accuracy. The system provides a robust foundation for future applications in smart health and remote patient monitoring.
