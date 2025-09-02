"""Simple configuration loader for Hyperliquid Trading System."""

import os

import yaml


class Config:
    """Configuration class with enforced structure."""

    def __init__(self, config_dict):
        self.account_address = config_dict['account_address']
        self.secret_key = config_dict['secret_key']
        self.api_wallet_address = config_dict.get('api_wallet_address')
        self.keystore_path = config_dict.get('keystore_path', '')
        self.base_url = config_dict.get('base_url')

    def __getitem__(self, key):
        """Allow dict-style access for backward compatibility."""
        return getattr(self, key)

    def get(self, key, default=None):
        """Allow dict.get() style access."""
        return getattr(self, key, default)

    def items(self):
        """Allow dict.items() style access."""
        return {
            'account_address': self.account_address,
            'secret_key': self.secret_key,
            'api_wallet_address': self.api_wallet_address,
            'keystore_path': self.keystore_path,
            'base_url': self.base_url
        }.items()


def load_config(environment=None):
    """Load config for the specified environment (or default)."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if environment is None:
        environment = config.get('default_environment', 'testnet')

    return Config(config[environment])


def get_environments():
    """Get available environments."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return [k for k in config.keys() if k != 'default_environment']
