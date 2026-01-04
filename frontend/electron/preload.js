// preload.js
const { ipcRenderer } = require('electron')

window.electronAPI = {
  onData: (callback) => ipcRenderer.on('ipc-data', (event, value) => callback(value))
}
