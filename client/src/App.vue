<!-- Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 2016-present Scille SAS -->

<template>
  <ion-app>
    <ion-router-outlet />
  </ion-app>
</template>

<script setup lang="ts">
import { IonApp, IonRouterOutlet } from '@ionic/vue';
import { inject } from 'vue';
import { SplashScreen } from '@capacitor/splash-screen';
import { onMounted } from '@vue/runtime-core';
import { toggleDarkMode } from '@/states/darkMode';
import { StorageManagerKey } from '@/common/injectionKeys';
import { StorageManager } from '@/services/storageManager';

// eslint-disable-next-line @typescript-eslint/no-non-null-assertion
const storageManager: StorageManager = inject(StorageManagerKey)!;

onMounted(async (): Promise<void> => {
  SplashScreen.hide();

  const config = await storageManager.retrieveConfig();
  toggleDarkMode(config.theme);
});
</script>
