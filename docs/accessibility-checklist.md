# Accessibility manual testing checklist

- Verify the skip link appears on keyboard focus and moves focus to the main content region.
- Navigate every page with Tab, Shift+Tab, Enter, Space, and Escape only; confirm visible focus states remain obvious on buttons, links, inputs, dialogs, and navigation.
- Open the mobile navigation and notifications panel with the keyboard; confirm focus is trapped inside each surface until it is closed and Escape closes them.
- Confirm the global search shortcut hint (Ctrl/Cmd+K) is present and the shortcut focuses the search field.
- Review all icon-only controls with a screen reader and confirm labels are announced clearly.
- Check loading, error, offline, install, and update banners with a screen reader and confirm live-region announcements are spoken once.
- Verify active navigation items are announced correctly and breadcrumb/navigation landmarks are exposed.
- Test forms for labels, required state, and error announcements; confirm checkbox groups and select controls read the expected label text.
- Review meaningful images for descriptive alt text and confirm decorative icons are hidden from assistive technology.
- Zoom to 200% and test common viewport widths (320px, 768px, 1280px); confirm content reflows without horizontal scrolling in normal workflows.
- Confirm mobile tap targets remain at least 44x44px for primary controls, menu buttons, and bottom navigation.
- Run `cd frontend && npm run lint` and `cd frontend && npm run build` before release.
