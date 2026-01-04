// Type definitions for IPC data
export interface BreathData {
  type: 'breath_data';
  frame_idx: number;
  rr_wave: number[];
  displacement: number[];
  flow_rate: number[];
  respiratory_rate: number;
  warning_id: number;
  is_in_bed?: boolean; // May be added by processing
}

export interface SCGData {
  type: 'scg_data';
  frame_idx: number;
  scg_waveform: number[];
  isArrhythmia: number;
}

export interface HeartRateData {
  type: 'heart_rate_data';
  heart_rate: number;
  hrv: number;
  stress_index: number;
  stress_level: string;
}

export interface HumanCheckData {
  type: 'human_check_data';
  status: string; // 'presence', 'absence'
}

export type IPCMessage = BreathData | SCGData | HeartRateData | HumanCheckData;

// Define window.electronAPI type
declare global {
  interface Window {
    electronAPI: {
      onData: (callback: (data: IPCMessage) => void) => void;
    };
  }
}

export const setupIPCListeners = (handlers: {
  onBreath?: (data: BreathData) => void;
  onSCG?: (data: SCGData) => void;
  onHeartRate?: (data: HeartRateData) => void;
  onHumanCheck?: (data: HumanCheckData) => void;
}) => {
  if (window.electronAPI) {
    window.electronAPI.onData((data: IPCMessage) => {
      switch (data.type) {
        case 'breath_data':
          handlers.onBreath?.(data);
          break;
        case 'scg_data':
          handlers.onSCG?.(data);
          break;
        case 'heart_rate_data':
          handlers.onHeartRate?.(data);
          break;
        case 'human_check_data':
          handlers.onHumanCheck?.(data);
          break;
      }
    });
  } else {
    console.warn('Electron IPC not available');
  }
};
