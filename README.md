# docker-radarvirtuel v2 — Guide installation beta

## Comment ça fonctionne

```
Votre décodeur (readsb/dump1090/ultrafeeder)
        │ Beast TCP port 30005
        ▼
  [docker-radarvirtuel]
        │ Beast TCP port 30004
        ▼
  radarvirtuel.com
```

Au démarrage, le container :
1. Génère un UID unique pour votre station (sauvegardé automatiquement)
2. Détecte l'aéroport le plus proche de vos coordonnées
3. Enregistre votre station sur radarvirtuel.com
4. Démarre le pipe Beast → radarvirtuel.com:30004

---

## Prérequis

- Docker + Docker Compose installés
- Un décodeur ADS-B actif avec **Beast output sur le port 30005**
  (readsb, dump1090-fa, tar1090, ultrafeeder)
- Accès internet sortant TCP port 30004 et HTTPS 443

---

## Installation

```bash
# 1 — Créer le répertoire
mkdir -p /opt/adsb && cd /opt/adsb

# 2 — Télécharger les fichiers
curl -O https://radarvirtuel.com/dl/docker/docker-compose.yml
curl -O https://radarvirtuel.com/dl/docker/.env.example

# 3 — Créer votre fichier .env
cp .env.example .env
nano .env
# → Renseigner FEEDER_LAT, FEEDER_LONG, SOURCE_HOST

# 4 — Démarrer
docker compose up -d

# 5 — Vérifier les logs
docker logs -f radarvirtuel
```

---

## Configuration SOURCE_HOST

| Situation | Valeur |
|---|---|
| ultrafeeder dans le même stack Docker | `SOURCE_HOST=ultrafeeder:30005` |
| readsb/dump1090 standalone sur la même machine | `SOURCE_HOST=${HOSTNAME}:30005` |
| readsb sur une autre machine du réseau | `SOURCE_HOST=192.168.1.10:30005` |

> ⚠️ Ne jamais utiliser `127.0.0.1` — cela pointe à l'intérieur du container.

---

## Logs attendus au démarrage

```
[RV] ==================================================
[RV] RadarVirtuel Docker Feeder v2.0 — 2026-06-08
[RV] ==================================================
[RV] UID generated: a1b2c3d4e5f6... → saved to /data/station_uid.txt
[RV] Position: lat=48.6076 lon=-1.6956 alt=25m
[RV] Nearest airport: LFRV — Vannes-Meucon (12.3 km)
[RV] Label selected: LFRV1
[RV] Registration: CREATED — station LFRV1 uid=a1b2c3d4e5f6...
[RV] Launching readsb connector:
[RV]   Source : ultrafeeder:30005 (Beast in)
[RV]   Target : radarvirtuel.com:30004 (Beast out)
[RV]   Station: LFRV1 lat=48.6076 lon=-1.6956
```

Au second démarrage :
```
[RV] UID loaded from /data/station_uid.txt: a1b2c3d4e5f6...
[RV] Registration: EXISTING — station LFRV1
```

---

## Récupérer votre UID

```bash
docker exec radarvirtuel cat /data/station_uid.txt
```

---

## Mise à jour

```bash
docker compose pull && docker compose up -d
```

---

## Votre page station

`https://radarvirtuel.com/station/VOTRELABEL`

---

## Problèmes fréquents

**Aucune connexion — logs vides après démarrage**
```bash
# Vérifier que Beast est accessible
nc -zv ${HOSTNAME} 30005
```

**`Registration HTTP 409`**
→ Le label est déjà pris. Définir `RV_STATION_LABEL=ICAO2` dans `.env`

**`Connection refused` sur radarvirtuel.com:30004**
→ Vérifier que le port TCP 30004 sortant est autorisé sur votre pare-feu/box

---

## Contact beta test

Retours et problèmes : **support@adsbnetwork.com**
Objet : `[Docker v2 beta]`
