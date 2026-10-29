import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Switch, StyleSheet, TouchableOpacity, Alert, ActivityIndicator, ScrollView, RefreshControl } from 'react-native';
import * as Notifications from 'expo-notifications';
import { doc, onSnapshot, setDoc, serverTimestamp } from 'firebase/firestore';
import { db } from '../services/firebase';

const DEVICE_ID = 'raspberry-pi-1';

const DEFAULT_SETTINGS = {
  emptyThreshold: 35,
  checkIntervalSeconds: 60,
  alertCooldownMinutes: 30,
  quietStartHour: 23,
  quietEndHour: 7,
  videoOnCat: true,
};

// Un champ numérique éditable persisté dans settings/gamelle (lu par le Pi)
function NumberField({ label, suffix, value, onChange }) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.fieldInput}>
        <TextInput
          style={styles.textInput}
          value={String(value)}
          keyboardType="numeric"
          onChangeText={text => onChange(parseInt(text, 10) || 0)}
        />
        {suffix && <Text style={styles.suffix}>{suffix}</Text>}
      </View>
    </View>
  );
}

export default function SettingsScreen() {
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [piStatus, setPiStatus] = useState(null);
  const [testLoading, setTestLoading] = useState(false);

  useEffect(() => {
    // Réglages partagés avec le Raspberry (temps réel)
    const unsub = onSnapshot(doc(db, 'settings', 'gamelle'), (snap) => {
      setSettings({ ...DEFAULT_SETTINGS, ...snap.data() });
    }, err => {
      console.warn('Lecture réglages:', err.message);
      setSettings(DEFAULT_SETTINGS);
    });
    // État du Raspberry publié par main.py
    const unsubStatus = onSnapshot(doc(db, 'status', DEVICE_ID), (snap) => {
      setPiStatus(snap.data() || null);
    }, () => {});
    return () => { unsub(); unsubStatus(); };
  }, []);

  async function saveSettings() {
    if (!settings) return;
    setSaving(true);
    try {
      await setDoc(doc(db, 'settings', 'gamelle'), {
        ...settings,
        updatedAt: serverTimestamp(),
        updatedBy: 'mobile-app',
      }, { merge: true });
      Alert.alert('Enregistré', 'Le Raspberry appliquera les réglages sous peu.');
    } catch (err) {
      Alert.alert('Erreur', 'Impossible d\'enregistrer : ' + err.message);
    } finally {
      setSaving(false);
    }
  }

  async function testNotification() {
    setTestLoading(true);
    try {
      await Notifications.scheduleNotificationAsync({
        content: {
          title: '🚨 Gamelle vide !',
          body: 'Ton chat n\'a plus de croquettes 🐱 (notification de test)',
          sound: 'default',
        },
        trigger: null,
      });
    } catch (err) {
      Alert.alert('Notification impossible', err.message);
    } finally {
      setTestLoading(false);
    }
  }

  const piTemp = piStatus?.cpuTemp ? `${piStatus.cpuTemp.toFixed(1)} °C` : '—';
  const piUptime = piStatus?.uptimeSeconds
    ? `${Math.floor(piStatus.uptimeSeconds / 3600)} h ${Math.floor((piStatus.uptimeSeconds % 3600) / 60)} min`
    : '—';
  const piLastSeen = piStatus?.lastSeen
    ? piStatus.lastSeen.toDate().toLocaleString('fr-FR')
    : '—';

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl
          refreshing={false}
          onRefresh={() => setSettings(s => ({ ...s }))}
          tintColor="#e67e22"
        />
      }
    >
      <Text style={styles.sectionTitle}>Appareil</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.label}>Raspberry</Text>
          <Text style={styles.value}>{DEVICE_ID}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>Dernier contact</Text>
          <Text style={styles.value}>{piLastSeen}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>Température CPU</Text>
          <Text style={styles.value}>{piTemp}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>Uptime</Text>
          <Text style={styles.value}>{piUptime}</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Réglages de surveillance</Text>
      <View style={styles.card}>
        {!settings ? (
          <ActivityIndicator color="#e67e22" style={{ marginVertical: 12 }} />
        ) : (
          <>
            <NumberField
              label="Seuil « gamelle vide » (score)"
              value={settings.emptyThreshold}
              onChange={v => setSettings({ ...settings, emptyThreshold: v })}
            />
            <NumberField
              label="Intervalle de vérification"
              suffix="s"
              value={settings.checkIntervalSeconds}
              onChange={v => setSettings({ ...settings, checkIntervalSeconds: Math.max(10, v) })}
            />
            <NumberField
              label="Anti-spam notification"
              suffix="min"
              value={settings.alertCooldownMinutes}
              onChange={v => setSettings({ ...settings, alertCooldownMinutes: v })}
            />
            <NumberField
              label="Début heures silencieuses"
              suffix="h"
              value={settings.quietStartHour}
              onChange={v => setSettings({ ...settings, quietStartHour: Math.min(23, Math.max(0, v)) })}
            />
            <NumberField
              label="Fin heures silencieuses"
              suffix="h"
              value={settings.quietEndHour}
              onChange={v => setSettings({ ...settings, quietEndHour: Math.min(23, Math.max(0, v)) })}
            />
            <View style={styles.row}>
              <Text style={styles.label}>Vidéo quand le chat est détecté</Text>
              <Switch
                value={settings.videoOnCat}
                onValueChange={v => setSettings({ ...settings, videoOnCat: v })}
                trackColor={{ true: '#e67e22' }}
              />
            </View>
            <TouchableOpacity style={styles.saveButton} onPress={saveSettings} disabled={saving}>
              {saving
                ? <ActivityIndicator color="#fff" size="small" />
                : <Text style={styles.saveButtonText}>Enregistrer</Text>}
            </TouchableOpacity>
            <Text style={styles.hint}>
              Pendant les heures silencieuses, le Raspberry ne prend ni photo ni vidéo.
            </Text>
          </>
        )}
      </View>

      <Text style={styles.sectionTitle}>Notifications</Text>
      <View style={styles.card}>
        <Text style={styles.note}>
          Les push distants ne fonctionnent pas dans Expo Go (limite Expo depuis le SDK 53) ;
          ils seront actifs dans la version finale. Test local :
        </Text>
        <TouchableOpacity style={styles.button} onPress={testNotification} disabled={testLoading}>
          {testLoading
            ? <ActivityIndicator color="#fff" size="small" />
            : <Text style={styles.buttonText}>Tester la notification « gamelle vide »</Text>}
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f5f5f5' },
  sectionTitle: { fontSize: 13, color: '#888', textTransform: 'uppercase', marginTop: 16, marginBottom: 6 },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 16 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 7 },
  label: { color: '#555', flex: 1 },
  value: { fontWeight: '600' },
  field: { paddingVertical: 7 },
  fieldLabel: { color: '#555', marginBottom: 4 },
  fieldInput: { flexDirection: 'row', alignItems: 'center' },
  textInput: {
    borderWidth: 1, borderColor: '#ddd', borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 6, minWidth: 90, fontSize: 15,
  },
  suffix: { marginLeft: 8, color: '#888' },
  saveButton: {
    backgroundColor: '#e67e22', borderRadius: 10, padding: 13,
    alignItems: 'center', marginTop: 14,
  },
  saveButtonText: { color: '#fff', fontWeight: 'bold' },
  hint: { fontSize: 11, color: '#aaa', marginTop: 10 },
  note: { color: '#666', fontSize: 13, marginBottom: 12 },
  button: { backgroundColor: '#e67e22', borderRadius: 10, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: 'bold' },
});
