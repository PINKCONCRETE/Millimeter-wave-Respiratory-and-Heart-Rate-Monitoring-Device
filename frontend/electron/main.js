const { app, BrowserWindow } = require('electron')
const path = require('path')
const net = require('net')

// IPC Pipe Name for Windows
const PIPE_NAME = '\\\\.\\pipe\\mmw_monitor_pipe'

let mainWindow
let server

function createWindow () {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false, // For MVP simplicity
      preload: path.join(__dirname, 'preload.js')
    }
  })

  // In development, load from Vite dev server
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadURL('http://localhost:5173')
  }

  // Create Named Pipe Server
  server = net.createServer((stream) => {
    console.log('Python Client connected')
    
    let buffer = ''
    
    stream.on('data', (chunk) => {
      buffer += chunk.toString()
      
      let lineEndIndex
      while ((lineEndIndex = buffer.indexOf('\n')) !== -1) {
        const line = buffer.substring(0, lineEndIndex)
        buffer = buffer.substring(lineEndIndex + 1)
        
        if (line.trim()) {
          try {
            const data = JSON.parse(line)
            if (mainWindow && !mainWindow.isDestroyed()) {
              mainWindow.webContents.send('ipc-data', data)
            }
          } catch (e) {
            console.error('Parse error:', e) 
          }
        }
      }
    })

    stream.on('end', () => {
      console.log('Python Client disconnected')
    })
    
    stream.on('error', (err) => {
        console.error('Pipe error:', err)
    })
  })

  server.listen(PIPE_NAME, () => {
    console.log(`Named Pipe Server listening on ${PIPE_NAME}`)
  })
}

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (server) server.close()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
