import { io, Socket } from 'socket.io-client'

// 开发时连接 Flask 5000，生产时同域
const URL = import.meta.env.DEV ? 'http://localhost:5000' : '/'

export const socket: Socket = io(URL, {
  autoConnect: true,
  transports: ['websocket', 'polling'],
})
