# ESP-Hub. Der Hub selbst liegt vorkompiliert in hub_main.mpy (Quelltext:
# Hub/hub_main.py). Quelltext auf dem Board zu kompilieren braucht kurz so
# viel Speicher, dass daneben der WLAN-Treiber keinen Platz mehr hatte
# ("Wifi Out of Memory", Abstuerze). Vorkompiliert entfaellt das.
import hub_main
