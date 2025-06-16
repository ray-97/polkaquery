# Polkaquery
# Copyright (C) 2025 Ray
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from substrateinterface import SubstrateInterface

class AssetHubRPCClient:
    def __init__(self, network_url: str):
        self.substrate = SubstrateInterface(url=network_url)

    def get_asset_details(self, asset_id: int):
        # Example: Get details for a specific asset
        asset_details = self.substrate.query('Assets', 'Asset', [asset_id])
        return asset_details.value

    def get_account_balance(self, asset_id: int, account_address: str):
        # Example: Get the balance of an asset for an account
        account_info = self.substrate.query('Assets', 'Account', [asset_id, account_address])
        return account_info.value['balance']
