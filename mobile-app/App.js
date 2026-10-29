import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import * as Notifications from 'expo-notifications';
import HomeScreen from './src/screens/HomeScreen';
import GalleryScreen from './src/screens/GalleryScreen';
import { registerPushToken } from './src/services/notifications';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
  }),
});

const Stack = createNativeStackNavigator();

export default function App() {
  useEffect(() => {
    registerPushToken();
  }, []);

  return (
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="Home" component={HomeScreen} options={{ title: '🐱 Gamelle' }} />
        <Stack.Screen name="Gallery" component={GalleryScreen} options={{ title: '📸 Photos' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}