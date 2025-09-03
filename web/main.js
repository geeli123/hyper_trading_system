const api = {
  async status() { return fetch('/system/status').then(r => r.json()); },
  async subs() { return fetch('/subscriptions').then(r => r.json()); },
  async templates() { return fetch('/subscriptions/templates').then(r => r.json()); },
  async createFromTemplate(name, q) { const qs = q ? ('?' + new URLSearchParams(q)) : ''; return fetch(`/subscriptions/templates/${name}${qs}`, { method: 'POST' }).then(r => r.json()); },
  async removeSub(id) { return fetch(`/subscriptions/${id}`, { method: 'DELETE' }).then(r => r.json()); },
  async clearAll() { return fetch('/subscriptions', { method: 'DELETE' }).then(r => r.json()); },
  async listConfigs() { return fetch('/configs').then(r => r.json()); },
  async upsertConfig(payload) { return fetch('/configs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }).then(r => r.json()); },
  async deleteConfig(key) { return fetch(`/configs/${key}`, { method: 'DELETE' }).then(r => r.json()); },
  async listAccounts() { return fetch('/accounts').then(r => r.json()); },
  async upsertAccount(payload) { return fetch('/accounts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }).then(r => r.json()); },
  async deleteAccount(alias) { return fetch(`/accounts/${alias}`, { method: 'DELETE' }).then(r => r.json()); },
};

const { createApp, reactive, onMounted } = Vue;

createApp({
  setup() {
    const state = reactive({
      route: (location.hash.replace('#/', '') || 'monitor'),
      status: { ws_ready: false, active_subscriptions: 0, subscription_stats: { total: 0 } },
      subs: [],
      configs: [],
      accounts: [],
      configForm: { key: '', value: '', description: '', config_type: 'string' },
      accountForm: { alias: '', account_address: '', api_wallet_address: '', secret_key: '', is_active: true },
    });

    const setRoute = () => { state.route = (location.hash.replace('#/', '') || 'monitor'); };
    window.addEventListener('hashchange', setRoute);

    const refreshMonitor = async () => {
      state.status = await api.status();
      state.subs = await api.subs();
    };

    const refreshConfigs = async () => { state.configs = await api.listConfigs(); };
    const refreshAccounts = async () => { state.accounts = await api.listAccounts(); };

    const createFromFirstTemplate = async () => {
      const tpls = await api.templates();
      const first = Object.keys(tpls)[0];
      if (first) {
        const alias = prompt('可选：输入account_alias用于该订阅（留空则默认）');
        const addr = !alias ? prompt('可选：直接输入account_address（留空则默认）') : '';
        await api.createFromTemplate(first, { account_alias: alias || undefined, account_address: addr || undefined });
        await refreshMonitor();
      }
    };
    const clearAll = async () => { await api.clearAll(); await refreshMonitor(); };
    const removeSub = async (id) => { await api.removeSub(id); await refreshMonitor(); };

    const saveConfig = async () => { await api.upsertConfig(state.configForm); state.configForm = { key: '', value: '', description: '', config_type: 'string' }; await refreshConfigs(); };
    const deleteConfig = async (key) => { await api.deleteConfig(key); await refreshConfigs(); };

    const saveAccount = async () => { await api.upsertAccount(state.accountForm); state.accountForm = { alias: '', account_address: '', api_wallet_address: '', secret_key: '', is_active: true }; await refreshAccounts(); };
    const deleteAccount = async (alias) => { await api.deleteAccount(alias); await refreshAccounts(); };

    onMounted(async () => {
      await Promise.all([refreshMonitor(), refreshConfigs(), refreshAccounts()]);
    });

    return { ...Vue.toRefs(state), createFromFirstTemplate, clearAll, removeSub, saveConfig, deleteConfig, saveAccount, deleteAccount };
  }
}).mount('#app');


