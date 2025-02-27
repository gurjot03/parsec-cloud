<!-- Parsec Cloud (https://parsec.cloud) Copyright (c) BUSL-1.1 2016-present Scille SAS -->

<template>
  <ion-page>
    <ion-content :fullscreen="true">
      <!-- contextual menu -->
      <ms-action-bar
        id="revoked-users-ms-action-bar"
      >
        <!-- view common workspace -->
        <div v-if="selectedUsersCount >= 1">
          <ms-action-bar-button
            :icon="eye"
            v-show="selectedUsersCount === 1"
            id="button-common-workspaces"
            :button-label="$t('UsersPage.userContextMenu.actionSeeCommonWorkspaces')"
            @click="viewCommonWorkspace()"
          />
        </div>
        <div class="right-side">
          <ms-grid-list-toggle
            v-model="displayView"
            @update:model-value="resetSelection()"
          />
        </div>
      </ms-action-bar>
      <!-- users -->
      <div class="users-container">
        <div v-if="userList.length === 0">
          {{ $t('UsersPage.revokedEmptyList') }}
        </div>
        <div v-else>
          <div v-if="displayView === DisplayState.List">
            <ion-list>
              <ion-list-header
                class="user-list-header"
                lines="full"
              >
                <ion-label class="user-list-header__label label-selected">
                  <ion-checkbox
                    aria-label=""
                    class="checkbox"
                    @ion-change="selectAllUsers($event.detail.checked)"
                    v-model="allUsersSelected"
                    :indeterminate="indeterminateState"
                  />
                </ion-label>
                <ion-label class="user-list-header__label cell-title label-name">
                  {{ $t('UsersPage.listDisplayTitles.name') }}
                </ion-label>
                <ion-label class="user-list-header__label cell-title label-email">
                  {{ $t('UsersPage.listDisplayTitles.email') }}
                </ion-label>
                <ion-label class="user-list-header__label cell-title label-profile">
                  {{ $t('UsersPage.listDisplayTitles.profile') }}
                </ion-label>
                <ion-label class="user-list-header__label cell-title label-joined-on">
                  {{ $t('UsersPage.listDisplayTitles.joinedOn') }}
                </ion-label>
                <ion-label class="user-list-header__label cell-title label-space" />
              </ion-list-header>
              <user-list-item
                v-for="user in userList"
                :key="user.id"
                :user="user"
                :show-checkbox="selectedUsersCount > 0 || allUsersSelected"
                @menu-click="openUserContextMenu($event, user)"
                @select="onUserSelect"
                ref="userListItemRefs"
              />
            </ion-list>
          </div>
          <div
            v-else
            class="users-container-grid"
          >
            <ion-item
              class="users-grid-item"
              v-for="user in userList"
              :key="user.id"
            >
              <user-card
                ref="userGridItemRefs"
                :user="user"
                :show-checkbox="selectedUsersCount > 0 || allUsersSelected"
                @menu-click="openUserContextMenu($event, user)"
                @select="onUserSelect"
              />
            </ion-item>
          </div>
        </div>
      </div>
      <div class="user-footer">
        <div class="user-footer__container">
          <ion-text
            class="text title-h5"
            v-if="selectedUsersCount === 0"
          >
            {{ $t('UsersPage.itemCount', { count: userList.length }, userList.length) }}
          </ion-text>
          <ion-text
            class="text title-h5"
            v-if="selectedUsersCount !== 0"
          >
            {{ $t('UsersPage.userSelectedCount', { count: selectedUsersCount }, selectedUsersCount) }}
          </ion-text>
          <div
            class="content"
            v-if="selectedUsersCount >= 1"
          >
            <ms-action-bar-button
              v-show="selectedUsersCount === 1"
              class="shortcuts-btn"
              :icon="eye"
              id="button-common-workspaces"
              @click="viewCommonWorkspace()"
            />
          </div>
        </div>
      </div>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { ref, Ref, computed, onMounted, inject } from 'vue';
import {
  IonContent,
  IonItem,
  IonList,
  IonPage,
  IonLabel,
  IonListHeader,
  IonCheckbox,
  IonText,
  popoverController,
} from '@ionic/vue';
import {
  eye,
} from 'ionicons/icons';
import UserListItem from '@/components/users/UserListItem.vue';
import UserCard from '@/components/users/UserCard.vue';
import MsActionBarButton from '@/components/core/ms-action-bar/MsActionBarButton.vue';
import MsGridListToggle from '@/components/core/ms-toggle/MsGridListToggle.vue';
import { DisplayState } from '@/components/core/ms-toggle/MsGridListToggle.vue';
import UserContextMenu from '@/views/users/UserContextMenu.vue';
import { UserAction } from '@/views/users/UserContextMenu.vue';
import MsActionBar from '@/components/core/ms-action-bar/MsActionBar.vue';
import { UserInfo, listRevokedUsers as parsecListRevokedUsers } from '@/parsec';
import { NotificationCenter, NotificationKey, NotificationLevel, Notification } from '@/services/notificationCenter';
import { useI18n } from 'vue-i18n';

const displayView = ref(DisplayState.List);
const userList: Ref<UserInfo[]> = ref([]);
const userListItemRefs: Ref<typeof UserListItem[]> = ref([]);
const userGridItemRefs: Ref<typeof UserCard[]> = ref([]);
// eslint-disable-next-line @typescript-eslint/no-non-null-assertion
const notificationCenter: NotificationCenter = inject(NotificationKey)!;
const { t } = useI18n();

const allUsersSelected = computed({
  get: (): boolean => selectedUsersCount.value === userList.value.length,
  set: (_val) => _val,
});

const indeterminateState = computed({
  get: (): boolean => selectedUsersCount.value > 0 && selectedUsersCount.value < userList.value.length,
  set: (_val) => _val,
});

const selectedUsersCount = computed(() => {
  if (displayView.value === DisplayState.List) {
    return userListItemRefs.value.filter((item) => item.isSelected).length;
  } else {
    return userGridItemRefs.value.filter((item) => item.isSelected).length;
  }
});

function viewCommonWorkspace(): void {
  console.log('View common workspace clicked');
}

function onUserSelect(_user: UserInfo, _selected: boolean): void {
  if (selectedUsersCount.value === 0) {
    selectAllUsers(false);
  }
}

function selectAllUsers(checked: boolean): void {
  if (displayView.value === DisplayState.List) {
    for (const item of userListItemRefs.value || []) {
      item.isSelected = checked;
      if (checked) {
        item.showCheckbox = true;
      } else {
        item.showCheckbox = false;
      }
    }
  } else {
    for (const item of userGridItemRefs.value || []) {
      item.isSelected = checked;
      if (checked) {
        item.showCheckbox = true;
      } else {
        item.showCheckbox = false;
      }
    }
  }
}

function details(user: UserInfo): void {
  console.log(`Show details on user ${user.humanHandle.label}`);
}

async function openUserContextMenu(event: Event, user: UserInfo): Promise<void> {
  const popover = await popoverController
    .create({
      component: UserContextMenu,
      cssClass: 'user-context-menu',
      event: event,
      translucent: true,
      showBackdrop: false,
      dismissOnSelect: true,
      reference: 'event',
      componentProps: {
        isRevoked: user.isRevoked(),
      },
    });
  await popover.present();

  const { data } = await popover.onDidDismiss();
  const actions = new Map<UserAction, (user: UserInfo) => void>([
    [UserAction.Details, details],
  ]);

  if (!data) {
    return;
  }

  const fn = actions.get(data.action);
  if (fn) {
    fn(user);
  }
}

function resetSelection(): void {
  userListItemRefs.value = [];
  userGridItemRefs.value = [];
}

async function refreshUserList(): Promise<void> {
  const result = await parsecListRevokedUsers();
  if (result.ok) {
    userList.value = result.value;
  } else {
    notificationCenter.showToast(new Notification({
      message: t('UsersPage.listRevokedUsersFailed'),
      level: NotificationLevel.Error,
    }));
  }
}

onMounted(async (): Promise<void> => {
  await refreshUserList();
});
</script>

<style scoped lang="scss">
.users-container {
  margin: 2em;
}

.user-list-header {
  color: var(--parsec-color-light-secondary-grey);
  padding-inline-start:0;

  &__label {
    padding: 0 1rem;
    height: 100%;
    display: flex;
    align-items: center;
  }

  .label-selected {
    min-width: 4rem;
    flex-grow: 0;
    display: flex;
    align-items: center;
    justify-content: end;
  }

  .label-name {
    width: 100%;
    max-width: 20vw;
    min-width: 11.25rem;
    white-space: nowrap;
    overflow: hidden;
  }

  .label-email {
    min-width: 17.5rem;
    flex-grow: 0;
  }

  .label-profile {
    min-width: 11.5rem;
    max-width: 10vw;
    flex-grow: 2;
  }

  .label-joined-on {
    min-width: 11.25rem;
    flex-grow: 0;
  }

  .label-space {
    min-width: 4rem;
    flex-grow: 0;
    margin-left: auto;
    margin-right: 1rem;
  }
}

.users-container-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5em;
  overflow-y: auto;
}

.users-toolbar {
  padding: 1em 2em;
  height: 6em;
  background-color: var(--parsec-color-light-secondary-background);
  border-top: 1px solid var(--parsec-color-light-secondary-light);
}

.right-side {
  margin-left: auto;
  display: flex;
}

.users-grid-item {
  --inner-padding-end: 0px;
  --inner-padding-start: 0px;
}
</style>
