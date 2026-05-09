import { Palette, PanelsTopLeft, Type } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useTheme } from '@/context/ThemeContext'

const themeOptions = [
  { value: 'system', title: 'System', description: 'Follow your device preference automatically.' },
  { value: 'light', title: 'Light', description: 'Bright surfaces with soft contrast for daytime use.' },
  { value: 'dark', title: 'Dark', description: 'Low-glare surfaces for evening work and OLED screens.' },
  { value: 'high-contrast', title: 'High contrast', description: 'Maximum contrast and stronger outlines for accessibility.' },
] as const

export function AppearanceSettingsPage() {
  const { t } = useTranslation(['common', 'settings'])
  const { preferences, resolvedTheme, systemTheme, setPreference, resetPreferences, savePreferences } = useTheme()
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const handleSave = async () => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      await savePreferences()
      setMessage(t('settings:appearance.messages.saved'))
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settings:appearance.errors.save'))
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const defaults = resetPreferences()
      await savePreferences(defaults)
      setMessage(t('settings:appearance.messages.reset'))
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : t('settings:appearance.errors.reset'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('settings:appearance.title')}</CardTitle>
          <CardDescription>
            {t('settings:appearance.description')} {t('settings:appearance.systemStatus', { systemTheme, resolvedTheme })}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <Palette className="h-4 w-4 text-primary" />
              <div>
                <h3 className="font-medium">{t('settings:appearance.theme.title')}</h3>
                <p className="text-sm text-muted-foreground">{t('settings:appearance.theme.description')}</p>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {themeOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setPreference('theme', option.value)}
                  className={`rounded-xl border p-4 text-left transition ${preferences.theme === option.value ? 'border-primary bg-primary/5 shadow-sm' : 'hover:bg-muted/60'}`}
                >
                  <p className="font-medium">{option.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{option.description}</p>
                </button>
              ))}
            </div>
          </section>

          <div className="grid gap-4 lg:grid-cols-2">
            <section className="space-y-3">
              <Label htmlFor="accent-color">{t('settings:appearance.accentColor.label')}</Label>
              <div className="flex flex-wrap items-center gap-3">
                <input
                  id="accent-color"
                  type="color"
                  value={preferences.accent_color}
                  aria-label={t('settings:appearance.accentColor.label')}
                  className="h-11 w-16 cursor-pointer rounded-lg border border-input bg-background p-1"
                  onChange={(event) => setPreference('accent_color', event.target.value)}
                />
                <Input value={preferences.accent_color} onChange={(event) => setPreference('accent_color', event.target.value)} className="max-w-xs font-mono uppercase" />
              </div>
              <p className="text-sm text-muted-foreground">{t('settings:appearance.accentColor.description')}</p>
            </section>

            <section className="space-y-3">
              <Label htmlFor="font-size">{t('settings:appearance.fontSize.label')}</Label>
              <Select value={preferences.font_size} onValueChange={(value) => setPreference('font_size', value as typeof preferences.font_size)}>
                <SelectTrigger id="font-size">
                  <SelectValue placeholder={t('settings:appearance.fontSize.label')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="small">{t('settings:appearance.fontSize.small')}</SelectItem>
                  <SelectItem value="medium">{t('settings:appearance.fontSize.medium')}</SelectItem>
                  <SelectItem value="large">{t('settings:appearance.fontSize.large')}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">{t('settings:appearance.fontSize.description')}</p>
            </section>

            <section className="space-y-3">
              <Label htmlFor="density">{t('settings:appearance.density.label')}</Label>
              <Select value={preferences.density} onValueChange={(value) => setPreference('density', value as typeof preferences.density)}>
                <SelectTrigger id="density">
                  <SelectValue placeholder={t('settings:appearance.density.label')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="comfortable">{t('settings:appearance.density.comfortable')}</SelectItem>
                  <SelectItem value="compact">{t('settings:appearance.density.compact')}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">{t('settings:appearance.density.description')}</p>
            </section>

            <section className="space-y-3">
              <Label htmlFor="sidebar-position">{t('settings:appearance.sidebar.label')}</Label>
              <Select value={preferences.sidebar_position} onValueChange={(value) => setPreference('sidebar_position', value as typeof preferences.sidebar_position)}>
                <SelectTrigger id="sidebar-position">
                  <SelectValue placeholder={t('settings:appearance.sidebar.label')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="left">{t('settings:appearance.sidebar.left')}</SelectItem>
                  <SelectItem value="right">{t('settings:appearance.sidebar.right')}</SelectItem>
                  <SelectItem value="collapsed">{t('settings:appearance.sidebar.collapsed')}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground">{t('settings:appearance.sidebar.description')}</p>
            </section>
          </div>

          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="mb-4 flex items-center gap-2">
              <PanelsTopLeft className="h-4 w-4 text-primary" />
              <div>
                <h3 className="font-medium">{t('settings:appearance.preview.title')}</h3>
                <p className="text-sm text-muted-foreground">{t('settings:appearance.preview.description')}</p>
              </div>
            </div>
            <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
              <Card>
                <CardHeader>
                  <CardTitle>Dashboard widget preview</CardTitle>
                  <CardDescription>Buttons, cards, and tables update instantly as you customize the workspace.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-lg border bg-background/70 p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Theme</p>
                      <p className="font-semibold capitalize">{resolvedTheme}</p>
                    </div>
                    <div className="rounded-lg border bg-background/70 p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Density</p>
                      <p className="font-semibold capitalize">{preferences.density}</p>
                    </div>
                    <div className="rounded-lg border bg-background/70 p-3">
                      <p className="text-xs uppercase tracking-wide text-muted-foreground">Font</p>
                      <p className="font-semibold capitalize">{preferences.font_size}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button>{t('settings:appearance.preview.primaryAction')}</Button>
                    <Button variant="outline">{t('settings:appearance.preview.secondaryAction')}</Button>
                    <Button variant="ghost">
                      <Type className="h-4 w-4" />
                      {t('settings:appearance.preview.ghostAction')}
                    </Button>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="preview-name">{t('settings:appearance.preview.inputLabel')}</Label>
                      <Input id="preview-name" value="Math enrichment block" readOnly />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="preview-select">{t('settings:appearance.preview.selectLabel')}</Label>
                      <Select value="ready">
                        <SelectTrigger id="preview-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="ready">Ready to publish</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{t('settings:appearance.preview.tableTitle')}</CardTitle>
                  <CardDescription>{t('settings:appearance.preview.tableDescription')}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Widget</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Notes</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      <TableRow>
                        <TableCell>Assignments</TableCell>
                        <TableCell className="font-medium text-primary">Updated</TableCell>
                        <TableCell>Accent color and focus styles follow your selection.</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Sidebar</TableCell>
                        <TableCell>{preferences.sidebar_position}</TableCell>
                        <TableCell>Desktop navigation reflows left, right, or collapsed.</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          </div>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {message ? <p className="text-sm text-primary">{message}</p> : null}
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void handleSave()} disabled={saving}>
              {saving ? t('common:buttons.save') : t('settings:appearance.actions.save')}
            </Button>
            <Button variant="outline" onClick={() => void handleReset()} disabled={saving}>
              {t('settings:appearance.actions.reset')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
