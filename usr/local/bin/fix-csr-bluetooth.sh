#!/bin/bash
# Fix counterfeit CSR 0a12:0001 Bluetooth adapter (Barrot 8041a02)
# Forces compatible BR/EDR + standard SSP (P-192) settings
# Run: at boot via systemd, or on hotplug via udev rule

# Prevent concurrent runs from udev + systemd
exec 200>/tmp/csr_bluetooth_fix.lock
flock -n 200 || exit 0

sleep 2

# Force standard SSP / BR-EDR register states on hci0
btmgmt --index 0 le off 2>/dev/null
btmgmt --index 0 sc off 2>/dev/null
btmgmt --index 0 ssp on 2>/dev/null
btmgmt --index 0 linksec on 2>/dev/null
btmgmt --index 0 fast-conn on 2>/dev/null
btmgmt --index 0 connectable on 2>/dev/null
btmgmt --index 0 bondable on 2>/dev/null
btmgmt --index 0 pairable on 2>/dev/null

# Power cycle to latch registers
btmgmt --index 0 power off 2>/dev/null
sleep 1
btmgmt --index 0 power on 2>/dev/null

# Ensure Pairable property on D-Bus
busctl --system set-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 Pairable b true 2>/dev/null
busctl --system set-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 PairableTimeout u 0 2>/dev/null
