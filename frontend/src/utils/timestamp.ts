// 格式化时间戳
export const convertTimestampToTimeHM = (timestamp: number): string => {
  const date = new Date(timestamp * 1000)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
}

export const convertTimestampToDate = (timestamp: number): string => {
  const date = new Date(timestamp * 1000)
  return `${date.getHours()}:${date.getMinutes()}:${date.getSeconds()}`
}

export const convertTimestampToTimeHMS = (timestamp: number): string => {
  const date = new Date(timestamp * 1000)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
}

// 将秒级时间戳格式化为本地时区 YYYY-MM-DD HH:mm:ss
export const formatTimestampToLocalDateTime = (timestampSeconds: number): string => {
  const date = new Date(timestampSeconds * 1000)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}
