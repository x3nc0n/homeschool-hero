import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import i18next from 'i18next'

const root = path.resolve(process.cwd(), 'src', 'locales')

function loadJson(...segments) {
  return JSON.parse(readFileSync(path.join(root, ...segments), 'utf8'))
}

async function createInstance(language = 'en') {
  const instance = i18next.createInstance()
  await instance.init({
    lng: language,
    fallbackLng: 'en',
    defaultNS: 'common',
    ns: ['common', 'dashboard', 'auth', 'settings'],
    resources: {
      en: {
        common: loadJson('en', 'common.json'),
        dashboard: loadJson('en', 'dashboard.json'),
        auth: loadJson('en', 'auth.json'),
        settings: loadJson('en', 'settings.json'),
      },
      es: {
        common: loadJson('es', 'common.json'),
      },
    },
    interpolation: { escapeValue: false },
    returnNull: false,
    initImmediate: false,
  })
  return instance
}

test('initializes in english by default', async () => {
  const i18n = await createInstance()
  assert.equal(i18n.language, 'en')
  assert.equal(i18n.t('appName'), 'Homeschool Hero')
})

test('loads translation keys across namespaces', async () => {
  const i18n = await createInstance()
  assert.equal(i18n.t('hero.familyTitle', { ns: 'dashboard' }), 'Family dashboard')
  assert.equal(i18n.t('login.title', { ns: 'auth' }), 'Welcome back')
  assert.equal(i18n.t('language.title', { ns: 'settings' }), 'Language preference')
})

test('supports language switching, interpolation, and pluralization', async () => {
  const i18n = await createInstance()
  await i18n.changeLanguage('es')

  assert.equal(i18n.t('greeting', { name: 'John' }), 'Bienvenido de nuevo, John')
  assert.equal(i18n.t('notifications.unreadCount', { count: 2 }), '2 sin leer')
})

test('falls back to english when a key is missing in spanish', async () => {
  const i18n = await createInstance('es')
  assert.equal(i18n.t('hero.familyTitle', { ns: 'dashboard' }), 'Family dashboard')
})
