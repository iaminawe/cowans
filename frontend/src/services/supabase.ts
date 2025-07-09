import { createClient } from '@supabase/supabase-js'

// Get environment variables
const supabaseUrl = process.env.REACT_APP_SUPABASE_URL || 'https://gqozcvqgsjaagnnjukmo.supabase.co'
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdxb3pjdnFnc2phYWdubmp1a21vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTE3NDgyMzEsImV4cCI6MjA2NzMyNDIzMX0.xnt1D1f4nUhBmoqdTZOgdEtRERdrH0EkWdAaPcmlDoc'

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase configuration')
}

// Create Supabase client
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    storage: window.localStorage,
    storageKey: 'supabase.auth.token'
  }
})

// Helper to get current session
export const getSession = async () => {
  const { data: { session }, error } = await supabase.auth.getSession()
  if (error) {
    console.error('Error getting session:', error)
    return null
  }
  return session
}

// Helper to get access token
export const getAccessToken = async () => {
  const session = await getSession()
  return session?.access_token || null
}