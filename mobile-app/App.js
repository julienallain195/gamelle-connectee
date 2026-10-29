import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import * as Notifications from 'expo-notifications';
import HomeScreen from './src/screens/HomeScreen';
import PhotosScreen from './src/screens/PhotosScreen';
import CatScreen from './src/screens/CatScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import { registerPushToken } from './src/services/notifications';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
  }),
});

const Tab = createBottomTabNavigator();

const TAB_ICONS = {
  Gamelle: { on: 'restaurant', off: 'restaurant-outline' },
  Photos: { on: 'images', off: 'images-outline' },
  Chat: { on: 'paw', off: 'paw-outline' },
  'Paramètres': { on: 'settings', off: 'settings-outline' },
};

export default function App() {
  useEffect(() => {
    registerPushToken();
  }, []);

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          tabBarIcon: ({ focused, color, size }) => (
            <Ionicons
              name={focused ? TAB_ICONS[route.name].on : TAB_ICONS[route.name].off}
              size={size}
              color={color}
            />
          ),
          tabBarActiveTintColor: '#e67e22',
        })}
      >
        <Tab.Screen name="Gamelle" component={HomeScreen} options={{ title: '🐱 Gamelle' }} />
        <Tab.Screen name="Photos" component={PhotosScreen} options={{ title: '📸 Photos' }} />
        <Tab.Screen name="Chat" component={CatScreen} options={{ title: '🐾 Chat' }} />
        <Tab.Screen name="Paramètres" component={SettingsScreen} options={{ title: '⚙️ Paramètres' }} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
