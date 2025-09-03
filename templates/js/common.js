// API 工具类
class ApiResponse {
  static handle(response, onSuccess, onError) {
    if (response && response.code === 0) {
      if (onSuccess) onSuccess(response.data || {});
    } else {
      const msg = (response && response.message) || 'Unknown error';
      if (onError) {
        onError(msg);
      } else {
        alert(msg);
      }
    }
  }
  
  static isSuccess(r) { 
    return r && r.code === 0; 
  }
  
  static getData(r) { 
    return (r && r.code === 0) ? r.data : null; 
  }
  
  static getErrorMessage(r) {
    return (r && r.code !== 0) ? r.message : null;
  }
}

class ApiClient {
  static async get(url, options = {}) {
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {})
        },
        ...options
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('API请求失败:', error);
      return { code: -1, message: error.message, data: null };
    }
  }

  static async post(url, data = null, options = {}) {
    try {
      const isFormData = data instanceof FormData;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
          ...(options.headers || {})
        },
        body: isFormData ? data : JSON.stringify(data),
        ...options
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('API请求失败:', error);
      return { code: -1, message: error.message, data: null };
    }
  }

  static async delete(url, options = {}) {
    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {})
        },
        ...options
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('API请求失败:', error);
      return { code: -1, message: error.message, data: null };
    }
  }
}

// API 接口
const api = {
  async status() { return ApiClient.get('/system/status'); },
  async subs() { return ApiClient.get('/subscriptions/'); },
  async createSubscription(params) { return ApiClient.post('/subscriptions/', params); },
  async removeSub(id) { return ApiClient.delete(`/subscriptions/${id}`); },
  async retrySub(id) { return ApiClient.post(`/subscriptions/${id}/retry`); },
  async clearAll() { return ApiClient.delete('/subscriptions/'); },
  async listConfigs() { return ApiClient.get('/configs/'); },
  async upsertConfig(payload) { return ApiClient.post('/configs/', payload); },
  async deleteConfig(key) { return ApiClient.delete(`/configs/${key}`); },
  async listAccounts() { return ApiClient.get('/accounts/'); },
  async upsertAccount(payload) { return ApiClient.post('/accounts/', payload); },
  async deleteAccount(alias) { return ApiClient.delete(`/accounts/${alias}`); },
};

// 通知系统
class NotificationSystem {
  constructor() {
    this.notifications = [];
  }

  showNotification(message, type = 'info', duration = 4000) {
    const id = Date.now() + Math.random();
    const notification = { id, message, type };
    this.notifications.push(notification);
    
    if (duration > 0) {
      setTimeout(() => {
        this.removeNotification(id);
      }, duration);
    }
  }

  removeNotification(id) {
    const index = this.notifications.findIndex(n => n.id === id);
    if (index > -1) {
      this.notifications.splice(index, 1);
    }
  }

  showSuccess(message) { this.showNotification(message, 'success'); }
  showError(message) { this.showNotification(message, 'error'); }
  showWarning(message) { this.showNotification(message, 'warning'); }
  showInfo(message) { this.showNotification(message, 'info'); }
}

// 全局通知实例
window.notificationSystem = new NotificationSystem();
