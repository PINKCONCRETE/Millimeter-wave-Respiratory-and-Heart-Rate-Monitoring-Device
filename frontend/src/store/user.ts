import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: '',
    name: '',
    avatar: '',
    roles: [] as string[]
  }),
  
  getters: {
  },
  
  actions: {
    // 设置token
    setToken(token: string) {
      this.token = token
    },
    
    // 重置Token
    resetToken() {
      return new Promise<void>((resolve) => {
        this.token = ''
        this.roles = []
        resolve()
      })
    }
  }
})