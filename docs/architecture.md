# 🏗️ Architecture du projet

## Schéma global

┌─────────────────┐     photos + état      ┌─────────────────┐
│  Raspberry Pi   │ ─────────────────────► │    Firebase     │
│  + caméra       │                        │  (Firestore +   │
│  (Python)       │ ◄───────────────────── │   Storage)      │
└─────────────────┘   notification push    └────────┬────────┘
│
┌─────────────────┘
▼
┌─────────────────┐
│  App mobile     │
│  React Native   │
│  (Expo)         │
└─────────────────┘

## Flux détaillé (toutes les 60 secondes)

1. **Photo** : le Pi capture une image de la gamelle (1280x720)
2. **Détection** : OpenCV calcule un "score de remplissage" sur la zone de la gamelle
   - Score élevé = croquettes visibles = gamelle pleine
   - Score faible = fond lisse = gamelle vide
3. **Upload** : la photo est envoyée sur Firebase Storage
4. **Événement** : un document est écrit dans Firestore (`events`) avec l'état + le score + le chemin de la photo
5. **Notification** : si gamelle vide → push sur le téléphone (max 1 toutes les 30 min)

## Côté app mobile

- **HomeScreen** : écoute Firestore en temps réel → affiche "🚨 VIDE" ou "✅ pleine" + historique
- **GalleryScreen** : affiche les photos depuis Firebase Storage en grille 2 colonnes