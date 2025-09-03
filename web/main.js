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
      accountForm: { alias: '', api_wallet_address: '', secret_key: '', is_active: true },
      homeForm: { name: '', coin: 'ETH', interval: '1m', account_alias: '' },
    });

    const setRoute = () => { state.route = (location.hash.replace('#/', '') || 'monitor'); };
    window.addEventListener('hashchange', setRoute);

    const refreshMonitor = async () => {
      state.status = await api.status();
      state.subs = await api.subs();
    };

    const refreshConfigs = async () => { state.configs = await api.listConfigs(); };
    const refreshAccounts = async () => { state.accounts = await api.listAccounts(); };

    const createHome = async () => {
      // We map to the candle subscription type used by backend
      const params = { type: 'candle', coin: state.homeForm.coin, interval: state.homeForm.interval };
      const q = {};
      if (state.homeForm.account_alias) q.account_alias = state.homeForm.account_alias;
      // Use templates endpoint to keep consistency
      const templateKey = `candle_${state.homeForm.interval}_${state.homeForm.coin.toLowerCase()}`;
      await api.createFromTemplate(templateKey, q);
      state.homeForm = { name: '', coin: 'ETH', interval: '1m', account_alias: '' };
      await refreshMonitor();
    };
    const clearAll = async () => { await api.clearAll(); await refreshMonitor(); };
    const removeSub = async (id) => { await api.removeSub(id); await refreshMonitor(); };

    const saveConfig = async () => { await api.upsertConfig(state.configForm); state.configForm = { key: '', value: '', description: '', config_type: 'string' }; await refreshConfigs(); };
    const deleteConfig = async (key) => { await api.deleteConfig(key); await refreshConfigs(); };

    const saveAccount = async () => { await api.upsertAccount(state.accountForm); state.accountForm = { alias: '', api_wallet_address: '', secret_key: '', is_active: true }; await refreshAccounts(); };
    const deleteAccount = async (alias) => { await api.deleteAccount(alias); await refreshAccounts(); };

    onMounted(async () => {
      await Promise.all([refreshMonitor(), refreshConfigs(), refreshAccounts()]);
    });

    return { ...Vue.toRefs(state), createHome, clearAll, removeSub, saveConfig, deleteConfig, saveAccount, deleteAccount };
  }
}).mount('#app');


