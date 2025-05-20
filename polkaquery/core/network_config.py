# Polkaquery
# Copyright (C) 2025 Ray

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Network configurations for Polkaquery.
"""

SUPPORTED_NETWORKS = {
    "polkadot": {"base_url": "https://polkadot.api.subscan.io", "decimals": 10, "symbol": "DOT"},
    # "kusama": {"base_url": "https://kusama.api.subscan.io", "decimals": 12, "symbol": "KSM"},
    # "westend": {"base_url": "https://westend.api.subscan.io", "decimals": 12, "symbol": "WND"},
    # "statemint": {"base_url": "https://statemint.api.subscan.io", "decimals": 10, "symbol": "DOT"}, # AssetHub Polkadot
    # "statemine": {"base_url": "https://statemine.api.subscan.io", "decimals": 12, "symbol": "KSM"}, # AssetHub Kusama
    # Add more networks as needed
}
DEFAULT_NETWORK = "polkadot"
