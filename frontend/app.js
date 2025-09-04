const { createApp } = Vue;

createApp({
    data() {
        return {
            currentPage: 'strategies',
            apiBaseUrl: 'http://localhost:8000',
            appEnv: '',  // 添加环境变量

            // Data storage
            strategyRecords: [],
            accounts: [],
            configs: [],

            // Loading states
            loading: {
                records: false,
                accounts: false,
                configs: false,
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
                account_alias: ''
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
            editStrategyError: ''
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
                    account_alias: this.newStrategy.account_alias
                };

                const response = await ApiClient.post(`${this.apiBaseUrl}/strategy-records/`, payload);

                ApiResponse.handle(response,
                    (data) => {
                        // Reset form
                        this.newStrategy = {
                            name: '',
                            coin: '',
                            interval: '',
                            account_alias: ''
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
                account_alias: strategy.account_alias
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
                    account_alias: this.editingStrategy.account_alias
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
        }
    }
}).mount('#app');
