const { createApp } = Vue;

createApp({
    data() {
        return {
            currentPage: 'strategies',
            apiBaseUrl: window.location.origin,  // use current host (protocol + host + optional port)
            appEnv: '',  // 添加环境变量

            // Data storage
            strategyRecords: [],
            accounts: [],
            configs: [],
            logs: {
                items: [],
                pagination: null
            },

            // Loading states
            loading: {
                records: false,
                accounts: false,
                configs: false,
                logs: false,
                createStrategy: false,
                createAccount: false,
                createConfig: false,
                startingStrategy: {}  // Track loading state for each strategy by ID
            },

            // Form data
            newStrategy: {
                name: '',
                coin: '',
                interval: '',
                account_alias: '',
                strategy_params: {
                    trade_size_usd: 12.0,
                    ma_lookback_periods: 20,
                    bb_std_dev: 2.5,
                    stop_loss_multiplier: 0.5,
                    take_profit_multiplier: 0.5,
                    input_candle_periods: 1,
                    input_candle_unit: 'm',
                    target_candle_periods: 1,
                    target_candle_unit: 'h',
                    max_decimals_sz: 4,
                    max_decimals_px: 1
                }
            },
            newAccount: {
                alias: '',
                account_address: '',
                secret_key: ''
            },
            newConfig: {
                key: '',
                value: '',
                description: ''
            },

            // Error messages
            createStrategyError: '',
            createAccountError: '',
            createConfigError: '',

            // Strategy record editing
            editingStrategy: null,

            // Logs related
            currentStrategy: null,
            logFilters: {
                event_type: '',
                level: '',
                account_alias: ''
            },
            editStrategyError: '',

            // Expandable records state
            expandedRecords: {},
            expandedStrategyParams: {},
            
            // Advanced parameters UI state
            showAdvancedParams: false,
            showEditAdvancedParams: false
        };
    },

    async mounted() {
        // Initial data loading
        await this.loadAllData();
    },

    methods: {
        // Page switching
        switchPage(page) {
            // Update navigation state
            document.querySelectorAll('.nav-link').forEach(link => {
                link.classList.remove('active');
            });
            event.target.classList.add('active');

            // Switch page content
            document.querySelectorAll('.page-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(`${page}-page`).classList.add('active');

            this.currentPage = page;

            // Load corresponding data based on page
            if (page === 'strategies') {
                this.loadStrategyRecords();
            } else if (page === 'accounts') {
                this.loadAccounts();
            } else if (page === 'configs') {
                this.loadConfigs();
            }
        },

        // Load all data
        async loadAllData() {
            await Promise.all([
                this.loadStrategyRecords(),
                this.loadAccounts(),
                this.loadConfigs()
            ]);
        },


        // Load strategy records
        async loadStrategyRecords() {
            this.loading.records = true;
            try {
                const response = await ApiClient.get(`${this.apiBaseUrl}/strategy-records/`);
                ApiResponse.handle(response,
                    (data) => {
                        this.strategyRecords = data;
                        // 从响应头中获取环境信息
                        if (response.headers && response.headers['x-app-env']) {
                            this.appEnv = response.headers['x-app-env'];
                        }
                    },
                    (error) => {
                        console.error('Failed to load strategy records:', error);
                        this.showNotification(error, 'danger');
                    }
                );
            } catch (error) {
                console.error('Error loading strategy records:', error);
                this.showNotification('Error loading strategy records', 'danger');
            } finally {
                this.loading.records = false;
            }
        },

        // Load account data
        async loadAccounts() {
            this.loading.accounts = true;
            try {
                const response = await ApiClient.get(`${this.apiBaseUrl}/accounts/`);
                ApiResponse.handle(response,
                    (data) => {
                        this.accounts = data;
                    },
                    (error) => {
                        console.error('Failed to load accounts:', error);
                        this.showNotification(error, 'danger');
                    }
                );
            } catch (error) {
                console.error('Error loading accounts:', error);
                this.showNotification('Error loading accounts', 'danger');
            } finally {
                this.loading.accounts = false;
            }
        },

        // Load configuration data
        async loadConfigs() {
            this.loading.configs = true;
            try {
                const response = await ApiClient.get(`${this.apiBaseUrl}/configs/`);
                ApiResponse.handle(response,
                    (data) => {
                        this.configs = data;
                    },
                    (error) => {
                        console.error('Failed to load configs:', error);
                        this.showNotification(error, 'danger');
                    }
                );
            } catch (error) {
                console.error('Error loading configs:', error);
                this.showNotification('Error loading configs', 'danger');
            } finally {
                this.loading.configs = false;
            }
        },

        // Create strategy (只创建记录，不启动)
        async createStrategy() {
            this.createStrategyError = '';

            if (!this.newStrategy.name || !this.newStrategy.coin ||
                !this.newStrategy.interval || !this.newStrategy.account_alias) {
                this.createStrategyError = 'Please fill in all required fields';
                return;
            }

            this.loading.createStrategy = true;

            try {
                const payload = {
                    name: this.newStrategy.name,
                    coin: this.newStrategy.coin,
                    interval: this.newStrategy.interval,
                    account_alias: this.newStrategy.account_alias,
                    strategy_params: this.newStrategy.strategy_params
                };

                const response = await ApiClient.post(`${this.apiBaseUrl}/strategy-records/`, payload);

                ApiResponse.handle(response,
                    (data) => {
                        // Reset form
                        this.newStrategy = {
                            name: '',
                            coin: '',
                            interval: '',
                            account_alias: '',
                            strategy_params: {
                                trade_size_usd: 12.0,
                                ma_lookback_periods: 20,
                                bb_std_dev: 2.5,
                                stop_loss_multiplier: 0.5,
                                take_profit_multiplier: 0.5,
                                input_candle_periods: 1,
                                input_candle_unit: 'm',
                                target_candle_periods: 1,
                                target_candle_unit: 'h',
                                max_decimals_sz: 4,
                                max_decimals_px: 1
                            }
                        };

                        // Close modal
                        const modal = bootstrap.Modal.getInstance(document.getElementById('createStrategyModal'));
                        modal.hide();

                        // Refresh data
                        this.loadStrategyRecords();

                        this.showNotification('Strategy created successfully', 'success');
                    },
                    (error) => {
                        this.createStrategyError = error;
                    }
                );
            } catch (error) {
                console.error('Error creating strategy:', error);
                this.createStrategyError = 'Error occurred while creating strategy';
            } finally {
                this.loading.createStrategy = false;
            }
        },


        // Create account
        async createAccount() {
            this.createAccountError = '';

            if (!this.newAccount.alias || !this.newAccount.account_address ||
                !this.newAccount.secret_key) {
                this.createAccountError = 'Please fill in all required fields';
                return;
            }

            this.loading.createAccount = true;

            try {
                const response = await ApiClient.post(`${this.apiBaseUrl}/accounts/`, this.newAccount);

                ApiResponse.handle(response,
                    (data) => {
                        // Reset form
                        this.newAccount = {
                            alias: '',
                            account_address: '',
                            secret_key: ''
                        };

                        // Close modal
                        const modal = bootstrap.Modal.getInstance(document.getElementById('createAccountModal'));
                        modal.hide();

                        // Refresh data
                        this.loadAccounts();

                        this.showNotification('Account added successfully', 'success');
                    },
                    (error) => {
                        this.createAccountError = error;
                    }
                );
            } catch (error) {
                console.error('Error creating account:', error);
                this.createAccountError = 'Error occurred while adding account';
            } finally {
                this.loading.createAccount = false;
            }
        },

        // Delete account
        async deleteAccount(alias) {
            if (!confirm(`Are you sure you want to delete account "${alias}"?`)) {
                return;
            }

            try {
                const response = await ApiClient.delete(`${this.apiBaseUrl}/accounts/${alias}`);

                ApiResponse.handle(response,
                    (data) => {
                        this.loadAccounts();
                        this.showNotification('Account deleted successfully', 'success');
                    },
                    (error) => {
                        this.showNotification(error, 'danger');
                    }
                );
            } catch (error) {
                console.error('Error deleting account:', error);
                this.showNotification('Error occurred while deleting', 'danger');
            }
        },

        // Create configuration
        async createConfig() {
            this.createConfigError = '';

            if (!this.newConfig.key || !this.newConfig.value) {
                this.createConfigError = 'Please fill in key and value';
                return;
            }

            this.loading.createConfig = true;

            try {
                const response = await ApiClient.post(`${this.apiBaseUrl}/configs/`, this.newConfig);

                ApiResponse.handle(response,
                    (data) => {
                        // Reset form
                        this.newConfig = {
                            key: '',
                            value: '',
                            description: ''
                        };

                        // Close modal
                        const modal = bootstrap.Modal.getInstance(document.getElementById('createConfigModal'));
                        modal.hide();

                        // Refresh data
                        this.loadConfigs();

                        this.showNotification('Configuration added successfully', 'success');
                    },
                    (error) => {
                        this.createConfigError = error;
                    }
                );
            } catch (error) {
                console.error('Error creating config:', error);
                this.createConfigError = 'Error occurred while adding configuration';
            } finally {
                this.loading.createConfig = false;
            }
        },

        // Delete configuration
        async deleteConfig(key) {
            if (!confirm(`Are you sure you want to delete configuration "${key}"?`)) {
                return;
            }

            try {
                const response = await ApiClient.delete(`${this.apiBaseUrl}/configs/${key}`);

                ApiResponse.handle(response,
                    (data) => {
                        this.loadConfigs();
                        this.showNotification('Configuration deleted successfully', 'success');
                    },
                    (error) => {
                        this.showNotification(error, 'danger');
                    }
                );
            } catch (error) {
                console.error('Error deleting config:', error);
                this.showNotification('Error occurred while deleting', 'danger');
            }
        },

        // Strategy record management
        async startStrategyRecord(strategyId) {
            // Set loading state for this specific strategy
            this.loading.startingStrategy[strategyId] = true;

            try {
                const response = await ApiClient.post(`${this.apiBaseUrl}/strategy-records/${strategyId}/start`);

                ApiResponse.handle(response,
                    (data) => {
                        this.loadStrategyRecords();
                        this.showNotification('Strategy started successfully', 'success');
                    },
                    (error) => {
                        this.showNotification(error, 'danger');
                    }
                );
            } catch (error) {
                console.error('Error starting strategy:', error);
                this.showNotification('Error occurred while starting strategy', 'danger');
            } finally {
                // Clear loading state
                this.loading.startingStrategy[strategyId] = false;
            }
        },

        async stopStrategyRecord(strategyId) {
            if (!confirm('Are you sure you want to stop this strategy?')) {
                return;
            }

            try {
                const response = await ApiClient.post(`${this.apiBaseUrl}/strategy-records/${strategyId}/stop`);

                ApiResponse.handle(response,
                    (data) => {
                        this.loadStrategyRecords();
                        this.showNotification('Strategy stopped successfully', 'success');
                    },
                    (error) => {
                        this.showNotification(error, 'danger');
                    }
                );
            } catch (error) {
                console.error('Error stopping strategy:', error);
                this.showNotification('Error occurred while stopping strategy', 'danger');
            }
        },

        async deleteStrategyRecord(strategyId) {
            if (!confirm('Are you sure you want to delete this strategy record?')) {
                return;
            }

            try {
                const response = await ApiClient.delete(`${this.apiBaseUrl}/strategy-records/${strategyId}`);

                ApiResponse.handle(response,
                    (data) => {
                        this.loadStrategyRecords();
                        this.showNotification('Strategy record deleted successfully', 'success');
                    },
                    (error) => {
                        this.showNotification(error, 'danger');
                    }
                );
            } catch (error) {
                console.error('Error deleting strategy record:', error);
                this.showNotification('Error occurred while deleting strategy record', 'danger');
            }
        },

        // Edit strategy record
        editStrategyRecord(strategy) {
            this.editingStrategy = {
                id: strategy.id,
                name: strategy.name,
                coin: strategy.coin,
                interval: strategy.interval,
                account_alias: strategy.account_alias,
                strategy_params: strategy.strategy_params || {
                    trade_size_usd: 12.0,
                    ma_lookback_periods: 20,
                    bb_std_dev: 2.5,
                    stop_loss_multiplier: 0.5,
                    take_profit_multiplier: 0.5,
                    input_candle_periods: 1,
                    input_candle_unit: 'm',
                    target_candle_periods: 1,
                    target_candle_unit: 'h',
                    max_decimals_sz: 4,
                    max_decimals_px: 1
                }
            };
            this.editStrategyError = '';
        },

        async updateStrategyRecord() {
            this.editStrategyError = '';

            if (!this.editingStrategy.name || !this.editingStrategy.coin ||
                !this.editingStrategy.interval || !this.editingStrategy.account_alias) {
                this.editStrategyError = 'Please fill in all required fields';
                return;
            }

            try {
                const payload = {
                    name: this.editingStrategy.name,
                    coin: this.editingStrategy.coin,
                    interval: this.editingStrategy.interval,
                    account_alias: this.editingStrategy.account_alias,
                    strategy_params: this.editingStrategy.strategy_params
                };

                const response = await ApiClient.put(`${this.apiBaseUrl}/strategy-records/${this.editingStrategy.id}`, payload);

                ApiResponse.handle(response,
                    (data) => {
                        // Close modal
                        const modal = bootstrap.Modal.getInstance(document.getElementById('editStrategyModal'));
                        modal.hide();

                        // Reset editing state
                        this.editingStrategy = null;

                        // Refresh data
                        this.loadStrategyRecords();

                        this.showNotification('Strategy record updated successfully', 'success');
                    },
                    (error) => {
                        this.editStrategyError = error;
                    }
                );
            } catch (error) {
                console.error('Error updating strategy record:', error);
                this.editStrategyError = 'Error occurred while updating strategy record';
            }
        },

        cancelEditStrategy() {
            this.editingStrategy = null;
            this.editStrategyError = '';
        },

        // Toggle expand/collapse for strategy records
        toggleExpand(recordId) {
            this.expandedRecords[recordId] = !this.expandedRecords[recordId];
        },

        // Toggle advanced parameters sections
        toggleAdvancedParams() {
            this.showAdvancedParams = !this.showAdvancedParams;
        },

        toggleEditAdvancedParams() {
            this.showEditAdvancedParams = !this.showEditAdvancedParams;
        },

        // Toggle strategy parameters expansion
        toggleStrategyParams(recordId) {
            if (recordId !== undefined && recordId !== null) {
                // 确保 expandedStrategyParams 对象存在
                if (!this.expandedStrategyParams) {
                    this.expandedStrategyParams = {};
                }
                this.expandedStrategyParams[recordId] = !this.expandedStrategyParams[recordId];
            }
        },

        // Utility methods
        formatParams(params) {
            if (!params) return '';
            if (typeof params === 'string') return params;

            // Filter out sensitive information
            const sensitiveKeys = ['user_secret_key', 'secret_key', 'private_key'];
            const filteredParams = Object.entries(params)
                .filter(([key]) => !sensitiveKeys.includes(key))
                .map(([key, value]) => `${key}: ${value}`)
                .join(', ');

            return filteredParams;
        },

        getStatusClass(status) {
            switch (status?.toLowerCase()) {
                case 'active':
                    return 'bg-success';
                case 'inactive':
                case 'paused':
                    return 'bg-warning';
                case 'error':
                case 'failed':
                    return 'bg-danger';
                default:
                    return 'bg-secondary';
            }
        },

        getEnvBadgeClass(env) {
            switch (env?.toLowerCase()) {
                case 'dev':
                    return 'env-dev';
                case 'prod':
                    return 'env-prod';
                default:
                    return 'env-default';
            }
        },

        // Show notification
        showNotification(message, type = 'info') {
            // Create notification element
            const notification = document.createElement('div');
            notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
            notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
            notification.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;

            document.body.appendChild(notification);

            // Auto remove after 3 seconds
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 3000);
        },

        // Logs related methods
        viewStrategyLogs(strategy) {
            this.currentStrategy = strategy;
            this.logFilters = {
                event_type: '',
                level: '',
                account_alias: ''
            };
            this.loadStrategyLogs(1);
        },

        async loadStrategyLogs(page = 1) {
            if (!this.currentStrategy) return;

            this.loading.logs = true;

            try {
                const params = new URLSearchParams({
                    page: page.toString(),
                    page_size: '10'
                });

                // Add filters if they have values
                if (this.logFilters.event_type) {
                    params.append('event_type', this.logFilters.event_type);
                }
                if (this.logFilters.level) {
                    params.append('level', this.logFilters.level);
                }
                if (this.logFilters.account_alias) {
                    params.append('account_alias', this.logFilters.account_alias);
                }

                const response = await ApiClient.get(`${this.apiBaseUrl}/logs/strategy/${encodeURIComponent(this.currentStrategy.name)}?${params}`);

                ApiResponse.handle(response,
                    (data) => {
                        this.logs = data;
                    },
                    (error) => {
                        console.error('Error loading strategy logs:', error);
                        this.showNotification('Failed to load strategy logs: ' + error, 'danger');
                    }
                );
            } catch (error) {
                console.error('Error loading strategy logs:', error);
                this.showNotification('Error occurred while loading strategy logs', 'danger');
            } finally {
                this.loading.logs = false;
            }
        },

        // Helper methods for logs
        formatDateTime(dateString) {
            if (!dateString) return '-';
            const date = new Date(dateString);
            return date.toLocaleString();
        },

        getLogLevelClass(level) {
            switch (level) {
                case 'ERROR':
                    return 'bg-danger';
                case 'WARNING':
                    return 'bg-warning';
                case 'INFO':
                default:
                    return 'bg-info';
            }
        },

        getPageNumbers(pagination) {
            if (!pagination) return [];
            
            const current = pagination.page;
            const total = pagination.total_pages;
            const pages = [];
            
            // Show max 5 page numbers
            let start = Math.max(1, current - 2);
            let end = Math.min(total, current + 2);
            
            // Adjust if we're near the beginning or end
            if (end - start < 4) {
                if (start === 1) {
                    end = Math.min(total, start + 4);
                } else if (end === total) {
                    start = Math.max(1, end - 4);
                }
            }
            
            for (let i = start; i <= end; i++) {
                pages.push(i);
            }
            
            return pages;
        }
    }
}).mount('#app');
