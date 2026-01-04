// Type definitions for IPC data
export interface BreathData {
  type: 'breath_data';
  frame_idx: number;
  rr_wave?: number[];
  displacement?: number[];
  flow_rate?: number[] | number;
  breath_value?: number;
  respiratory_rate: number;
  warning_id: number;
  is_in_bed?: boolean; // May be added by processing
}

export interface SCGData {
  type: 'scg_data';
  frame_idx: number;
  scg_waveform?: number[];
  scg_value?: number;
  isArrhythmia: number;
  max_bin?: number;
  score?: number;
}

export interface RealtimeAnalysisData {
  type: 'realtime_analysis';
  realtime_hr: number;
  realtime_premature: boolean;
  timestamp: number;
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
  has_human: boolean;
}

export interface FPSData {
  type: 'fps_stats';
  fps: number;
  timestamp: number;
}

export type IPCMessage = BreathData | SCGData | HeartRateData | HumanCheckData | FPSData | RealtimeAnalysisData;

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
  onFPS?: (data: FPSData) => void;
  onRealtimeAnalysis?: (data: RealtimeAnalysisData) => void;
}) => {
  if (window.electronAPI) {
    window.electronAPI.onData((data: IPCMessage) => {
      // Log received data for debugging
      // Clone data to avoid reference issues if modifying, and simplify arrays for logging if too large
      const logData = { ...data };
      if ('rr_wave' in logData && Array.isArray(logData.rr_wave) && logData.rr_wave.length > 20) {
          (logData as any).rr_wave = `Array(${logData.rr_wave.length})`;
      }
      if ('displacement' in logData && Array.isArray(logData.displacement) && logData.displacement.length > 20) {
          (logData as any).displacement = `Array(${logData.displacement.length})`;
      }
      if ('flow_rate' in logData && Array.isArray(logData.flow_rate) && logData.flow_rate.length > 20) {
          (logData as any).flow_rate = `Array(${logData.flow_rate.length})`;
      }
      if ('scg_waveform' in logData && Array.isArray(logData.scg_waveform) && logData.scg_waveform.length > 20) {
          (logData as any).scg_waveform = `Array(${logData.scg_waveform.length})`;
      }
      // console.log(`[IPC] ${data.type}:`, logData);

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
        case 'fps_stats':
          handlers.onFPS?.(data);
          break;
        case 'realtime_analysis':
          handlers.onRealtimeAnalysis?.(data);
          break;
      }
    });
  } else {
    console.warn('Electron IPC not available');
  }
};
