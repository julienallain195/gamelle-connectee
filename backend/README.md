# ☁️ Backend Firebase

## Services utilisés
- **Firestore** : collection `events` (état gamelle) + `devices` (tokens push)
- **Storage** : photos uploadées par le Raspberry
- **FCM** : notifications push via l'API Expo

## Déployer les règles
```bash
npm install -g firebase-tools
firebase login
firebase deploy --only firestore:rules,storage:rules

---

### Fichiers dans `docs/` :

**`docs/materiel.md`** :
```markdown
# 🛠️ Matériel nécessaire

| Composant | Recommandation | Prix ~ |
|---|---|---|
| Raspberry Pi | Pi 5 (4 Go) ou Pi 4 | 60-80€ |
| Caméra | Caméra officielle Pi v3 | 35€ |
| Carte microSD | 32 Go minimum | 10€ |
| Alimentation | alim officielle USB-C | 10€ |
| Boîtier | avec support caméra | 10€ |

## Montage
Caméra fixée au-dessus de la gamelle (~30-50 cm), Pi à côté.