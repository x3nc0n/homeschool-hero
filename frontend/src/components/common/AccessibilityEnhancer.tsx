import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

const FORM_CONTROL_SELECTOR = [
  'input:not([type="hidden"])',
  'textarea',
  'select',
  'button[role="combobox"]',
  '[role="textbox"]',
].join(', ')

let generatedIdCount = 0

function nextId(prefix: string) {
  generatedIdCount += 1
  return `${prefix}-${generatedIdCount}`
}

function associateStandaloneLabels(root: ParentNode) {
  const labels = Array.from(root.querySelectorAll<HTMLLabelElement>('label:not([for])'))

  labels.forEach((label) => {
    if (label.control) {
      if (!label.id) {
        label.id = nextId('field-label')
      }
      return
    }

    const parent = label.parentElement
    if (!parent) return

    const control = parent.querySelector<HTMLElement>(FORM_CONTROL_SELECTOR)
    if (!control || label.contains(control)) return

    if (!label.id) {
      label.id = nextId('field-label')
    }

    if (control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement || control instanceof HTMLSelectElement) {
      if (!control.id) {
        control.id = nextId('field-control')
      }
      label.htmlFor = control.id
      return
    }

    const labelledBy = new Set((control.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean))
    labelledBy.add(label.id)
    control.setAttribute('aria-labelledby', Array.from(labelledBy).join(' '))
  })
}

export function AccessibilityEnhancer() {
  const location = useLocation()

  useEffect(() => {
    const root = document.getElementById('root')
    if (!root) return

    const sync = () => associateStandaloneLabels(root)
    sync()

    const observer = new MutationObserver(() => sync())
    observer.observe(root, {
      childList: true,
      subtree: true,
    })

    return () => observer.disconnect()
  }, [location.pathname, location.search])

  return null
}
