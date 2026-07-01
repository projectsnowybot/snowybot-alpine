#!/bin/bash

# Exit immediately if any command fails
set -e

CONTAINER_NAME="my_alpine1"
HOST_SCRIPT="/home/snowy/catbot.py"
RUNY_SCRIPT="/home/snowy/runbot.sh"
CONTAINER_SCRIPT="/home/snowy/catbot.py"
RUN_SCRIPT="/home/snowy/runbot.sh"

# -----------------------------------------------------------------------
# HOST-LEVEL NO-DNS RESOLUTION (Bypasses network DNS inside sandbox)
# -----------------------------------------------------------------------
echo "🌐 Resolving whitelist domains to static IPs on the host..."

# Resolve target IPs securely on the host before sandbox confinement
JUST_DICE_IP=$(dig +short just-dice.com | tail -n1)
CF_INSIGHTS_IP=$(dig +short cloudflareinsights.com | tail -n1)
DOCKER_GW_IP=$(docker network inspect bridge -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}')

# Robust fallbacks if host DNS queries return blank
[ -z "$JUST_DICE_IP" ] && JUST_DICE_IP="104.26.11.102"
[ -z "$CF_INSIGHTS_IP" ] && CF_INSIGHTS_IP="104.16.25.34"
[ -z "$DOCKER_GW_IP" ] && DOCKER_GW_IP="172.17.0.1"

echo "🎯 Target IP for Just-Dice: $JUST_DICE_IP"
echo "🎯 Target IP for CloudFlare Insights: $CF_INSIGHTS_IP"
echo "🎯 Target IP for Docker Gateway: $DOCKER_GW_IP"

# 1. Grant container access to the local X11 display server natively as user snowy
echo "🖥️ Granting local display access..."
xhost +local:docker >/dev/null 2>&1 || true

# 2. RUN YOUR SEPARATE KILL SCRIPT
echo "🪓 Running your kill_all_docker.sh script..."
chmod +x ./kill_all_docker.sh
./kill_all_docker.sh


# 3. Launch Alpine container with Network Administration and precise Display Mapping
# Dynamically fetch the current active user's DISPLAY if it's blank under sudo
REAL_DISPLAY=$DISPLAY
[ -z "$REAL_DISPLAY" ] && REAL_DISPLAY=$(w -h $(whoami) | awk '{print $3}' | grep ":" | head -n1)
[ -z "$REAL_DISPLAY" ] && REAL_DISPLAY=":0.0"

echo "📦 Spinning up clean Alpine Linux sandbox container on Display: $REAL_DISPLAY..."

docker run -d -it \
  --name $CONTAINER_NAME \
  --cap-add=NET_ADMIN \
  -e DISPLAY="$REAL_DISPLAY" \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v /var/run/docker.sock:/var/run/docker.sock \
  alpine sh

# 4. [RUNNING AS ROOT INSIDE CONTAINER] Inject static host mapping to bypass DNS completely
echo "🔒 Injecting static IP mappings into /etc/hosts..."
docker exec -u root $CONTAINER_NAME sh -c "
    echo '$JUST_DICE_IP just-dice.com' >> /etc/hosts
    echo '$CF_INSIGHTS_IP cloudflareinsights.com' >> /etc/hosts
"

# 5. [RUNNING AS ROOT INSIDE CONTAINER] Create the 'snowy' user and assign to docker group
echo "👤 Provisioning passwordless 'snowy' user account synchronized with host IDs..."
docker exec -u root $CONTAINER_NAME sh -c "
    addgroup -g 1000 snowy && \
    adduser -D -u 1000 -G snowy -h /home/snowy snowy && \
    addgroup -g $(stat -c '%g' /var/run/docker.sock) host_docker 2>/dev/null || addgroup host_docker && \
    addgroup snowy host_docker
"

# 6. [RUNNING AS ROOT INSIDE CONTAINER] Install packages, Geckodriver, and dependencies
echo "📥 Installing system packages, web dependencies, Geckodriver, and nftables..."
docker exec -u root $CONTAINER_NAME apk update
docker exec -u root $CONTAINER_NAME apk add sudo bind-tools docker-cli nftables bash

