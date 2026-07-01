#!/bin/bash

# Exit immediately if any command fails
set -e

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ This script requires root privileges. Please run with sudo."
  exit 1
fi

echo "⚙️ Configuring strict, port-locked nftables rules..."

# 1. Flush any existing nftables rules to start fresh
nft flush ruleset

# 2. Create a standard inet table
nft add table inet filter


# =====================================================================
# 3. INPUT CHAIN (Strictly locked to specific ports)
# =====================================================================
nft add chain inet filter input { type filter hook input priority 0 \; policy drop \; }

# Allow all loopback traffic
nft add rule inet filter input iif lo accept

# DHCP Allow (Input)
nft add rule inet filter input iifname { "eth0", "eth1" } udp sport 67 udp dport 68 accept

# Locked Input Tracking: ONLY accept return traffic for Web (TCP) and DNS (UDP)
nft add rule inet filter input iifname { "eth0", "eth1" } tcp sport { 80, 443 } ct state { established, related } accept
nft add rule inet filter input iifname { "eth0", "eth1" } udp sport { 53, 123 } ct state { established, related } accept
nft add rule inet filter input iifname "docker0" oifname { "eth0", "eth1" } ct state { established, related } accept


# =====================================================================
# 4. FORWARD CHAIN (Docker Routing)
# =====================================================================
nft add chain inet filter forward { type filter hook forward priority 0 \; policy drop \; }

# Allow packets that belong to existing forwarded connections (Docker replies)
nft add rule inet filter forward ct state { established, related } accept


# =====================================================================
# 5. OUTPUT CHAIN (Outbound Bot Traffic)
# =====================================================================
nft add chain inet filter output { type filter hook output priority 0 \; policy drop \; }

# Allow all loopback outgoing traffic
nft add rule inet filter output oif lo accept

# DHCP Allow (Output)
nft add rule inet filter output oifname { "eth0", "eth1" } udp sport 68 udp dport 67 accept

# Your Bot Rules: Outbound Web/DNS traffic
nft add rule inet filter output oifname { "eth0", "eth1", "docker0" } tcp dport { 80, 443 } ct state { new, established } accept
nft add rule inet filter output oifname { "eth0", "eth1", "docker0" } udp dport { 53, 123 } ct state { new, established } accept


# =====================================================================
# 6. SAVE & PERSIST
# =====================================================================
nft list ruleset > /etc/nftables.conf

echo "💾 Rules saved securely to /etc/nftables.conf"
echo "✅ Firewall successfully updated with symmetrical port tracking!"