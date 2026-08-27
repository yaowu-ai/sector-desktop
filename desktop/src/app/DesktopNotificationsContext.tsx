import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import {
  loadDesktopNotifications,
  markDesktopNotificationRead,
  type DesktopNotification,
} from '../services/desktopApi'
import { useDesktopAuth } from './DesktopAuthContext'

const NOTIFICATION_POLL_MS = 15 * 1000

interface DesktopNotificationsContextValue {
  notifications: DesktopNotification[]
  loading: boolean
  unreadCount: number
  refreshNotifications: () => Promise<void>
  markRead: (notification: DesktopNotification) => Promise<void>
  markAllRead: () => Promise<void>
}

const DesktopNotificationsContext = createContext<DesktopNotificationsContextValue | null>(null)

export function DesktopNotificationsProvider({ children }: { children: React.ReactNode }) {
  const auth = useDesktopAuth()
  const [notifications, setNotifications] = useState<DesktopNotification[]>([])
  const [loading, setLoading] = useState(false)

  const refreshNotifications = useCallback(async (options: { silent?: boolean } = {}) => {
    if (!auth.session) {
      setNotifications([])
      return
    }

    if (!options.silent) setLoading(true)
    try {
      const response = await loadDesktopNotifications(auth.session, auth.apiBaseUrl)
      setNotifications(response.notifications ?? [])
    } finally {
      if (!options.silent) setLoading(false)
    }
  }, [auth.apiBaseUrl, auth.session])

  const markRead = useCallback(
    async (notification: DesktopNotification) => {
      if (!auth.session) return
      setNotifications((current) => current.map((item) => (item.id === notification.id ? markAsRead(item) : item)))
      try {
        await markDesktopNotificationRead(auth.session, notification.id, auth.apiBaseUrl)
      } catch (error) {
        void refreshNotifications()
        throw error
      }
    },
    [auth.apiBaseUrl, auth.session, refreshNotifications],
  )

  const markAllRead = useCallback(async () => {
    if (!auth.session) return
    const unreadNotifications = notifications.filter((item) => !item.read)
    if (unreadNotifications.length === 0) return

    setNotifications((current) => current.map(markAsRead))
    const results = await Promise.allSettled(
      unreadNotifications.map((item) => markDesktopNotificationRead(auth.session!, item.id, auth.apiBaseUrl)),
    )
    if (results.some((result) => result.status === 'rejected')) {
      await refreshNotifications()
      throw new Error('部分消息标记已读失败，请刷新后重试')
    }
    void refreshNotifications()
  }, [auth.apiBaseUrl, auth.session, notifications, refreshNotifications])

  useEffect(() => {
    void refreshNotifications().catch(() => undefined)
  }, [refreshNotifications])

  useEffect(() => {
    if (!auth.session) return
    const id = window.setInterval(() => {
      void refreshNotifications({ silent: true }).catch(() => undefined)
    }, NOTIFICATION_POLL_MS)
    return () => window.clearInterval(id)
  }, [auth.session, refreshNotifications])

  const unreadCount = notifications.filter((item) => !item.read).length
  const value = useMemo(
    () => ({
      notifications,
      loading,
      unreadCount,
      refreshNotifications,
      markRead,
      markAllRead,
    }),
    [loading, markAllRead, markRead, notifications, refreshNotifications, unreadCount],
  )

  return <DesktopNotificationsContext.Provider value={value}>{children}</DesktopNotificationsContext.Provider>
}

export function useDesktopNotifications() {
  const context = useContext(DesktopNotificationsContext)
  if (!context) {
    throw new Error('useDesktopNotifications must be used inside DesktopNotificationsProvider')
  }
  return context
}

function markAsRead(notification: DesktopNotification): DesktopNotification {
  return { ...notification, read: true, readAt: notification.readAt || new Date().toISOString() }
}