# 7. [RUNNING AS ROOT INSIDE CONTAINER] Hardening SSH configuration
echo "🔒 Injecting security parameters into sshd_config..."
docker exec -u root $CONTAINER_NAME sh -c '
    mkdir -p /etc/ssh
    touch /etc/ssh/sshd_config
    sed -i "/PermitEmptyPasswords/d" /etc/ssh/sshd_config
    echo "PermitEmptyPasswords no" >> /etc/ssh/sshd_config
    echo "PasswordAuthentication no" >> /etc/ssh/sshd_config
    echo "PermitRootLogin no" >> /etc/ssh/sshd_config
'

# 9. Push your custom automation script into the container layer
echo "📂 Copying your '$HOST_SCRIPT' over the sandbox boundary..."
docker cp $HOST_SCRIPT ${CONTAINER_NAME}:${CONTAINER_SCRIPT}
docker cp $RUNY_SCRIPT ${CONTAINER_NAME}:${RUN_SCRIPT}

# 10. [RUNNING AS ROOT INSIDE CONTAINER] Correct user directory ownership permissions
echo "🔒 Aligning file permissions for the snowy user profile..."
docker exec -u root $CONTAINER_NAME chown -R snowy:snowy /home/snowy/
# Ensure the copied launcher script inside the container is executable
docker exec -u root $CONTAINER_NAME chmod +x $RUN_SCRIPT

# 12. [RUNNING AS ROOT INSIDE CONTAINER] LOCK DOWN THE NETWORK LAYER WITH NFTABLES
echo "🚧 Activating modular outbound IP Whitelist rules via nftables..."
docker exec -u root $CONTAINER_NAME sh -c "
    nft flush ruleset
    nft add table inet filter
    
    # Block input, forward, and output chains by default
    nft add chain inet filter input '{ type filter hook input priority 0 ; policy drop ; }'
    nft add chain inet filter forward '{ type filter hook forward priority 0 ; policy drop ; }'
    nft add chain inet filter output '{ type filter hook output priority 0 ; policy drop ; }'
    
    # INPUT rules: Allow local interface, local subnets, and established connections
    nft add rule inet filter input oifname \"lo\" accept
    nft add rule inet filter input ip saddr 127.0.0.1 ip daddr 127.0.0.1 accept
    nft add rule inet filter input ct state established,related accept
    
    # OUTPUT rules: Allow local loopback tracking
    nft add rule inet filter output oifname \"lo\" accept
    nft add rule inet filter output ip saddr 127.0.0.1 ip daddr 127.0.0.1 accept
    nft add rule inet filter output ct state established,related accept
    
    # 🟢 NEW: Explicitly allow outbound DNS queries (UDP port 53)
    nft add rule inet filter output udp dport 53 accept
    
    # Dynamic set supporting subnets/intervals matching the target IP allocations
    nft add set inet filter allowed_ips '{ type ipv4_addr ; flags interval ; }'
    nft add rule inet filter output ip daddr @allowed_ips accept
    
    # Whitelist the entire Cloudflare 104.16.0.0/12 block and the Docker Gateway interface
    nft add element inet filter allowed_ips '{ 104.16.0.0/12, $DOCKER_GW_IP }'
"

echo "✅ Network layer locked down tightly using native nftables ruleset."

# 13. 🔒 PRIVILEGE ISOLATION HARDENING (Only user snowy gets passwordless sudo)
echo "🔒 Stripping generic group privileges and locking sudo rules exclusively to 'snowy'..."
docker exec -u root $CONTAINER_NAME sh -c "
    touch /etc/sudoers && \
    sed -i '/%wheel/d' /etc/sudoers && \
    sed -i '/%sudo/d' /etc/sudoers
"

docker exec -u root $CONTAINER_NAME sh -c "
    mkdir -p /etc/sudoers.d && \
    echo 'snowy ALL=(ALL) NOPASSWD: /usr/sbin/nft, /sbin/nft, /bin/sh' > /etc/sudoers.d/snowy && \
    chmod 0440 /etc/sudoers.d/snowy
"

docker exec -u root $CONTAINER_NAME chmod -R 1777 /home/snowy/

echo "✅ Deployment Successful! Passing control down to your script console..."
echo "-----------------------------------------------------------------------"


# 14. [RUNNING AS SNOWY INSIDE CONTAINER] Execute your RUN_SCRIPT inside their home folder
docker exec -it -u snowy -w /home/snowy $CONTAINER_NAME /bin/sh $RUN_SCRIPT