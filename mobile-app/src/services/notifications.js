import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { doc, setDoc } from 'firebase/firestore';
import { db } from './firebase';

export async function registerPushToken() {
  if (!Device.isDevice) return;
  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== 'granted') return;
  const token = (await Notifications.getExpoPushTokenAsync()).data;
  await setDoc(doc(db, 'devices', 'raspberry-pi-1'), { pushToken: token });
  console.log('Token:', token);
}